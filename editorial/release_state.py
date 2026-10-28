#!/usr/bin/env python3
"""Plan publication and record the shared receipt only after live acceptance.

No email or social actions. Evidence bytes remain immutable so the newsletter's
data/evidence digests stay valid. Old task-chat HELD results are not a release gate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editorial.edition_packet import current_packet, read_json, validate, write_json

SITE = "https://carriehw.github.io/ai-marketing-daily/"


def sha(value):
    return hashlib.sha256(value).hexdigest()


class StoryCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "article" and "story" in dict(attrs).get("class", "").split():
            self.count += 1


def fetch(path):
    req = urllib.request.Request(SITE + path + "?release_acceptance=" + str(time.time_ns()),
                                 headers={"Cache-Control": "no-cache", "User-Agent": "AI-Marketing-Daily-Release/2"})
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise ValueError("not HTTP 200: " + path)
        return response.read()


def asset_paths(date):
    paths = ["index.html", "data.json", f"archive/{date}.html", "archive/manifest.json",
             "archive/search-index.json", "archive/search-index-zh-hans.json",
             "discovery.js", "discovery-zh-hans.js", "sitemap.xml", "robots.txt",
             f"og/{date}.jpg", f"editorial/evidence/{date}.json",
             "edm/team.html", "edm/payload.json", "edm/payload-feed.xml", "edm/feed.xml"]
    for locale in ("en", "zh-hant", "zh-hans"):
        paths += [f"{locale}/index.html", f"{locale}/archive/{date}.html", f"{locale}/archive/index.html"]
    return paths


def observe(paths, fetcher=fetch):
    def one(path):
        try:
            body = fetcher(path)
            result = {"sha256": sha(body)}
            if path.endswith(".html"):
                counter = StoryCounter()
                counter.feed(body.decode("utf-8"))
                result["article_count"] = counter.count
            if path == "edm/payload.json":
                payload = json.loads(body)
                result["payload"] = {k: payload.get(k) for k in
                    ("edition_date", "headline_count", "verification_status", "data_sha256", "evidence_sha256", "edition_id")}
            return path, result
        except Exception as error:
            return path, {"error": str(error)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(one, paths))


def observe_until_matching(expected, fetcher=fetch, attempts=3, pause=None):
    """Retry only unmatched assets; every final digest must still match exactly."""
    pause = pause or time.sleep
    observed = observe(expected, fetcher)
    for attempt in range(1, attempts):
        pending = {path: digest for path, digest in expected.items()
                   if observed[path].get("sha256") != digest}
        if not pending:
            break
        for path, digest in pending.items():
            detail = observed[path].get("error") or ("received sha256=" + str(observed[path].get("sha256")))
            print(f"Live asset retry {attempt}/{attempts - 1}: {path}; expected sha256={digest}; {detail}", flush=True)
        pause(5 * attempt)
        observed.update(observe(pending, fetcher))
    return observed


def receipt_errors(receipt, data, evidence_bytes, workflow_conclusion="success"):
    errors = []
    if receipt.get("status") != "PUBLISHED & VERIFIED" or receipt.get("edition_date_hkt") != data.get("date"):
        errors.append("matching dated PUBLISHED & VERIFIED receipt absent")
    if receipt.get("published_story_count") != len(data.get("items", [])) or len(data.get("items", [])) < 10:
        errors.append("published count mismatch or below 10")
    # Serialize the data in the renderer's canonical format; packet compilation
    # uses the same exact representation, without changing evidence after release.
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if receipt.get("data_sha256") != sha(encoded) or receipt.get("deployed_evidence_sha256") != sha(evidence_bytes):
        errors.append("receipt is for different data/evidence bytes")
    if workflow_conclusion != "success":
        errors.append("matching publication workflow has not succeeded")
    return errors


def plan(root, today, candidate_only=False, fetcher=fetch):
    root = Path(root)
    packet = current_packet(root)
    errors = validate(packet, today)
    if errors:
        raise ValueError("publication held: " + "; ".join(errors))
    expected = {path: sha((root / path).read_bytes()) for path in asset_paths(today)}
    result = {"edition_date_hkt": today, "expected_asset_sha256": expected,
              "deployment_required": not candidate_only,
              "action": "CANDIDATE_CHECKED" if candidate_only else "DEPLOY_VERIFIED_CANDIDATE"}
    previous = root / "editorial/releases" / (today + ".json")
    if not candidate_only and previous.is_file():
        receipt = read_json(previous)
        proof_bytes = (root / f"editorial/evidence/{today}.json").read_bytes()
        if not receipt_errors(receipt, packet["data"], proof_bytes):
            observed = observe_until_matching(expected, fetcher)
            if all(observed[p].get("sha256") == digest for p, digest in expected.items()):
                result.update(action="AUDIT_ALREADY_CURRENT", deployment_required=False)
    return result


def make_receipt(root, release_plan, observed, source_commit, artifact_commit, workflow_run):
    root = Path(root)
    date = release_plan["edition_date_hkt"]
    packet = current_packet(root)
    if validate(packet, date):
        raise ValueError("the approved edition changed during acceptance")
    for path, expected in release_plan["expected_asset_sha256"].items():
        if observed.get(path, {}).get("sha256") != expected:
            detail = observed.get(path, {}).get("error") or ("received sha256=" + str(observed.get(path, {}).get("sha256")))
            raise ValueError(f"live acceptance failed for {path}; expected sha256={expected}; {detail}")
    count = len(packet["data"]["items"])
    counts = {locale: observed[f"{locale}/index.html"].get("article_count") for locale in ("en", "zh-hant", "zh-hans")}
    if any(value != count for value in counts.values()):
        raise ValueError("actual live article count differs by language")
    payload = observed["edm/payload.json"].get("payload", {})
    data_hash = sha((root / "data.json").read_bytes())
    proof_hash = sha((root / f"editorial/evidence/{date}.json").read_bytes())
    if (payload.get("edition_date") != date or payload.get("headline_count") != count or
            payload.get("verification_status") != "editorial_approved" or
            payload.get("data_sha256") != data_hash or payload.get("evidence_sha256") != proof_hash):
        raise ValueError("live newsletter is not the same approved data/evidence snapshot")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or not re.fullmatch(r"[0-9a-f]{40}", artifact_commit):
        raise ValueError("invalid source/artifact commit provenance")
    if not re.fullmatch(r"https://github.com/carriehw/ai-marketing-daily/actions/runs/\d+", workflow_run):
        raise ValueError("invalid workflow provenance")
    previous_path = root / f"editorial/releases/{date}.json"
    previous = read_json(previous_path) if previous_path.is_file() else {}
    now = datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(timespec="seconds")
    return {"release_schema_version": "2.0", "edition_date_hkt": date,
            "status": "PUBLISHED & VERIFIED", "published_story_count": count,
            "language_article_counts": counts, "verified_at_hkt": now,
            "published_at_hkt": previous.get("published_at_hkt") or previous.get("verified_at_hkt") or now,
            "acceptance_action": release_plan["action"], "source_commit": source_commit,
            "deployed_artifact_commit": artifact_commit if release_plan["deployment_required"] else previous.get("deployed_artifact_commit", artifact_commit),
            "workflow_run": workflow_run, "data_sha256": data_hash, "deployed_evidence_sha256": proof_hash,
            "verified_asset_sha256": release_plan["expected_asset_sha256"],
            "live_url": SITE + "zh-hant/", "archive_url": SITE + f"zh-hant/archive/{date}.html",
            "verification": {"live_bytes": True, "actual_language_article_counts": True, "newsletter_snapshot": True},
            "newsletter_sent_by_this_run": False, "social_posted_by_this_run": False,
            "review_scope": packet["evidence"].get("audit_status", "Source review provenance is in the immutable evidence snapshot.")}


def accept(root, release_plan, source_commit, artifact_commit, workflow_run, fetcher=fetch):
    root = Path(root)
    date = release_plan["edition_date_hkt"]
    # Keep all existing real production gates. A caller cannot manufacture a
    # receipt by passing a boolean saying that another task succeeded.
    for attempt in range(6):
        result = subprocess.run([sys.executable, "verify_live.py", "--today", date, "--dir", "."], cwd=root)
        if result.returncode == 0:
            break
        if attempt == 5:
            raise ValueError("existing production edition gate failed")
        time.sleep(20)
    for script in ("verify_discovery_live.py", "verify_locales_live.py"):
        subprocess.run([sys.executable, script], cwd=root, check=True)
    observed = observe_until_matching(release_plan["expected_asset_sha256"], fetcher)
    receipt = make_receipt(root, release_plan, observed, source_commit, artifact_commit, workflow_run)
    write_json(root / f"editorial/releases/{date}.json", receipt)
    write_json(root / "editorial/releases/latest.json", receipt)
    queue_path = root / f"editorial/queues/{date}.json"
    if queue_path.is_file():
        queue = read_json(queue_path)
        queue.update(stage="PUBLISHED & VERIFIED", published_story_count=receipt["published_story_count"],
                     release_record=f"editorial/releases/{date}.json", verified_at_hkt=receipt["verified_at_hkt"])
        write_json(queue_path, queue)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "accept"])
    parser.add_argument("--today", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--plan", type=Path, default=Path(".publication-plan.json"))
    parser.add_argument("--candidate-only", action="store_true")
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--artifact-commit")
    parser.add_argument("--workflow-run")
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.root, args.today, args.candidate_only)
        write_json(args.plan, result)
        if args.outputs:
            with args.outputs.open("a") as handle:
                handle.write("deployment_required=" + str(result["deployment_required"]).lower() + "\n")
                handle.write("action=" + result["action"] + "\n")
        print(result["action"] + ": " + args.today)
    else:
        result = accept(args.root, read_json(args.plan), args.source_commit, args.artifact_commit, args.workflow_run)
        print("PUBLISHED & VERIFIED shared receipt: " + result["edition_date_hkt"])


if __name__ == "__main__":
    main()
