#!/usr/bin/env python3
"""One reviewed edition input; never infer approval from a draft or a score.

The editor may submit this JSON through GitHub without a local Python runtime.
CI validates it before materializing the three existing renderer inputs.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editorial.check_evidence import assess
from verify_editorial import audit


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def story_errors(article, proof, localization, edition):
    """Precheck one actual review before it enters the approved queue."""
    errors = assess(
        {"date": edition, "sections": [article.get("section")], "items": [article]},
        {"schema_version": "1.0", "edition_date_hkt": edition, "status": "reviewed",
         "verified_at_hkt": proof.get("reviewed_at_hkt") or
             next((s.get("accessed_at_hkt") for s in proof.get("source_documents", [])), None),
         "stories": [proof]})
    for field in ("reviewed_by", "independent_review"):
        if not proof.get(field):
            errors.append("missing actual review provenance: " + field)
    if len(proof.get("claims", [])) < 3:
        errors.append("at least three separately documented pivotal claims required")
    if proof.get("title_zh") != article.get("title") or proof.get("source_story_url") != article.get("url"):
        errors.append("article and evidence identity/title mismatch")
    if proof.get("source_date_display") != article.get("time"):
        errors.append("article and evidence source-date mismatch")
    if proof.get("editorial_relevance_score", {}).get("total", 0) < 60:
        errors.append("selected article is below the 60-point processing threshold")
    if article.get("action") not in {"影響生意", "可即用", "要留意"}:
        errors.append("invalid website action enum; put the recommendation in next_step")
    if article.get("region") not in {"國際", "中國", "香港"}:
        errors.append("invalid website region enum")
    if (localization.get("url") != article.get("url") or
            localization.get("title_zh_hant") != article.get("title") or
            localization.get("decision") != "approved_for_ai_assisted_localization" or
            len(localization.get("simplified_editorial_note", "")) < 35):
        errors.append("missing matching, reviewed localization and risk note")
    return errors


def validate(packet, today):
    errors = []
    if packet.get("packet_version") != "1.0":
        errors.append("unsupported edition packet version")
    if packet.get("status") != "editorial_approved":
        errors.append("only an actually editorial-approved packet may enter publication")
    if packet.get("edition_date_hkt") != today:
        errors.append("packet is not for the requested Hong Kong edition")
    data, proof, review = (packet.get(k) or {} for k in ("data", "evidence", "localization_review"))
    errors += audit(data, proof, today)
    errors += assess(data, proof)
    if data.get("site_url", "").split("?")[0].rstrip("/") != "https://carriehw.github.io/ai-marketing-daily":
        errors.append("unexpected publication destination")
    if review.get("edition_date") != today or "human" not in review.get("scope", ""):
        errors.append("localization review date/scope invalid")
    localizations = review.get("items", [])
    if len(localizations) != len(data.get("items", [])):
        errors.append("localization/article count mismatch")
    by_url = {x.get("url"): x for x in localizations}
    for n, (article, evidence) in enumerate(zip(data.get("items", []), proof.get("stories", [])), 1):
        errors += [f"story {n}: {e}" for e in story_errors(article, evidence, by_url.get(article.get("url"), {}), today)]
    return errors


def current_packet(root):
    root = Path(root)
    data = read_json(root / "data.json")
    date = data["date"]
    return {"packet_version": "1.0", "edition_date_hkt": date,
            "status": "editorial_approved", "data": data,
            "evidence": read_json(root / "editorial/evidence" / (date + ".json")),
            "localization_review": read_json(root / "editorial/localization_review" / (date + ".json"))}


def prepare(root, today, check_only=False):
    root = Path(root)
    path = root / "editorial/editions" / (today + ".json")
    packet = read_json(path) if path.is_file() else current_packet(root)
    errors = validate(packet, today)
    if errors:
        raise ValueError("EDITION PACKET HELD:\n - " + "\n - ".join(errors))
    if not check_only:
        for path, value in ((root / "data.json", packet["data"]),
                            (root / "editorial/evidence" / (today + ".json"), packet["evidence"]),
                            (root / "editorial/localization_review" / (today + ".json"), packet["localization_review"])):
            write_json(path, value)
    return packet


def resolve_edition(data, wall_date, changed_paths, canonical_exists=False):
    """New content must be today's; code-only work may audit the last issue."""
    publication_paths = re.compile(r"^(data\.json|editorial/(editions|publish_requests|evidence|localization_review)/\d{4}-\d{2}-\d{2}\.json)$")
    publication = any(publication_paths.fullmatch(p) for p in changed_paths)
    if publication:
        packet_changed = f"editorial/editions/{wall_date}.json" in changed_paths
        derived_changed = any(p == "data.json" or re.fullmatch(r"editorial/(?:evidence|localization_review)/\d{4}-\d{2}-\d{2}\.json", p) for p in changed_paths)
        if canonical_exists and derived_changed and not packet_changed:
            raise ValueError("update the canonical edition packet; direct derived-input edits must not be silently overwritten")
        dates = {m[1] for p in changed_paths
                 if (m := re.fullmatch(r"editorial/(?:editions|publish_requests)/(\d{4}-\d{2}-\d{2})\.json", p))}
        if dates and wall_date not in dates:
            raise ValueError("publication request is not for the current Hong Kong date")
        return wall_date, True
    return data["date"], False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["snapshot", "prepare", "check", "resolve"])
    parser.add_argument("--today", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--before", default="")
    parser.add_argument("--outputs", type=Path)
    args = parser.parse_args()
    if args.command == "resolve":
        changed = []
        if re.fullmatch(r"[0-9a-f]{40}", args.before) and set(args.before) != {"0"}:
            changed = subprocess.check_output(["git", "diff", "--name-only", args.before, "HEAD"], cwd=args.root, text=True).splitlines()
        date, publication = resolve_edition(read_json(args.root / "data.json"), args.today, changed,
                                            (args.root / f"editorial/editions/{args.today}.json").is_file())
        if args.outputs:
            with args.outputs.open("a") as handle:
                handle.write(f"date={date}\npublication_intent={str(publication).lower()}\n")
        print(f"Hong Kong date {args.today}; {'new publication' if publication else 'existing-issue code/asset audit'} {date}")
        return
    if args.command == "snapshot":
        packet = current_packet(args.root)
        errors = validate(packet, args.today)
        if errors:
            raise ValueError("\n".join(errors))
        write_json(args.root / "editorial/editions" / (args.today + ".json"), packet)
    else:
        packet = prepare(args.root, args.today, args.command == "check")
    print(f"PASS edition packet: {args.today}, {len(packet['data']['items'])} reviewed stories; semantic review is required before submission")


if __name__ == "__main__":
    main()
