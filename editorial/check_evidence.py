#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Marketing Daily: structural editorial evidence gate.

This tool checks that a release contains complete, reviewable evidence records
and bilingual metadata. It CANNOT determine whether an article's claims are true:
a second editor must independently read original sources and validate semantics.
Fail closed for missing/undocumented pivotal claims. Python stdlib only.

Usage:
    python3 editorial/check_evidence.py --data data.json \\
        --evidence editorial/evidence/YYYY-MM-DD.json

Exit 0: evidence packet is complete enough for a human second-pass factual review.
Exit 1: missing or invalid; DO NOT publish.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

SCORES = {
    "direct_marketing_relevance": 30, "business_impact": 25,
    "actionability": 20, "market_relevance": 15, "novelty": 10,
}
ALLOWED = {"verified", "attributed"}
REQUIRED_ZH = ("title", "summary", "source", "url", "time", "section", "why")
REQUIRED_EN = ("title_en", "summary_en", "why_en")


def canonical(url):
    """Normalise benign tracking differences, not substantive paths."""
    try:
        p = urlsplit(url.strip())
        if p.scheme.lower() not in ("http", "https") or not p.netloc:
            return ""
        host = p.netloc.lower().removeprefix("www.")
        path = p.path.rstrip("/") or "/"
        clean = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_")]
        return urlunsplit(("https", host, path, urlencode(clean), ""))
    except Exception:
        return ""


def iso_date(s):
    try:
        return date.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None


def iso_hkt(s):
    try:
        dt = datetime.fromisoformat(str(s))
        return dt if dt.tzinfo and dt.utcoffset() == timedelta(hours=8) else None
    except (ValueError, TypeError):
        return None


def assess(data, evidence):
    problems = []
    def bad(message):
        problems.append(message)

    edition = iso_date(data.get("date"))
    if edition is None:
        bad("data.json date: invalid YYYY-MM-DD")
    if iso_date(evidence.get("edition_date_hkt")) != edition:
        bad("evidence.edition_date_hkt differs from data.json date")
    if not iso_hkt(evidence.get("verified_at_hkt")):
        bad("evidence.verified_at_hkt missing valid +08:00 timestamp")
    if evidence.get("status") not in ("reviewed", "approved"):
        bad("evidence.status must be reviewed or approved")
    if str(evidence.get("schema_version")) != "1.0":
        bad("evidence.schema_version must be 1.0")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        bad("data.json items must be a non-empty list")
        items = []
    sections = data.get("sections") or []
    urls = {}
    for i, article in enumerate(items, 1):
        tag = "article #%d" % i
        for field in REQUIRED_ZH + REQUIRED_EN:
            if not isinstance(article.get(field), str) or not article[field].strip():
                bad("%s missing %s" % (tag, field))
        link = canonical(str(article.get("url") or ""))
        if not link:
            bad("%s has invalid original URL" % tag)
        elif link in urls:
            bad("%s duplicates article #%d URL" % (tag, urls[link]))
        else:
            urls[link] = i
        if article.get("section") not in sections:
            bad("%s has unknown section" % tag)
        if article.get("highlights") and not article.get("highlights_en"):
            bad("%s missing translated highlights" % tag)
        if article.get("followup") and not article.get("followup_en"):
            bad("%s missing translated follow-up" % tag)
        if article.get("pattern") and not article.get("pattern_en"):
            bad("%s missing translated trend analysis" % tag)

    records = evidence.get("stories")
    if not isinstance(records, list):
        bad("evidence.stories must be a list")
        records = []
    covered = set()
    seen_ids = set()
    for k, rec in enumerate(records, 1):
        tag = "evidence story #%d" % k
        sid = rec.get("story_id")
        if not isinstance(sid, str) or not sid.strip():
            bad("%s missing stable story_id" % tag)
        elif sid in seen_ids:
            bad("%s duplicate story_id" % tag)
        else:
            seen_ids.add(sid)
        puburl = canonical(str(rec.get("published_article_url") or ""))
        if not puburl:
            bad("%s missing published_article_url" % tag)
        elif puburl not in urls:
            bad("%s has no matching published article URL" % tag)
        elif puburl in covered:
            bad("%s duplicates evidence for an article" % tag)
        else:
            covered.add(puburl)

        for date_key in ("event_date", "first_published_date"):
            val = iso_date(rec.get(date_key))
            if val is None:
                bad("%s missing/invalid %s" % (tag, date_key))
            elif edition and val > edition + timedelta(days=1):
                bad("%s future %s beyond timezone grace" % (tag, date_key))
        if rec.get("editorial_decision") != "publish":
            bad("%s not editor-approved for publication" % tag)
        if rec.get("needs_human_review") is not False:
            bad("%s human-review hold not cleared" % tag)
        if rec.get("impact") not in ("High", "Medium", "Low"):
            bad("%s impact enum invalid" % tag)
        if rec.get("recommended_response") not in ("Act Now", "Test", "Monitor", "Inform"):
            bad("%s recommended_response enum invalid" % tag)
        scoring = rec.get("editorial_relevance_score") or {}
        total = 0
        for key, maximum in SCORES.items():
            v = scoring.get(key)
            if type(v) is not int or v < 0 or v > maximum:
                bad("%s invalid score %s [0..%d]" % (tag, key, maximum))
            else:
                total += v
        if total < 50 and not rec.get("low_score_override_rationale"):
            bad("%s scored %d, requires low_score_override_rationale" % (tag, total))

        sources = rec.get("source_documents")
        if not isinstance(sources, list) or not sources:
            bad("%s no source documents" % tag)
            sources = []
        known = set()
        readable = 0
        for src in sources:
            u = canonical(str(src.get("url") or ""))
            if not u or src.get("source_class") not in ("A", "B", "C", "D"):
                bad("%s source has invalid URL/class" % tag)
            else:
                known.add(u)
            if src.get("access_state") == "accessible":
                readable += 1
            if not iso_hkt(src.get("accessed_at_hkt")):
                bad("%s source missing HKT accessed_at timestamp" % tag)
        if not readable:
            bad("%s has no accessible original source" % tag)

        claims = rec.get("material_claims")
        if not isinstance(claims, list) or not claims:
            bad("%s missing pivotal claims" % tag)
            claims = []
        for ci, claim in enumerate(claims, 1):
            mark = "%s claim #%d" % (tag, ci)
            if claim.get("status") not in ALLOWED:
                bad("%s not verified/attributed" % mark)
            if claim.get("second_pass_checked") is not True:
                bad("%s has no independent second pass" % mark)
            if not isinstance(claim.get("claim_zh"), str) or len(claim["claim_zh"].strip()) < 6:
                bad("%s missing atomic factual claim" % mark)
            if not isinstance(claim.get("evidence_locator"), str) or len(claim["evidence_locator"].strip()) < 5:
                bad("%s missing evidence locator" % mark)
            if canonical(str(claim.get("support_url") or "")) not in known:
                bad("%s support_url not in source_documents" % mark)
    for url, article_idx in urls.items():
        if url not in covered:
            bad("article #%d has no matched evidence record" % article_idx)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        print("EDITORIAL GATE FAIL: cannot read JSON: %s" % e, file=sys.stderr)
        return 1
    failures = assess(data, evidence)
    if failures:
        print("EDITORIAL GATE FAIL (%d issues):" % len(failures), file=sys.stderr)
        for err in failures:
            print(" - " + err, file=sys.stderr)
        return 1
    print("EDITORIAL EVIDENCE STRUCTURE PASS: %d stories; semantic truth still requires editorial review." %
          len(data["items"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
