"""Đọc & parse RSS/Atom bằng stdlib (urllib + xml.etree)."""

from __future__ import annotations

import gzip
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_USER_AGENT = "vnnews-bot/0.1 (+https://localhost)"
_TAG_RE = re.compile(r"<[^>]+>")
# Namespace Atom (một số báo trả Atom thay vì RSS)
_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class Article:
    source: str
    title: str
    link: str
    summary: str
    published: datetime | None

    def key(self) -> str:
        """Định danh chống trùng: ưu tiên link, fallback title."""
        return self.link.strip() or self.title.strip()


def _decompress(data: bytes, encoding: str) -> bytes:
    """Một số báo (vd Tiền Phong) trả gzip dù client không xin. Tự nhận diện & giải nén."""
    if encoding == "gzip" or data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    if encoding == "deflate":
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)
    return data


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG_RE.sub("", text)          # bỏ HTML tag trong description
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for parser in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            dt = parser(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError):
            continue
    return None


def fetch(source: str, url: str, timeout: int = 15) -> list[Article]:
    """Tải 1 feed, trả về danh sách Article. Lỗi mạng → raise cho caller xử lý."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
    data = _decompress(data, encoding)
    root = ET.fromstring(data)

    items = root.findall(".//item")
    if items:                              # RSS 2.0
        return [_from_rss(source, it) for it in items]
    # Atom fallback
    entries = root.findall(f".//{_ATOM}entry")
    return [_from_atom(source, e) for e in entries]


def _from_rss(source: str, item: ET.Element) -> Article:
    return Article(
        source=source,
        title=_clean(item.findtext("title")),
        link=(item.findtext("link") or "").strip(),
        summary=_clean(item.findtext("description")),
        published=_parse_date(item.findtext("pubDate")),
    )


def _from_atom(source: str, entry: ET.Element) -> Article:
    link_el = entry.find(f"{_ATOM}link")
    link = link_el.get("href") if link_el is not None else ""
    return Article(
        source=source,
        title=_clean(entry.findtext(f"{_ATOM}title")),
        link=(link or "").strip(),
        summary=_clean(entry.findtext(f"{_ATOM}summary")),
        published=_parse_date(entry.findtext(f"{_ATOM}updated")),
    )
