"""Client Telegram Bot API tối giản (stdlib urllib), có retry + backoff."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

_API = "https://api.telegram.org/bot{token}/{method}"
log = logging.getLogger("vnnews.telegram")


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, timeout: int = 15, retries: int = 3) -> None:
        self._token = token
        self._timeout = timeout
        self._retries = retries

    def _call(self, method: str, params: dict) -> dict:
        url = _API.format(token=self._token, method=method)
        body = urllib.parse.urlencode(params).encode("utf-8")
        last_err: Exception | None = None

        for attempt in range(1, self._retries + 1):
            req = urllib.request.Request(url, data=body)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    payload = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                if e.code == 429:                         # rate limit → tôn trọng retry_after
                    wait = _retry_after(detail, attempt)
                    log.warning("429 rate limit, chờ %.1fs (lần %d)", wait, attempt)
                    last_err = e
                    time.sleep(wait)
                    continue
                # 4xx khác (token sai, chat sai...) là lỗi vĩnh viễn, không retry
                raise TelegramError(f"HTTP {e.code} khi gọi {method}: {detail}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # lỗi mạng tạm thời (timeout, DNS, reset...) → backoff rồi thử lại
                last_err = e
                wait = min(2 ** attempt, 15)
                log.warning("Lỗi mạng khi gọi %s: %s — thử lại sau %ds (lần %d/%d)",
                            method, e, wait, attempt, self._retries)
                time.sleep(wait)
                continue

            if not payload.get("ok"):
                raise TelegramError(f"{method} lỗi: {payload.get('description')}")
            return payload["result"]

        raise TelegramError(f"{method} thất bại sau {self._retries} lần: {last_err}")

    def send_message(self, chat_id: str, text: str, *, disable_preview: bool = False) -> dict:
        return self._call("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_preview else "false",
        })

    def get_me(self) -> dict:
        return self._call("getMe", {})


def _retry_after(detail: str, attempt: int) -> float:
    """Đọc retry_after từ body 429 của Telegram, fallback backoff mũ."""
    try:
        params = json.loads(detail).get("parameters", {})
        return float(params.get("retry_after", 2 ** attempt))
    except (ValueError, AttributeError):
        return float(min(2 ** attempt, 15))
