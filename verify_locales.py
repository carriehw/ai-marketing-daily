#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed three-locale, multilingual SEO, content parity and source QA gate.

Structural and editorial-risk checks cannot replace external fact checking or an
independent human native-language proofread. Review records state their scope.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

LOCALES={"en":"en","zh-hant":"zh-Hant","zh-hans":"zh-Hans"}
LOCALE_OG={"en":"en_US","zh-hant":"zh_HK","zh-hans":"zh_CN"}

def url_for(base,loc,kind,date):
    return base.rstrip("/")+"/"+loc+"/"+({"home":"","directory":"archive/","issue":"archive/"+date+".html"}[kind])

def expected(page,base,kind,date,locale,count):
    failures=[]
    soup=BeautifulSoup(page,"html.parser")
    page_url=url_for(base,locale,kind,date)
    if not soup.html or soup.html.get("lang")!=LOCALES[locale]:
        failures.append(f"{locale}/{kind}: document lang incorrect")
    canonical=soup.find("link",rel="canonical")
    if not canonical or canonical.get("href")!=page_url:
        failures.append(f"{locale}/{kind}: canonical not self-referential")
    og=soup.find("meta",attrs={"property":"og:url"})
    if not og or og.get("content")!=page_url:
        failures.append(f"{locale}/{kind}: OG url points elsewhere")
    oglang=soup.find("meta",attrs={"property":"og:locale"})
    if oglang and oglang.get("content")!=LOCALE_OG[locale]:
        failures.append(f"{locale}/{kind}: wrong OG locale")
    alternates={x.get("hreflang"):x.get("href")
                for x in soup.select('link[rel="alternate"][hreflang]')}
    for l,code in LOCALES.items():
        if alternates.get(code)!=url_for(base,l,kind,date):
            failures.append(f"{locale}/{kind}: broken reciprocal hreflang {code}")
    if len([v for v in alternates if v in LOCALES.values()])!=3:
        failures.append(f"{locale}/{kind}: expected exactly 3 localizations")
    links=soup.select("nav.locale-links a")
    if len(links)!=3 or len([x for x in links if x.get("aria-current")=="page"])!=1:
        failures.append(f"{locale}/{kind}: language links missing or ambiguous")
    if soup.select(".l-zh,.l-en"):
        failures.append(f"{locale}/{kind}: hidden secondary-language content retained")
    if kind in ("home","issue") and count:
        articles=soup.select("main#main article.story")
        if len(articles)!=count:
            failures.append(f"{locale}/{kind}: article count {len(articles)} != {count}")
        modern=bool(soup.select("#news-explorer"))
        if modern:
            if len(soup.select("main#main article.story details.story-actions"))!=count:
                failures.append(f"{locale}/{kind}: not exactly one share menu per article")
            if soup.select(".story-share,.copy-team-brief"):
                failures.append(f"{locale}/{kind}: old duplicate buttons leaked into cards")
            embedded=soup.find("script",id="news-discovery-data")
            if not embedded:failures.append(f"{locale}/{kind}: no search source JSON")
            else:
                try:
                    cfg=json.loads(embedded.string or "{}")
                    if len(cfg.get("items",[]))!=count:
                        failures.append(f"{locale}/{kind}: search article data mismatch")
                    if cfg.get("edition_base")!=url_for(base,locale,"home",date):
                        failures.append(f"{locale}/{kind}: share URL not pinned to locale")
                    if cfg.get("date")!=date:
                        failures.append(f"{locale}/{kind}: edition date mismatch")
                except Exception:
                    failures.append(f"{locale}/{kind}: malformed search data")
    if locale=="zh-hans":
        if not soup.find("script",src=re.compile(r"discovery-zh-hans\.js$")) and kind in ("home","issue"):
            # Historical editions prior to discovery have no discovery.js.
            if soup.select("#news-explorer"):
                failures.append(f"{locale}/{kind}: search UX script is not localized")
        body=soup.get_text(" ",strip=True)
        if "行销" in body or "行銷" in body:
            failures.append(f"{locale}/{kind}: marketing terminology not localized")
    for entry in links:
        if not entry.get("href","").startswith(base):
            failures.append(f"{locale}/{kind}: bad language navigation link")
    return failures

def audit(root):
    data=json.loads((root/"data.json").read_text(encoding="utf-8"))
    manifest=json.loads((root/"archive/manifest.json").read_text(encoding="utf-8"))
    date=data["date"];base=data["site_url"]
    assert base.startswith("https://")
    review_path=root/"editorial"/"localization_review"/(date+".json")
    if not review_path.is_file():
        return ["No edition-by-edition localization review record: "+str(review_path)], {}
    review=json.loads(review_path.read_text(encoding="utf-8"))
    problems=[]
    if review.get("edition_date")!=date or len(review.get("items",[]))!=len(data["items"]):
        problems.append("Localization review record date or item count mismatch")
    expected_urls={v.get("url") for v in data["items"]}
    reviewed_urls={v.get("url") for v in review.get("items",[])}
    if expected_urls!=reviewed_urls:problems.append("Each editorial claim must have one matching review record")
    for review_item in review.get("items",[]):
        if review_item.get("decision")!="approved_for_ai_assisted_localization" or len(review_item.get("simplified_editorial_note",""))<35:
            problems.append("Incomplete localized semantic risk note for "+str(review_item.get("url")))
    if "human" not in review.get("scope",""):
        problems.append("Review scope must explicitly distinguish AI-assisted vs human proofreading")
    current_count=len(data["items"])
    output_stats={}
    for locale in LOCALES:
        for kind,path in [
            ("home",root/locale/"index.html"),
            ("issue",root/locale/"archive"/(date+".html")),
            ("directory",root/locale/"archive/index.html"),
        ]:
            if not path.is_file():
                problems.append("Missing localization: "+str(path));continue
            text=path.read_text(encoding="utf-8")
            problems.extend(expected(text,base,kind,date,locale,
                                      current_count if kind!="directory" else 0))
        all_dates=set()
        for issue in manifest:
            item=issue["date"]
            path=root/locale/"archive"/(item+".html")
            if not path.is_file():problems.append("Missing historical locale page "+locale+"/"+item)
            else:all_dates.add(item)
        output_stats[locale]={"issues":len(all_dates),
                              "homepage":(root/locale/"index.html").stat().st_size if (root/locale/"index.html").is_file() else 0}
    search=json.loads((root/"archive/search-index.json").read_text(encoding="utf-8"))
    zhsearch=root/"archive/search-index-zh-hans.json"
    if not zhsearch.exists():problems.append("Missing Simplified Chinese historical search index")
    else:
        simplified=json.loads(zhsearch.read_text(encoding="utf-8"))
        if simplified.get("count")!=search.get("count") or simplified.get("latest_date")!=date:
            problems.append("Simplified historical search index stale or incomplete")
        if (len(simplified.get("items",[])) and len(search.get("items",[])) and
            all(a.get("title_zh")==b.get("title_zh") for a,b in zip(simplified["items"],search["items"]))):
            problems.append("Simplified index contains only unconverted Traditional Chinese titles")
    js_path=root/"discovery-zh-hans.js"
    if not js_path.exists() or js_path.stat().st_size<500:
        problems.append("Missing executable localized Simplified discovery script")
    return problems,output_stats

def self_test():
    base="https://example.org/news/"
    src="""<!doctype html><html lang="zh-Hans"><head><link rel="canonical" href="https://example.org/news/zh-hans/">
<meta property="og:url" content="https://example.org/news/zh-hans/"><meta property="og:locale" content="zh_CN">
<link rel="alternate" hreflang="en" href="https://example.org/news/en/">
<link rel="alternate" hreflang="zh-Hant" href="https://example.org/news/zh-hant/">
<link rel="alternate" hreflang="zh-Hans" href="https://example.org/news/zh-hans/"></head>
<body><nav class="locale-links"><a href="https://example.org/news/en/">EN</a>
<a href="https://example.org/news/zh-hant/">繁</a>
<a href="https://example.org/news/zh-hans/" aria-current="page">简</a></nav></body></html>"""
    assert not expected(src,base,"home","2026-10-26","zh-hans",0)
    assert expected(src.replace('hreflang="zh-Hant"','hreflang="wrong"'),
                    base,"home","2026-10-26","zh-hans",0)
    assert expected(src.replace('rel="canonical" href="https://example.org/news/zh-hans/"',
                                'rel="canonical" href="https://example.org/news/"'),
                    base,"home","2026-10-26","zh-hans",0)
    print("PASS multilingual SEO validator positive and negative controls")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:self_test();sys.exit()
    issues,stats=audit(Path(__file__).resolve().parent)
    for i in issues[:40]:print("FAIL",i,file=sys.stderr)
    if issues:sys.exit(1)
    print("PASS multilingual SEO and localized journalism QA:",stats)
