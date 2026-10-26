#!/usr/bin/env python3
"""Post-deploy public-byte validation for three independent locale pages.

A release is not considered verified merely because GitHub Actions passed or a
stale previous deployment returned HTTP 200.
"""
from pathlib import Path
import hashlib
import json
import time
import urllib.request
import sys

ROOT=Path(__file__).resolve().parent
BASE="https://carriehw.github.io/ai-marketing-daily/"
date=json.loads((ROOT/"data.json").read_text(encoding="utf-8"))["date"]

PATHS=[
    "en/index.html","zh-hant/index.html","zh-hans/index.html",
    "en/archive/"+date+".html",
    "zh-hant/archive/"+date+".html",
    "zh-hans/archive/"+date+".html",
    "en/archive/index.html","zh-hant/archive/index.html",
    "zh-hans/archive/index.html",
    "archive/search-index-zh-hans.json",
    "discovery-zh-hans.js","sitemap.xml","robots.txt",
]

def digest(x):return hashlib.sha256(x).digest()

def validate():
    expected={p:(ROOT/p).read_bytes() for p in PATHS}
    for try_no in range(1,6):
        errors=[]
        for p,b in expected.items():
            try:
                req=urllib.request.Request(BASE+p+"?verify="+date+"-"+str(try_no),
                    headers={"Cache-Control":"no-cache",
                             "User-Agent":"AI-Marketing-Daily-LocaleQA/1.0"})
                with urllib.request.urlopen(req,timeout=20) as resp:
                    if resp.status!=200:raise RuntimeError("HTTP "+str(resp.status))
                    fetched=resp.read()
                if digest(fetched)!=digest(b):
                    errors.append(p+": content is from a different build")
            except Exception as err:
                errors.append(p+": "+str(err))
        if not errors:
            print("PUBLISHED & VERIFIED",len(PATHS),
                  "locale/SEO paths; 3 homepages + 3 live archives; edition",date)
            return 0
        print("Locale verification retry",try_no,errors[:4],flush=True)
        if try_no<5:time.sleep(15)
    print("FAIL locale live verification: "+"; ".join(errors),file=sys.stderr)
    return 1

if __name__=="__main__":raise SystemExit(validate())
