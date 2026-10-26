#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quality gate for Reader-first homepage without dropping news or source evidence.

Controls must be interactive in generated DOM. This is a structural test,
not a claim of mobile-browser screenshot or real-device validation.
"""
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

root=Path(__file__).resolve().parent
data=json.loads((root/"data.json").read_text(encoding="utf-8"))
issues=[]
n=len(data["items"])
for language in ("en","zh-hant","zh-hans"):
    for kind,path in (("home",root/language/"index.html"),
                      ("current archive",root/language/"archive"/(data["date"]+".html"))):
        if not path.is_file():
            issues.append(f"{language}/{kind}: missing page")
            continue
        html=path.read_text(encoding="utf-8")
        soup=BeautifulSoup(html,"html.parser")
        label=f"{language}/{kind}"
        hero=soup.select_one("header.hero .hero-feature-grid")
        if not hero or not hero.select_one(".hero-intro") or not hero.select_one(".top-stories"):
            issues.append(f"{label}: responsive first-screen grid or top news absent")
        if len(soup.select(".top-stories .lead-row"))!=3:
            issues.append(f"{label}: missing editorially ranked top 3")
        if not soup.select_one(".top-search[href='#news-explorer']"):
            issues.append(f"{label}: search is not discoverable in top navigation")
        nav=soup.select_one(".mobile-category-menu .mobile-cat-list")
        if not nav or len(nav.select("a[href^='#sec']"))<1:
            issues.append(f"{label}: accessible category menu missing")
        if soup.select(".hero .stats, .hero .legend"):
            issues.append(f"{label}: old duplicate hero furniture still visible")
        notes=soup.select_one(".edition-notes")
        if not notes or notes.has_attr("open"):
            issues.append(f"{label}: editorial context not hidden behind optional disclosure")
        if not soup.select_one("#news-explorer") or not soup.select_one("#news-reading-mode"):
            issues.append(f"{label}: discovery or reading controls not found")
        if not soup.select_one('#view-quick[aria-pressed="true"]'):
            issues.append(f"{label}: Quick Scan should be active by default")
        if not soup.select_one('#view-deep[aria-pressed="false"]'):
            issues.append(f"{label}: Deep Read missing")
        articles=soup.select("main#main article.story")
        if len(articles)!=n:
            issues.append(f"{label}: story count {len(articles)} != {n}")
        for i,article in enumerate(articles):
            if not article.get("id"):issues.append(f"{label}: missing permanent story id at {i}")
            summary=article.select_one(":scope > .scan-brief .scan-summary")
            impact=article.select_one(":scope > .scan-brief .scan-impact")
            if not summary or not summary.get_text(" ",strip=True):
                issues.append(f"{label}: no Quick Scan summary at story {i}")
            if not impact or not impact.get_text(" ",strip=True):
                issues.append(f"{label}: no marketer impact in Quick Scan story {i}")
            expander=article.select_one(":scope > details.story-expanded")
            if not expander or expander.has_attr("open"):
                issues.append(f"{label}: per-story Deep Read not collapsed initially {i}")
            elif not expander.select_one(".block") or not expander.select_one(".take"):
                issues.append(f"{label}: published key points/insight not preserved {i}")
            if len(article.select(".story-foot details.story-actions"))!=1:
                issues.append(f"{label}: share/copy controls lost {i}")
            if not article.select_one(".story-foot .readsrc[href^='https://']"):
                issues.append(f"{label}: original source link lost {i}")
        css="\n".join(x.get_text() for x in soup.select("style"))
        needed=(".hero-feature-grid{display:grid", ".scan-brief{display:grid",
                ".story-expanded>summary{", ".reading-toolbar{display:flex",
                ".top-search{display:inline-flex", "@media(max-width:560px)",
                ".navlinks{display:none!important")
        for x in needed:
            if x not in css: issues.append(f"{label}: reader CSS rule absent: {x}")
        if "sessionStorage.setItem('amd-reader-mode'" not in html:
            issues.append(f"{label}: Quick/Deep preference not wired")
        if "details.story-expanded" not in html:
            issues.append(f"{label}: JS does not handle expanded stories")
if issues:
    for p in issues[:35]:print("FAIL",p,file=sys.stderr)
    raise SystemExit(1)
print(f"PASS Reader-first UI QA: {n} complete articles, ranked Top 3, compact menu/search, optional editorial context, Quick/Deep modes across 3 language homepages and dated archives")
