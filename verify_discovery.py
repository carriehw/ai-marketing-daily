#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks phase-two search index, reader controls and copyable story payload."""
import json
import re
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent

def check_index(index, data, manifest):
    failures=[]
    items=index.get("items",[])
    if index.get("version")!=1:failures.append("index version missing")
    if index.get("count")!=len(items):failures.append("index count mismatch")
    if index.get("latest_date")!=data.get("date"):failures.append("index date stale")
    if index.get("issue_count")!=len(manifest):failures.append("archive issue count mismatch")
    latest=sum(x.get("date")==data.get("date") for x in items)
    if latest!=len(data.get("items",[])):failures.append("latest edition not fully indexed")
    if len(items)<len(data.get("items",[])):failures.append("historical index unexpectedly small")
    invalid=[]
    for i, item in enumerate(items):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html(?:#[a-zA-Z0-9_-]+)?",item.get("url","")):
            invalid.append(i)
        if not item.get("title_zh") and not item.get("title_en"):
            invalid.append(i)
    if invalid:failures.append("index has invalid links or empty titles")
    dates={x.get("date") for x in items}
    covered=len(dates)
    # Historical archives have used multiple markup generations. An archive
    # may hold unindexed old stories, but an ENTIRE missing issue should fail.
    for issue in manifest:
        if issue.get("total",0)>0 and issue.get("date") not in dates:
            failures.append("entire historical issue missing from index: "+str(issue.get("date")))
            if len(failures)>10:break
    return failures

def audit(root):
    data=json.loads((root/"data.json").read_text(encoding="utf-8"))
    index=json.loads((root/"archive/search-index.json").read_text(encoding="utf-8"))
    manifest=json.loads((root/"archive/manifest.json").read_text(encoding="utf-8"))
    html=(root/"index.html").read_text(encoding="utf-8")
    js=(root/"discovery.js").read_text(encoding="utf-8")
    errors=check_index(index,data,manifest)
    m=re.search(r'<script type="application/json" id="news-discovery-data">(.*?)</script>',html,re.S)
    if not m:errors.append("embedded discovery JSON missing")
    else:
        payload=json.loads(m.group(1))
        if payload.get("date")!=data.get("date") or len(payload.get("items",[]))!=len(data["items"]):
            errors.append("embedded story payload date/count mismatch")
        if len({x.get("id") for x in payload.get("items",[])})!=len(payload.get("items",[])):
            errors.append("duplicate discovery story IDs")
        for item in payload.get("items",[]):
            if ('id="'+item.get("id","")+'"') not in html:errors.append("missing DOM story link")
            if not item.get("summary") or not item.get("why"):errors.append("brief lacks a factual summary/insight")
            if not item.get("url","").startswith("https://"):errors.append("missing original source")
        if "data-site" in m.group(1):errors.append("unexpected executable HTML in data")
    for marker in ('id="news-query"','id="scope-today"','id="scope-archive"',
                   'id="news-section"','id="news-signal"','id="news-status"',
                   'id="archive-result-list"','id="news-reset"',
                   'id="brief-manual"','id="brief-manual-text"'):
        if marker not in html:errors.append("missing reader control "+marker)
    for marker in ("fetch(new URL(searchPath",
                   "document.querySelectorAll('.story-actions')",
                   "formatTeamBrief", "function archiveRows()", "input.addEventListener('input'"):
        if marker not in js:errors.append("missing wired user action "+marker)
    count=html.count('class="story-actions"')
    if count!=len(data["items"]):errors.append("share/copy menus missing or duplicated")
    return errors,index,payload if m else {}

def self_test():
    mini={"version":1,"latest_date":"2026-10-26","issue_count":1,"count":1,
          "items":[{"date":"2026-10-26","title_zh":"測試新聞","url":"2026-10-26.html#an-article"}]}
    data={"date":"2026-10-26","items":[1]}
    manifest=[{"date":"2026-10-26","total":1}]
    if check_index(mini,data,manifest):raise AssertionError("correct fixture was rejected")
    bad=json.loads(json.dumps(mini));bad["items"][0]["url"]="https://evil.example/phishing"
    if not check_index(bad,data,manifest):raise AssertionError("unsafe path was not rejected")
    bad=json.loads(json.dumps(mini));bad["latest_date"]="2026-10-25"
    if not check_index(bad,data,manifest):raise AssertionError("stale index was not rejected")
    print("PASS discovery validator: positive and two negative controls")

if __name__=="__main__":
    if "--self-test" in sys.argv:
        self_test();sys.exit(0)
    failures,index,_=audit(BASE)
    for item in failures:print("FAIL",item)
    if failures:sys.exit(1)
    print("PASS discovery: %d searchable historical articles from %d issues; latest %s, bilingual briefs and wired search controls"%(
        index["count"],index["issue_count"],index["latest_date"]))
