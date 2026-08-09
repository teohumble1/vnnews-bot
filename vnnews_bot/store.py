"""Lưu link đã gửi để chống trùng (JSON, FIFO cắt bớt)."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path


class SeenStore:
    def __init__(self, path: Path, limit: int = 5000) -> None:
        self._path = path
        self._limit = limit
        self._seen: "OrderedDict[str, None]" = OrderedDict()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                keys = json.loads(self._path.read_text(encoding="utf-8"))
                for k in keys:
                    self._seen[k] = None
            except (ValueError, OSError):
                self._seen.clear()

    def has(self, key: str) -> bool:
        return key in self._seen

    def add(self, key: str) -> None:
        self._seen[key] = None
        self._seen.move_to_end(key)
        while len(self._seen) > self._limit:
            self._seen.popitem(last=False)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(self._seen.keys()), ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    def __len__(self) -> int:
        return len(self._seen)
