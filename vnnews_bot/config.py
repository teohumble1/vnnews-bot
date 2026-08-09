"""Cấu hình: nguồn RSS báo VN + đọc token/chat từ env hoặc file config.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Nguồn tin mặc định — RSS "tin mới nhất" của các báo lớn VN.
DEFAULT_SOURCES: dict[str, str] = {
    "VnExpress":   "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "Tuổi Trẻ":    "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "Thanh Niên":  "https://thanhnien.vn/rss/home.rss",
    "Dân Trí":     "https://dantri.com.vn/rss/home.rss",
    "VietnamNet":  "https://vietnamnet.vn/rss/thoi-su.rss",
    "Người Lao Động": "https://nld.com.vn/rss/home.rss",
    "Tiền Phong":  "https://tienphong.vn/rss/home.rss",
}

CONFIG_PATH = Path(os.environ.get("VNNEWS_CONFIG", Path.home() / ".config" / "vnnews-bot" / "config.json"))
STATE_PATH = Path(os.environ.get("VNNEWS_STATE", Path.home() / ".local" / "state" / "vnnews-bot" / "seen.json"))


@dataclass
class Config:
    bot_token: str = ""
    chat_id: str = ""
    sources: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SOURCES))
    poll_interval: int = 120          # giây giữa 2 lần quét
    max_per_cycle: int = 8            # tối đa bài gửi mỗi vòng (tránh spam)
    request_timeout: int = 15
    seen_limit: int = 5000            # số link nhớ để chống trùng

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        # 1) file config.json (nếu có)
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.bot_token = data.get("bot_token", cfg.bot_token)
            cfg.chat_id = str(data.get("chat_id", cfg.chat_id))
            if data.get("sources"):
                cfg.sources = dict(data["sources"])
            cfg.poll_interval = int(data.get("poll_interval", cfg.poll_interval))
            cfg.max_per_cycle = int(data.get("max_per_cycle", cfg.max_per_cycle))
        # 2) env override (ưu tiên cao nhất)
        cfg.bot_token = os.environ.get("VNNEWS_BOT_TOKEN", cfg.bot_token)
        cfg.chat_id = os.environ.get("VNNEWS_CHAT_ID", cfg.chat_id)
        return cfg

    def require(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("bot_token (env VNNEWS_BOT_TOKEN)")
        if not self.chat_id:
            missing.append("chat_id (env VNNEWS_CHAT_ID)")
        if missing:
            raise SystemExit(
                "Thiếu cấu hình: " + ", ".join(missing) + "\n"
                "Đặt qua biến môi trường hoặc file " + str(CONFIG_PATH)
            )
