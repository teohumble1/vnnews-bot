"""Đọc & parse RSS/Atom bằng stdlib (urllib + xml.etree)."""

from __future__ import annotations

import gzip
import html
import http.client
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# UA kiểu trình duyệt: một số site (BleepingComputer, SecurityWeek) trả 403 cho UA lạ
_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r"""<img[^>]+src=['"]([^'"]+)""", re.IGNORECASE)
# Namespace Atom (một số báo trả Atom thay vì RSS)
_ATOM = "{http://www.w3.org/2005/Atom}"
# Media RSS (media:content / media:thumbnail) — BBC, nhiều báo dùng
_MRSS = "{http://search.yahoo.com/mrss/}"
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")


@dataclass
class Article:
    source: str
    title: str
    link: str
    summary: str
    published: datetime | None
    image: str | None = None

    def key(self) -> str:
        """Định danh chống trùng: ưu tiên link, fallback title."""
        return self.link.strip() or self.title.strip()


def _extract_image(item: ET.Element, raw_desc: str | None) -> str | None:
    """Tìm URL ảnh thumbnail: enclosure → media:content/thumbnail → <img> trong description."""
    # 1) <enclosure type="image/..."> hoặc url đuôi ảnh
    for enc in item.findall("enclosure"):
        url = enc.get("url")
        typ = (enc.get("type") or "").lower()
        if url and (typ.startswith("image") or url.lower().split("?")[0].endswith(_IMG_EXT)):
            return url
    # 2) media:content / media:thumbnail (có/không namespace), kể cả trong media:group
    for parent in (item, item.find(f"{_MRSS}group")):
        if parent is None:
            continue
        for tag in (f"{_MRSS}content", f"{_MRSS}thumbnail", "thumbnail", "content"):
            el = parent.find(tag)
            if el is not None and el.get("url"):
                return el.get("url")
    # 3) <img src="..."> trong description HTML
    m = _IMG_RE.search(raw_desc or "")
    if m:
        return m.group(1)
    return None


def _download(url: str, timeout: int, attempts: int = 2) -> bytes:
    """Tải feed, thử lại 1 lần khi lỗi mạng tạm thời (IncompleteRead, timeout...)."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                encoding = (resp.headers.get("Content-Encoding") or "").lower()
            return _decompress(data, encoding)
        except urllib.error.HTTPError:
            raise                                    # 404/403: thử lại vô ích
        except (OSError, http.client.HTTPException) as e:
            last = e
            if i + 1 < attempts:
                time.sleep(1)
    raise last                                       # type: ignore[misc]


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
    data = _download(url, timeout)
    root = ET.fromstring(data)

    items = root.findall(".//item")
    if items:                              # RSS 2.0
        return [_from_rss(source, it) for it in items]
    # Atom fallback
    entries = root.findall(f".//{_ATOM}entry")
    return [_from_atom(source, e) for e in entries]


def _from_rss(source: str, item: ET.Element) -> Article:
    raw_desc = item.findtext("description")
    return Article(
        source=source,
        title=_clean(item.findtext("title")),
        link=(item.findtext("link") or "").strip(),
        summary=_clean(raw_desc),
        published=_parse_date(item.findtext("pubDate")),
        image=_extract_image(item, raw_desc),
    )


def _from_atom(source: str, entry: ET.Element) -> Article:
    link_el = entry.find(f"{_ATOM}link")
    link = link_el.get("href") if link_el is not None else ""
    raw_desc = entry.findtext(f"{_ATOM}summary")
    return Article(
        source=source,
        title=_clean(entry.findtext(f"{_ATOM}title")),
        link=(link or "").strip(),
        summary=_clean(raw_desc),
        published=_parse_date(entry.findtext(f"{_ATOM}updated")),
        image=_extract_image(entry, raw_desc),
    )
