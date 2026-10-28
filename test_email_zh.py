"""Regression tests for the Chinese EDM; synthetic articles are only fixtures."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from build_email_zh import build, rank, link

class EDMSafetyTests(unittest.TestCase):
    def test_rebuild_preserves_issue_feed_bytes_and_new_issue_gets_new_time(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            data=self.sample()
            (root/"data.json").write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            with patch("build_email_zh.datetime",wraps=datetime) as clock:
                clock.now.return_value=datetime(2026,10,26,1,30,tzinfo=timezone.utc)
                build(root)
            first=(root/"edm/feed.xml").read_bytes()
            with patch("build_email_zh.datetime",wraps=datetime) as clock:
                clock.now.return_value=datetime(2026,10,27,2,30,tzinfo=timezone.utc)
                build(root)
                self.assertEqual(first,(root/"edm/feed.xml").read_bytes())
                data["date"]="2026-10-27"
                (root/"data.json").write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
                build(root)
            item=ET.parse(root/"edm/feed.xml").find("./channel/item")
            self.assertEqual(item.findtext("guid"),"ai-daily-2026-10-27")
            self.assertEqual(item.findtext("pubDate"),"Tue, 27 Oct 2026 02:30:00 +0000")

    def sample(self,n=14):
        return {"date":"2026-10-26","sections":["廣告平台 & 行銷科技"],
                "items":[{"title":"測試新聞 "+str(i),"url":"https://example.com/story/"+str(i),
                          "summary":"此為測試資料，並非實際新聞。",
                          "section":"廣告平台 & 行銷科技","action":"影響生意",
                          "why":"測試中的行銷影響說明。",
                          "next_step":"核對來源。"} for i in range(n)]}
    def test_generates_valid_html_and_feed(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"data.json").write_text(json.dumps(self.sample(),ensure_ascii=False),encoding="utf-8")
            build(root)
            page=(root/"email-zh.html").read_text(encoding="utf-8")
            feed=(root/"edm/feed.xml").read_text(encoding="utf-8")
            self.assertEqual(page.count("MARKETER TAKEAWAY"),6)
            self.assertIn("utm_campaign=ai-daily-2026-10-26",page)
            self.assertIn("lang=zh&amp;utm_source=edm",page)
            self.assertLess(len(page.encode()),102400)
            root_xml=ET.fromstring(feed)
            item=root_xml.find("./channel/item")
            self.assertIn("<table",item.find("description").text)
            self.assertIn("2026-10-26",item.find("title").text)
    def test_stops_below_editorial_floor(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"data.json").write_text(json.dumps(self.sample(9),ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"HELD"):
                build(root)
            self.assertFalse((root/"edm/feed.xml").exists())
    def test_explicit_priority_and_links(self):
        docs=self.sample()["items"]
        docs[11]["edm_priority"]=1
        self.assertEqual(rank(docs)[0]["title"],docs[11]["title"])
        u=link("https://carriehw.github.io/ai-marketing-daily/","2026-10-26","highlight-1")
        self.assertIn("utm_source=edm",u)

if __name__=="__main__":
    unittest.main()
