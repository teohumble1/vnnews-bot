"""Test offline cho vnnews-bot (không cần mạng)."""

import gzip
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vnnews_bot import feeds
from vnnews_bot.bot import format_message
from vnnews_bot.feeds import Article, _clean, _decompress, _parse_date
from vnnews_bot.store import SeenStore

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Tin &amp; th&#7917;</title>
    <link>https://vnexpress.net/a-123.html</link>
    <description>&lt;p&gt;M&#7897;t &lt;b&gt;n&#7897;i dung&lt;/b&gt;   d&#7841;ng HTML&lt;/p&gt;</description>
    <pubDate>Sat, 09 Aug 2026 08:30:00 +0700</pubDate>
  </item>
  <item>
    <title>Bai khong ngay</title>
    <link>https://tuoitre.vn/b-456.html</link>
    <description>tom tat</description>
  </item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom title</title>
    <link href="https://example.vn/atom-1"/>
    <summary>atom summary</summary>
    <updated>2026-08-09T01:30:00Z</updated>
  </entry>
</feed>"""


class ParseTests(unittest.TestCase):
    def test_rss_parse(self):
        arts = feeds._from_rss("VnExpress", __import__("xml.etree.ElementTree", fromlist=["fromstring"]).fromstring(RSS).find(".//item"))
        self.assertEqual(arts.source, "VnExpress")
        self.assertEqual(arts.title, "Tin & thử")
        self.assertEqual(arts.link, "https://vnexpress.net/a-123.html")
        self.assertNotIn("<b>", arts.summary)              # HTML tag bị strip
        self.assertIn("nội dung", arts.summary)
        self.assertNotIn("   ", arts.summary)              # khoảng trắng bị gộp
        self.assertIsNotNone(arts.published)

    def test_clean_strips_and_collapses(self):
        self.assertEqual(_clean("<p>a  &amp;  b</p>"), "a & b")
        self.assertEqual(_clean(None), "")

    def test_parse_date_variants(self):
        self.assertIsNotNone(_parse_date("Sat, 09 Aug 2026 08:30:00 +0700"))
        self.assertIsNotNone(_parse_date("2026-08-09T01:30:00Z"))
        self.assertIsNone(_parse_date("khong phai ngay"))
        self.assertIsNone(_parse_date(None))

    def test_decompress_gzip_by_magic(self):
        raw = b"<rss></rss>"
        self.assertEqual(_decompress(gzip.compress(raw), ""), raw)   # nhận diện qua magic byte
        self.assertEqual(_decompress(raw, ""), raw)                  # data thường giữ nguyên

    def test_article_key_fallback(self):
        a = Article("S", "Tieu de", "", "", None)
        self.assertEqual(a.key(), "Tieu de")                          # không link → dùng title


class StoreTests(unittest.TestCase):
    def test_dedupe_persist_and_trim(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seen.json"
            s = SeenStore(p, limit=3)
            for k in ("a", "b", "c", "d"):
                s.add(k)
            self.assertFalse(s.has("a"))       # bị cắt (FIFO, quá limit)
            self.assertTrue(s.has("d"))
            s.save()
            s2 = SeenStore(p, limit=3)          # nạp lại từ đĩa
            self.assertTrue(s2.has("d"))
            self.assertEqual(len(s2), 3)


class FormatTests(unittest.TestCase):
    def test_format_escapes_and_truncates(self):
        a = Article("VnExpress", "A <b>title</b> & co", "https://x.vn/1", "s" * 400,
                    datetime(2026, 8, 9, 8, 30))
        msg = format_message(a)
        self.assertIn("&lt;b&gt;", msg)         # title được escape
        self.assertIn("VnExpress", msg)
        self.assertIn("…", msg)                 # summary bị cắt
        self.assertIn("08:30 09/08", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
