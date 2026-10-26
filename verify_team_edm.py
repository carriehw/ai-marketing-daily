#!/usr/bin/env python3
"""Fail the build if the English-only Outlook EDM loses key contracts."""
import datetime as dt
import html
import json
import re
import base64
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

root = Path(__file__).resolve().parent
data = json.loads((root/"data.json").read_text(encoding="utf-8"))
p = json.loads((root/"edm/payload.json").read_text(encoding="utf-8"))
body = (root/"edm/team.html").read_text(encoding="utf-8")
subject = (root/"edm/subject.txt").read_text(encoding="utf-8").strip()
index = (root/"index.html").read_text(encoding="utf-8")
date = dt.date.fromisoformat(data["date"]).isoformat()

checks = {
    "English-only payload": p.get("language") == "en" and '<html lang="en"' in body,
    "Single data source": p.get("edition_date") == date and p.get("headline_count") == len(data["items"]),
    "Editorial news floor": len(data["items"]) >= 10,
    "Exactly six highlighted": p.get("featured_count") == 6 and body.count("border-top:4px solid") == 6,
    "Body matches payload": p.get("html") == body,
    "Subject matches payload": p.get("subject") == subject and date in subject,
    "Email not clipped": len(body.encode("utf-8")) < 102400,
    "No Chinese text in English issue": not re.search(r"[\u3400-\u9fff]", body),
    "Complete action board": body.count("0</td>") == 0 and "What Marketers Should Do" in body,
    "Not a file attachment": "<table " in body and "<body" in body,
    "No recipient addresses leaked": "@i-click.com" not in json.dumps(p),
    "No unsupported scripts": "<script" not in body.lower(),
    "Editorial-approved payload": p.get("verification_status") == "editorial_approved",
    "Stable per-day edition ID": p.get("edition_id") == "ai-marketing-daily-en-" + date,
    "Outlook card spacer rows": body.count('height="16"') >= 6,
    "Outlook labels use table cells": body.count('nowrap="nowrap"') == 6,
    "CTA has cell padding": 'mso-padding-alt:14px 26px' in body,
    "Classic Outlook width fallback": '<!--[if mso]><table role="presentation" width="620"' in body,
}
class FontAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.missing=[]
    def handle_starttag(self, tag, attrs):
        if tag in {"body", "table", "td", "div", "p", "a", "span", "b"}:
            style=dict(attrs).get("style", "").lower()
            if "font-family:arial," not in style:
                self.missing.append(tag)
font_audit=FontAudit()
font_audit.feed(body)
checks["Every text element has an explicit sans-serif font"] = not font_audit.missing
feed = ET.parse(root/"edm/payload-feed.xml").getroot()
feed_items = feed.findall("channel/item")
checks["One current English RSS payload"] = len(feed_items) == 1 and feed_items[0].findtext("title") == subject
encoded = feed_items[0].findtext("description")
checks["RSS decodes byte-for-byte to canonical JSON"] = base64.b64decode(encoded, validate=True) == (root/"edm/payload.json").read_bytes()
anchors = set(re.findall(r'id="([a-z0-9][a-z0-9-]*-[0-9a-f]{6})"', index))
urls = re.findall(r'href="([^"]+)"', body)
if len(urls) != 7:
    checks["Exactly six story links and one CTA"] = False
else:
    checks["Exactly six story links and one CTA"] = True
checks["Links target source site only"] = all(
    urlsplit(html.unescape(url)).netloc.lower() == "carriehw.github.io" for url in urls
)
checks["All links tracked and English"] = all(
    parse_qs(urlsplit(html.unescape(url)).query).get("lang") == ["en"]
    and parse_qs(urlsplit(html.unescape(url)).query).get("utm_source") == ["edm"]
    and parse_qs(urlsplit(html.unescape(url)).query).get("utm_medium") == ["email"]
    and parse_qs(urlsplit(html.unescape(url)).query).get("utm_campaign") == ["ai-daily-" + date]
    for url in urls
)
checks["All story deep-links resolve"] = all(
    urlsplit(html.unescape(url)).fragment in anchors for url in urls[:6]
)
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + " " + name)
if not all(checks.values()):
    raise SystemExit("English team EDM QA FAILED")

