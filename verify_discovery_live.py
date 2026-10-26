#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-deployment proof that historical search and discovery JS are live.

GitHub Pages may serve a previous deploy for a brief period; compare exact bytes
of both artifacts rather than accepting HTTP 200 from an old version.
"""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SITE = "https://carriehw.github.io/ai-marketing-daily/"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def check():
    expected = {}
    for path in ("discovery.js", "archive/search-index.json"):
        b = (BASE / path).read_bytes()
        if not b:
            raise RuntimeError("Missing or empty local generated file: " + path)
        expected[path] = b
    search = json.loads(expected["archive/search-index.json"])
    today = json.loads((BASE / "data.json").read_text(encoding="utf-8"))["date"]
    if search.get("latest_date") != today or search.get("count", 0) < 10:
        raise RuntimeError("Invalid local search index before live validation")

    failures = []
    for attempt in range(1, 6):
        failures = []
        for path, local in expected.items():
            url = SITE + path + "?validation=" + today + "-" + str(attempt)
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Carrie-AI-News-Discovery-Verification/1.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                })
                with urllib.request.urlopen(req, timeout=18) as response:
                    if response.status != 200:
                        raise RuntimeError("HTTP " + str(response.status))
                    live = response.read()
                if sha(live) != sha(local):
                    failures.append(path + ": live bytes differ from built revision")
                else:
                    print("PASS", path, len(live), "bytes and SHA-256 match")
            except Exception as error:
                failures.append(path + ": " + str(error))
        if not failures:
            print("PUBLISHED & VERIFIED discovery assets | %d historic articles | %d issues | %s"%(
                search["count"],search["issue_count"],today))
            return 0
        print("Attempt %d failed: %s"%(attempt,"; ".join(failures)))
        if attempt < 5:
            time.sleep(12)
    print("FAIL live discovery validation: "+ "; ".join(failures),file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(check())
