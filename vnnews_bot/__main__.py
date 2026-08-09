"""CLI: vnnews-bot — tin tức real-time báo VN → Telegram."""

from __future__ import annotations

import argparse
import logging
import sys

from .bot import format_message, run_cycle, run_forever
from .config import STATE_PATH, Config
from .feeds import fetch
from .store import SeenStore
from .telegram import Telegram


def _setup_log(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vnnews-bot", description="Tin tức real-time báo VN gửi qua Telegram")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run", help="Chạy vòng lặp gửi tin liên tục")
    sub.add_parser("once", help="Quét & gửi đúng 1 vòng rồi thoát")
    sub.add_parser("dry-run", help="Quét & in ra bài mới, KHÔNG gửi")
    sub.add_parser("check", help="Kiểm tra token/chat (getMe + gửi 1 tin thử)")
    sp = sub.add_parser("sources", help="In & thử tải từng nguồn RSS")
    sp.add_argument("--limit", type=int, default=2, help="Số bài in mỗi nguồn")

    args = p.parse_args(argv)
    _setup_log(args.verbose)

    if args.cmd == "sources":
        cfg = Config.load()
        for name, url in cfg.sources.items():
            try:
                arts = fetch(name, url, timeout=cfg.request_timeout)
                print(f"✔ {name} ({len(arts)} bài) — {url}")
                for a in arts[: args.limit]:
                    print(f"    · {a.title}")
            except Exception as e:  # noqa: BLE001
                print(f"✘ {name} LỖI: {e} — {url}")
        return 0

    if args.cmd == "dry-run":
        cfg = Config.load()
        seen = SeenStore(STATE_PATH, limit=cfg.seen_limit)
        run_cycle(cfg, Telegram(cfg.bot_token or "x"), seen, dry_run=True)
        return 0

    # các lệnh cần token/chat
    cfg = Config.load()
    cfg.require()

    if args.cmd == "check":
        tg = Telegram(cfg.bot_token, timeout=cfg.request_timeout)
        me = tg.get_me()
        print(f"Bot OK: @{me.get('username')} (id {me.get('id')})")
        tg.send_message(cfg.chat_id, "✅ <b>vnnews-bot</b> kết nối thành công.")
        print(f"Đã gửi tin thử tới chat {cfg.chat_id}.")
        return 0

    if args.cmd == "once":
        tg = Telegram(cfg.bot_token, timeout=cfg.request_timeout)
        seen = SeenStore(STATE_PATH, limit=cfg.seen_limit)
        run_cycle(cfg, tg, seen)
        return 0

    if args.cmd == "run":
        try:
            run_forever(cfg)
        except KeyboardInterrupt:
            print("\nDừng.", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
