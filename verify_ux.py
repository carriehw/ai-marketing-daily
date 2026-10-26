#!/usr/bin/env python3
"""Release guard for the phase-one reader experience.

Checks that generated controls are real, accessible links are anchored correctly,
and sharing uses language-specific URLs and permanent story archives. Does not
pretend to replace actual mobile-device interaction or visual tests.
"""
import argparse
import html
import json
import re
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.articles = []
        self.leads = []
        self.share_buttons = []
        self.category_links = []
        self.kind_labels = 0
        self.in_mobile = 0
        self.has_mobile_menu = False
        self.in_top = 0
        self.has_top = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        klass = set(a.get("class", "").split())
        if a.get("id"):
            self.ids.add(a["id"])
        if "mobile-category-menu" in klass:
            self.in_mobile += 1
            self.has_mobile_menu = True
        if "top-stories" in klass:
            self.in_top += 1
            self.has_top = True
        if tag == "article" and "story" in klass:
            self.articles.append(a.get("id", ""))
        if tag == "a" and "lead-row" in klass:
            self.leads.append(a.get("href", ""))
        if tag == "button" and "story-share" in klass:
            self.share_buttons.append(a)
        if tag == "span" and "source-kind" in klass:
            self.kind_labels += 1
        if self.in_mobile and tag == "a" and a.get("href", "").startswith("#sec"):
            self.category_links.append(a.get("href"))

    def handle_endtag(self, tag):
        if tag == "details" and self.in_mobile:
            self.in_mobile -= 1
        if tag == "section" and self.in_top:
            self.in_top -= 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--html", default="index.html")
    p.add_argument("--data", default="data.json")
    args = p.parse_args()
    content = Path(args.html).read_text(encoding="utf-8")
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    inv = Inventory()
    inv.feed(content)
    failures = []
    n = len(data["items"])
    if not inv.has_top or len(inv.leads) != min(3, n):
        failures.append("top three digest missing or wrong size")
    for href in inv.leads:
        if href.lstrip("#") not in inv.articles:
            failures.append("top story link has no matching article")
    if len(inv.articles) != n:
        failures.append(f"article count mismatch: {len(inv.articles)} != {n}")
    if len(inv.share_buttons) != n:
        failures.append(f"share button count mismatch: {len(inv.share_buttons)} != {n}")
    if inv.kind_labels != n:
        failures.append("missing source-kind labels")
    for b in inv.share_buttons:
        if b.get("data-story", "") not in inv.articles:
            failures.append("share button points to non-existent article")
        if not b.get("data-title-zh") or not b.get("data-title-en"):
            failures.append("share button missing bilingual title")
    expected_sections = [f"#sec{i}" for i, section in enumerate(data["sections"])
                         if any(story["section"] == section for story in data["items"])]
    if not inv.has_mobile_menu or inv.category_links != expected_sections:
        failures.append("mobile menu does not link to each populated section")
    if "每則附一手來源" in content:
        failures.append("misleading every-story-primary-source claim survived")
    if "每則附可查核資料來源" not in content:
        failures.append("traceable-source promise not displayed")
    js_markers = ("function languageShareUrl(storyId)",
                  "searchParams.set('lang',curLang())",
                  "'archive/'+ISSUE_DATE+'.html'",
                  "document.querySelectorAll('.story-share')",
                  "mobileCategories.open=false")
    for marker in js_markers:
        if marker not in content:
            failures.append("missing working interaction: " + marker)
    if ".mobile-category-menu{display:block}" not in content:
        failures.append("mobile category control not visible in mobile stylesheet")

    # Check syntax of browser scripts with Node if installed, not raw HTML comments.
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", content, re.S)
    for index, (attrs, script) in enumerate(scripts):
        if "application/json" in attrs or "application/ld+json" in attrs:
            continue
        if not script.strip():
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "page.js"
                path.write_text(script, encoding="utf-8")
                r = subprocess.run(["node", "--check", str(path)],
                                   capture_output=True, text=True, timeout=20)
                if r.returncode:
                    failures.append(f"inline JavaScript block {index} is invalid: {r.stderr[-500:]}")
        except FileNotFoundError:
            print("NOTE node not installed, skipping script syntax check")
            break
    if failures:
        for fail in failures:
            print("FAIL", fail)
        return 1
    print(f"PASS phase-one UX guard: {n} articles, 3 ranked leads, {len(inv.category_links)} mobile categories, bilingual permanent share URLs and JS syntax.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
