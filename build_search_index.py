#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a small bilingual search index from all actual published issue archives.

No invented links or archive backfilling. Older layouts without stable article IDs
link to their issue page; new layouts link directly to story anchors.
Run after build_archive.py to include the newest date.
"""
import argparse
import html
import json
import re
from pathlib import Path

def clean(v):
    v=re.sub(r"<[^>]*>", " ", v or "")
    return re.sub(r"\s+", " ", html.unescape(v)).strip()

def lang_text(fragment,lang):
    m=re.search(r'<span\b[^>]*class=["\'][^"\']*\bl-'+lang+r'\b[^"\']*["\'][^>]*>(.*?)</span>',fragment,re.S|re.I)
    return clean(m.group(1)) if m else ""

def extract(doc, date):
    found=[]
    for match in re.finditer(r"<article\b[^>]*>[\s\S]*?</article\s*>",doc,re.I):
        card=match.group(0)
        head=re.search(r"<h3\b[^>]*>(.*?)</h3\s*>",card,re.S|re.I)
        if not head: continue
        inner=head.group(1)
        az=lang_text(inner,"zh") or clean(inner)
        ae=lang_text(inner,"en") or az
        if not az: continue
        ref=re.search(r'<article\b[^>]*\bid=["\']([^"\']+)["\']',card,re.I)
        sid=ref.group(1) if ref else ""
        if sid and not re.fullmatch(r"[a-zA-Z0-9_-]{2,150}",sid):sid=""
        # Summaries vary by historical template; old card uses .sum, newer uses
        # .kh bullets. Take a short extract of the first editorial paragraphs.
        parts=[]
        for p in re.finditer(r"<(?:p|li)\b[^>]*>(.*?)</(?:p|li)\s*>",card,re.I|re.S):
            snippet=p.group(1)
            zz=lang_text(snippet,"zh")
            ee=lang_text(snippet,"en")
            if zz or ee: parts.append((zz,ee))
            if len(parts)>=4:break
        desc_zh=" ".join(p[0] for p in parts if p[0])[:320]
        desc_en=" ".join(p[1] for p in parts if p[1])[:320]
        publisher=re.search(r'<span\b[^>]*class=["\'][^"\']*\bsrc\b[^"\']*["\'][^>]*>(.*?)</span>',card,re.I|re.S)
        src=clean(publisher.group(1)) if publisher else ""
        sig=re.search(r'\bclass=["\'][^"\']*\b(?:signal|chip)\s+(act|watch|impact)\b',card)
        act=sig.group(1) if sig else ""
        section_num=re.findall(r'<section\b[^>]*id=["\']sec(\d+)["\']',doc[:match.start()],re.I)
        sec=int(section_num[-1]) if section_num else None
        # Index only published HTML, no live page or mismatched date guessing.
        found.append({
            "date":date,
            "title_zh":az[:220],
            "title_en":ae[:220],
            "summary_zh":desc_zh,
            "summary_en":desc_en,
            "source":src[:80],
            "section":sec,
            "signal":act,
            "url":date+".html"+("#"+sid if sid else "")
        })
    return found

def build(directory):
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    stories=[];dates=set();missing=[]
    for issue in manifest:
        date=issue.get("date","")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date) or date in dates:
            raise ValueError("Invalid or repeated archive issue date: "+str(date))
        dates.add(date)
        issue_path=directory/(date+".html")
        if not issue_path.is_file():
            missing.append(date);continue
        text=issue_path.read_text(encoding="utf-8")
        stories.extend(extract(text,date))
    if missing: raise ValueError("Archived issue HTML missing: "+", ".join(missing[:10]))
    if not stories: raise ValueError("No archived articles indexed")
    # The index must include the edition that has just been built. Too few news
    # entries means the extractor failed: fail closed instead of shipping fake search.
    current=manifest[0]
    current_count=sum(x["date"]==current["date"] for x in stories)
    if current_count!=current["total"]:
        raise ValueError("Current article indexing mismatch: %d != %d"%(current_count,current["total"]))
    payload={"version":1,"latest_date":current["date"],"issue_count":len(manifest),"count":len(stories),"items":stories}
    path=directory/"search-index.json"
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("PASS archive index: %d articles from %d dated issues; current edition %d; %d bytes"%(
        len(stories),len(manifest),current_count,path.stat().st_size))
    return payload

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dir",default="archive")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        latest='<section id="sec0"><article class="story c1" id="stable-id"><h3><a href="https://example.com/a"><span class="l-zh">標題</span><span class="l-en">English headline</span></a></h3><p><span class="l-zh">說明</span><span class="l-en">Summary</span></p></article></section>'
        older='<article class="card"><h3><a href="https://example.com/b"><span class="l-zh">舊標題</span><span class="l-en">Old headline</span></a></h3><p class="sum"><span class="l-zh">舊說明</span><span class="l-en">Earlier news</span></p></article>'
        x,y=extract(latest,"2026-10-26"),extract(older,"2026-08-01")
        assert len(x)==len(y)==1 and x[0]["url"]=="2026-10-26.html#stable-id"
        assert y[0]["url"]=="2026-08-01.html" and y[0]["title_en"]=="Old headline"
        print("PASS search-index extraction: modern and legacy layouts; safe links")
        return
    build(Path(a.dir))

if __name__=="__main__":
    main()
