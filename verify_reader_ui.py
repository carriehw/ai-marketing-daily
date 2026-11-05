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
        if not soup.select_one("#news-explorer"):
            issues.append(f"{label}: discovery not found")
        main=soup.select_one("main#main")
        direct=[child for child in main.children if getattr(child,"name",None)]
        news=[child for child in direct if child.name=="section" and (child.get("id","").startswith("sec"))]
        search=soup.select_one("main#main > section#news-explorer")
        if not search or not news or direct.index(search)<=max(direct.index(child) for child in news):
            issues.append(f"{label}: news must appear before search")
        if not soup.select_one("#today-search-results #today-result-list"):
            issues.append(f"{label}: no in-place today's search results")
        if not soup.select_one("#archive-search-results #archive-result-list"):
            issues.append(f"{label}: archive search results missing")
        if soup.select('#view-quick, #view-deep, #news-reading-mode, details.story-expanded'):
            issues.append(f"{label}: obsolete reading controls remain")
        articles=soup.select("main#main article.story")
        if len(articles)!=n:
            issues.append(f"{label}: story count {len(articles)} != {n}")
        for i,article in enumerate(articles):
            if not article.get("id"):issues.append(f"{label}: missing permanent story id at {i}")
            content=article.select_one(":scope > .story-expanded-body")
            if not content or not content.select_one(".block") or not content.select_one(".take"):
                issues.append(f"{label}: published key points/insight not visible {i}")
            if article.select('.story-meta .no'):
                issues.append(f"{label}: redundant story number {i}")
            if not article.select_one('.source-date .src') or not article.select_one('.source-date .date'):
                issues.append(f"{label}: publisher/date grouping missing {i}")
            if not article.select_one('.story-taxonomy .source-kind'):
                issues.append(f"{label}: reporting type missing {i}")
            for detail in article.select('details.detail'):
                if detail.has_attr('open'):issues.append(f"{label}: supplemental context must start collapsed {i}")
            if len(article.select(".story-foot details.story-actions"))!=1:
                issues.append(f"{label}: share/copy controls lost {i}")
            if len(article.select(".story-foot .readsrc[href^='https://']"))!=1:
                issues.append(f"{label}: original source link lost {i}")
            if article.select(".story-foot .evidence-link,.story-foot .signal,.story-foot .chip"):
                issues.append(f"{label}: redundant footer metadata or evidence still renders as CTA {i}")
            if len(article.select(".story-taxonomy .signal, .story-taxonomy .region"))!=2:
                issues.append(f"{label}: classification tags missing from story context {i}")
            if len(article.select(".story-foot > a, .story-foot > details"))!=2:
                issues.append(f"{label}: footer must contain only two direct actions {i}")
            if article.select_one(".evidence-link") and not article.select_one(".story-meta .evidence-link"):
                issues.append(f"{label}: supporting-source link not adjacent to publisher {i}")
        css="\n".join(x.get_text() for x in soup.select("style"))
        needed=(".hero-feature-grid{display:grid", ".source-date{display:flex",
                ".story-expanded-body{",
                ".top-search{display:inline-flex", "@media(max-width:560px)",
                ".navlinks{display:none!important")
        for x in needed:
            if x not in css: issues.append(f"{label}: reader CSS rule absent: {x}")
if issues:
    for p in issues[:35]:print("FAIL",p,file=sys.stderr)
    raise SystemExit(1)
print(f"PASS Reader-first UI QA: {n} complete articles, ranked Top 3, compact menu/search, optional editorial context, single full reading view with optional supplemental context across 3 language homepages and dated archives")
