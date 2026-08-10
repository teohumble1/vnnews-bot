"""Vòng lặp chính: quét feeds → lọc bài mới → gửi Telegram."""

from __future__ import annotations

import html
import logging
import time

from .config import STATE_PATH, Config
from .feeds import Article, fetch
from .store import SeenStore
from .telegram import Telegram, TelegramError

log = logging.getLogger("vnnews")


def format_message(a: Article) -> str:
    """HTML message cho Telegram. Escape nội dung, giữ tối đa 3 dòng."""
    title = html.escape(a.title)
    source = html.escape(a.source)
    parts = [f"📰 <b>{title}</b>"]
    # Bỏ tóm tắt nếu nó trùng/lặp tiêu đề (vd Google News nhét lại headline)
    tkey = a.title.strip().lower()[:60]
    same = bool(tkey) and a.summary.strip().lower().startswith(tkey)
    if a.summary and not same:
        summary = a.summary[:280] + ("…" if len(a.summary) > 280 else "")
        parts.append(html.escape(summary))
    when = a.published.strftime("%H:%M %d/%m") if a.published else ""
    footer = f"🔗 <a href=\"{html.escape(a.link)}\">{source}</a>"
    if when:
        footer += f" · {when}"
    parts.append(footer)
    return "\n\n".join(parts)


def collect_new(cfg: Config, seen: SeenStore) -> list[Article]:
    """Quét tất cả nguồn, trả về bài chưa từng gửi (mới nhất trước)."""
    fresh: list[Article] = []
    for source, url in cfg.sources.items():
        try:
            articles = fetch(source, url, timeout=cfg.request_timeout)
        except Exception as e:                       # noqa: BLE001 — 1 nguồn lỗi không được kéo sập cả bot
            log.warning("Không tải được %s: %s", source, e)
            continue
        for a in articles:
            key = a.key()
            if key and not seen.has(key):
                fresh.append(a)
    # sắp xếp: có ngày thì mới nhất trước; không ngày về cuối
    fresh.sort(key=lambda a: (a.published is not None, a.published or 0), reverse=True)
    return fresh


def run_cycle(cfg: Config, tg: Telegram, seen: SeenStore, *, dry_run: bool = False) -> int:
    """Một vòng quét + gửi. Trả về số bài đã gửi."""
    fresh = collect_new(cfg, seen)
    if not fresh:
        log.info("Không có bài mới.")
        return 0

    to_send = fresh[: cfg.max_per_cycle]
    sent = 0
    for a in to_send:
        msg = format_message(a)
        if dry_run:
            log.info("[dry-run] %s | %s", a.source, a.title)
        else:
            try:
                tg.send_message(cfg.chat_id, msg)
            except TelegramError as e:
                log.error("Gửi thất bại: %s", e)
                break                                # dừng vòng này, giữ chưa-seen để thử lại
            time.sleep(1.2)                          # nương rate-limit Telegram
        seen.add(a.key())
        sent += 1

    # đánh dấu đã-seen cho phần còn lại (không gửi vì vượt max) để lần sau không dồn
    for a in fresh[cfg.max_per_cycle:]:
        seen.add(a.key())

    if not dry_run:
        seen.save()
    log.info("Đã gửi %d bài (còn %d bài mới bị hoãn).", sent, max(0, len(fresh) - len(to_send)))
    return sent


def run_forever(cfg: Config, *, dry_run: bool = False) -> None:
    tg = Telegram(cfg.bot_token, timeout=cfg.request_timeout)
    seen = SeenStore(STATE_PATH, limit=cfg.seen_limit)
    log.info("Bắt đầu quét mỗi %ds, %d nguồn, đã nhớ %d link.",
             cfg.poll_interval, len(cfg.sources), len(seen))
    while True:
        try:
            run_cycle(cfg, tg, seen, dry_run=dry_run)
        except Exception as e:                       # noqa: BLE001
            log.exception("Lỗi vòng quét: %s", e)
        time.sleep(cfg.poll_interval)
