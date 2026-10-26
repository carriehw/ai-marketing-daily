#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publication gate for structured editorial evidence. Not an AI truth oracle.

Stops publishing when evidence is absent, mismatched, unattributed, duplicated,
backdated or below the approved quality-first service-level floor.
Supports --self-test with deliberately broken fixtures.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
REQUIRED = ("title","title_en","summary","summary_en","url","time","section","action","region","why","why_en")
BAD_ABSOLUTES = ("廣告識別符一律攔截","所有廣告識別符全面封鎖","所有追蹤手段一律攔截")
SECTIONS = {"AI 大模型 & 市場動態","廣告平台 & 行銷科技","創意生產工具","行業影響 & 品牌案例","即學技巧 & 玩法"}
CLAIM_STATES = {"verified","attributed"}
URL_RE = re.compile(r"^https?://[^\s/]+/.+")

def audit(data, proof, expected_date=None):
    bad=[]
    items=data.get("items",[])
    date=data.get("date","")
    if expected_date and date!=expected_date: bad.append("edition date mismatch")
    try: dt.date.fromisoformat(date)
    except (ValueError, TypeError): bad.append("invalid edition ISO date")
    if proof.get("edition_date_hkt")!=date: bad.append("evidence edition date mismatch")
    target=int(proof.get("coverage_floor",10))
    if target!=10: bad.append("daily service-level floor must be 10")
    if len(items)<10: bad.append("verified full-news count below 10; exception requires human review")
    if len(items)>30: bad.append("suspicious unusually large issue")
    evid=proof.get("stories",[])
    if len(evid)!=len(items): bad.append("evidence/issue item count mismatch")
    urls=set()
    for i,it in enumerate(items):
        n=i+1
        prefix=f"story {n}"
        for key in REQUIRED:
            if not isinstance(it.get(key),str) or not it[key].strip():bad.append(f"{prefix} missing {key}")
        if it.get("section") not in SECTIONS:bad.append(f"{prefix} unknown section")
        url=it.get("url","")
        if not URL_RE.match(url):bad.append(f"{prefix} invalid original article URL")
        normal=url.split("?")[0].rstrip("/").lower()
        if normal in urls:bad.append(f"{prefix} repeated original article URL")
        urls.add(normal)
        if any(x in it.get("title","")+it.get("summary","")+" ".join(it.get("highlights",[])) for x in BAD_ABSOLUTES):bad.append(f"{prefix} known overbroad headline claim")
        try:
            mt=re.fullmatch(r"(\d{1,2})月(\d{1,2})日",it.get("time",""))
            if not mt:raise ValueError()
            pubdate=dt.date(int(date[:4]),int(mt[1]),int(mt[2]))
            eddate=dt.date.fromisoformat(date)
            if pubdate>eddate:bad.append(f"{prefix} source publication after edition date")
        except (ValueError, TypeError):bad.append(f"{prefix} invalid source publication date")
        if len(it.get("highlights",[]))<2 or len(it.get("highlights_en",[]))<2:
            bad.append(f"{prefix} missing bilingual highlights")
        if len(it.get("detail","").strip())<120 or len(it.get("detail_en","").strip())<120:
            bad.append(f"{prefix} missing meaningful bilingual detailed content")
        if i>=len(evid):continue
        e=evid[i]
        if e.get("title_zh")!=it.get("title"):bad.append(f"{prefix} proof title does not match content")
        if e.get("source_story_url")!=url:bad.append(f"{prefix} proof article link mismatch")
        if e.get("source_date_display")!=it.get("time"):bad.append(f"{prefix} proof date mismatch")
        if e.get("editorial_decision")!="approved" or e.get("needs_human_review") is not False:
            bad.append(f"{prefix} unresolved editorial decision")
        # Editorial relevance ranking is separate from source verification.
        score=e.get("editorial_relevance_score",{})
        dimensions={"direct_marketing_relevance":30,"business_impact":25,
                    "actionability":20,"market_relevance":15,"novelty":10}
        if not isinstance(score,dict):
            bad.append(f"{prefix} editorial scoring record missing")
        else:
            valid_score=True
            subtotal=0
            for dim,cap in dimensions.items():
                value=score.get(dim)
                if type(value) is not int or not 0<=value<=cap:
                    valid_score=False
                    bad.append(f"{prefix} invalid editorial score: {dim}")
                else:
                    subtotal+=value
            if valid_score:
                if score.get("total")!=subtotal:
                    bad.append(f"{prefix} editorial score arithmetic mismatch")
                if subtotal<50:
                    bad.append(f"{prefix} low marketer relevance: {subtotal}/100")

        docs=e.get("source_documents",[])
        if not docs:bad.append(f"{prefix} source documents absent")
        support_urls={d.get("url") for d in docs}
        if it.get("verification_url") and it.get("verification_url") not in support_urls:
            bad.append(f"{prefix} public verification URL not in evidence record")
        for doc in docs:
            if not URL_RE.match(doc.get("url","")):bad.append(f"{prefix} invalid supporting source URL")
            if doc.get("source_class") not in {"A","B","C"}:bad.append(f"{prefix} unsupported source class")
            if len(doc.get("evidence_locator","").strip())<12:bad.append(f"{prefix} missing evidence locator")
            if len(doc.get("limitations","").strip())<12:bad.append(f"{prefix} missing source limitations")
        claims=e.get("claims",[])
        if len(claims)<3:bad.append(f"{prefix} fewer than 3 separately documented editorial claims")
        for c in claims:
            if c.get("support_url") not in support_urls:bad.append(f"{prefix} claim refers to unlisted evidence")
            if c.get("status") not in CLAIM_STATES:bad.append(f"{prefix} unresolved/unsafe claim")
            if not c.get("evidence_locator") or len(str(c["evidence_locator"]))<10:
                bad.append(f"{prefix} claim lacks evidence locator")
        if not e.get("reviewed_by") or not e.get("independent_review"):
            bad.append(f"{prefix} no review provenance")
    if proof.get("release_status") not in {"pending_live_validation","published_verified"}:
        bad.append("invalid release status")
    return bad

def self_test():
    item={x:"x" for x in REQUIRED}
    item.update({"url":"https://example.com/story","time":"10月25日","section":"創意生產工具","title":"題目","title_en":"Title","highlights":["a","b"],"highlights_en":["a","b"],"detail":"a"*130,"detail_en":"a"*130})
    data={"date":"2026-10-26","items":[dict(item,url=f"https://example.com/story-{i}",title=f"題目{i}") for i in range(10)]}
    proof={"edition_date_hkt":"2026-10-26","coverage_floor":10,"release_status":"pending_live_validation","stories":[]}
    for it in data["items"]:
        u="https://example.com/source"
        proof["stories"].append({"title_zh":it["title"],"source_story_url":it["url"],"source_date_display":it["time"],"editorial_decision":"approved","needs_human_review":False,"editorial_relevance_score":{"direct_marketing_relevance":20,"business_impact":20,"actionability":16,"market_relevance":12,"novelty":8,"total":76},"reviewed_by":"second pass","independent_review":"reopened source","source_documents":[{"url":u,"source_class":"B","evidence_locator":"example original reporting exact section","limitations":"example method not universal"}],"claims":[{"claim_zh":"a","support_url":u,"evidence_locator":"exact source evidence","status":"attributed"}]*3})
    def passes(d,p):return len(audit(d,p,"2026-10-26"))==0
    if not passes(data,proof):return False,"valid control rejected"
    if passes(data,{**proof,"stories":proof["stories"][:-1]}):return False,"missing evidence not rejected"
    if passes({**data,"items":data["items"][:8]},proof):return False,"undersupply not rejected"
    broken=json.loads(json.dumps(proof));broken["stories"][0]["claims"][0]["status"]="rejected"
    if passes(data,broken):return False,"rejected claim not rejected"
    changed=json.loads(json.dumps(data));changed["items"][1]["title"]="unsourced edit"
    if passes(changed,proof):return False,"mismatched headline not rejected"
    return True,"positive and 4 negative controls passed"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="data.json")
    p.add_argument("--evidence")
    p.add_argument("--today")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        ok,msg=self_test()
        print(("PASS " if ok else "FAIL ")+msg)
        return 0 if ok else 1
    data=json.loads(Path(a.data).read_text(encoding="utf-8"))
    evpath=Path(a.evidence or f"editorial/evidence/{data.get('date','')}.json")
    if not evpath.is_file():
        print(f"FAIL missing evidence file {evpath}")
        return 1
    proof=json.loads(evpath.read_text(encoding="utf-8"))
    errors=audit(data,proof,a.today)
    for err in errors:print("FAIL",err)
    if errors:
        print(f"FAIL {len(errors)} problems; cannot build or publish")
        return 1
    print(f"PASS {len(data['items'])} stories passed structural/source-record checks; human source reading remains mandatory")
    return 0

if __name__=="__main__":sys.exit(main())
