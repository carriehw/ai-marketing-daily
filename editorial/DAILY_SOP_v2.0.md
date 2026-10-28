# AI Marketing Daily — Daily Operating SOP v2.0

Adopted 2026-10-28 under Carrie's workflow-repair instruction. This implements the
Editorial Constitution; it does not lower its factual, multilingual or ten-story gates.

## Authoritative records

| Record | Purpose | Can certify publication? |
| --- | --- | --- |
| `editorial/queues/YYYY-MM-DD.json` on `daily/YYYY-MM-DD` | Compact current candidate states and next unresolved action per story | No |
| `editorial/editions/YYYY-MM-DD.json` | Single, complete reviewed edition input: data, evidence and localization review | No |
| GitHub Actions candidate/build result | Structural, language, browser, archive, newsletter and image checks | No |
| `editorial/releases/YYYY-MM-DD.json` on main, matching successful workflow and live edition | Actual dated release receipt, exact source/evidence bytes, live article counts and asset hashes | Yes |

Read the dated release record before old draft journals or task-chat results. A
matching successful release is not invalidated by a stale HELD result in another
chatroom. `latest.json` is a convenience pointer; its edition date must match the
requested Hong Kong date. Never infer a new issue from yesterday's pointer.

## Research and article closure

1. Resolve the actual Asia/Hong_Kong date and current main/working-branch SHAs.
2. If the dated receipt has PUBLISHED & VERIFIED, >=10 articles, matching
   `data_sha256` and `deployed_evidence_sha256`, and its linked GitHub workflow
   concluded successfully, confirm the actual edition where accessible and stop
   as ALREADY CURRENT. When the chat's web tool cannot read Pages, the existing
   CI live-byte and live-article acceptance evidence is the technical fallback;
   do not hold an already verified issue solely because that web tool failed.
3. Otherwise reuse the compact queue. Discover roughly 20–25 relevant sourced
   candidates only when creating a new day's queue, and de-duplicate against
   published history. Every provisional score >=60 enters processing or an
   explicitly recorded reserve. A score is never approval.
4. Process the highest-value unresolved articles through **all** stages before
   moving on: inspect original text; record atomic claims and actual source/event
   dates; reopen and challenge pivotal claims; make an explicit editorial
   decision; complete Traditional Chinese, English and Simplified review notes;
   validate the matching article/evidence/localization tuple. Preserve actual
   reviewer provenance and scope. Do not invent a separate reviewer, human
   approval, product trial or independent performance measurement.
5. A company announcement can be reported as an attributed announcement with its
   rollout limits. Do not require a product trial merely to report that an
   announcement exists. Remove unsupported ROI, universal-availability or causal
   assertions; hold a story if the remaining pivotal claim is unsupported.
6. Human-review holds apply to genuinely unresolved high-consequence matters.
   Never clear them wholesale. Mere existence of a draft is not a human-review
   requirement for every otherwise publishable story.
7. Queue states: DISCOVERED, SOURCE_READ, REVIEWED, APPROVED, HELD or REJECTED.
   `approved_count` is the count of genuinely complete APPROVED records; it is not
   the number searched, translated or conditionally approved. Every HELD record
   needs a precise remaining source/claim and next action. Save old history in
   dated audit entries rather than appending stale blockers to the current state.
8. If a source fails, use the same event's canonical official source or direct
   reporting and record the access limitation. A blocked page does not approve a
   claim. Reuse approved translations after checking qualifiers and dates.

Persist every complete article, even when fewer than ten are ready, in
`editorial/articles/YYYY-MM-DD/STORY-SLUG.json` with `edition_date_hkt`,
`state: APPROVED`, `article`, `evidence` and `localization_review` (the matching
one-story objects from the adopted schema). Put its `article_packet_path` in the
compact queue. Checkpoint tasks reuse those exact reviewed objects rather than
rebuilding completed work. The editorial QA workflow runs `check-stories` against
completed article packets; incomplete/conditional material stays in work records
and cannot be counted as a completed article. The full edition still requires ten.

The instruction to keep the original 14 candidates applied to **2026-10-28 only**.
It is not a permanent daily candidate count. Later editions use their own dated
queue; no subsequent task should restart that day's research unnecessarily.

## Submit without requiring a local shell

The canonical packet is the JSON object:

```json
{
  "packet_version": "1.0",
  "edition_date_hkt": "YYYY-MM-DD",
  "status": "editorial_approved",
  "data": {"date": "YYYY-MM-DD", "items": []},
  "evidence": {"schema_version": "1.0", "stories": []},
  "localization_review": {"edition_date": "YYYY-MM-DD", "items": []}
}
```

The abbreviated empty arrays above are documentation, not a valid publishable
packet. Follow the complete adopted schema and today's approved packet example.
Require >=10 complete, relevant articles (target 12–18), >=3 separately documented
claims per article, actual second-pass provenance, all five scoring dimensions,
accurate source timestamps, matched final titles and reviewed localization.

With a shell, run `python editorial/edition_packet.py check --today YYYY-MM-DD`
and inspect any failure. `snapshot` creates a packet from already approved legacy
inputs; it cannot approve unfinished material. CI repeats all checks independently.

Without a shell, use the GitHub connector. Do not stop merely because local git,
Python, Node or direct Pages access is absent:

1. Save incremental work to the dated branch/queue with expected-SHA protection.
2. Once editorial review is actually complete, assemble one approved packet.
3. Refresh main and dated-branch SHAs. Use Git tree/commit/ref tools to submit the
   packet atomically to main, based on that exact current main tree and expected
   branch SHA. Include the reviewed input only, not fabricated build results.
4. Read the resulting Verified AI Marketing Daily Build & Deploy run. CI
   materializes the existing three inputs, runs all existing source-record,
   date, language, reader, archive, search, newsletter and sharing-image gates,
   commits compiled artifacts, deploys if needed, verifies the actual public
   bytes, then writes the shared receipt automatically.
5. A failed input remains unpublished. Fix the specific error and resubmit the
   corrected packet. For a transient failed CI job, rerun only that failed job
   when supported. An explicit `editorial/publish_requests/YYYY-MM-DD.json`
   commit can request a fresh audit/recovery of the already reviewed packet.
   Never change facts or relax a validator to turn a red run green.
6. If a conflicting SHA rejects a write, reread both branches, preserve newer
   work, and merge/rebase the intended input. Never force-overwrite another run.

Do not wait for the next scheduled iteration after >=10 complete articles are
ready. Submit, inspect the run, and finish the receipt in the same iteration when
possible. If execution ends, preserve the actual run ID and unresolved action for
the next checkpoint. Scheduled iterations do not imply work continues between them.

## CI and release receipt

* Documentation/policy-only commits run editorial controls, not daily deployment.
* A new publication input must be for the actual HKT day. Code-only work may
  build/audit the existing dated issue without renaming it to today.
* Pull requests check candidates without deployment, production writes or receipts.
* On main, an identical approved edition with matching actual live asset bytes is
  audited without another deployment. A changed candidate follows normal deploy.
* Shared receipts are created only after the existing production validators plus
  exact asset, three-language article-count and newsletter-digest checks pass.
* The reviewed evidence snapshot is not modified after its newsletter digest is
  calculated. The separate release receipt records later acceptance.
* Receipts and compact queues are committed with `[skip ci]`; these metadata
  updates cannot recursively publish or send another issue.
* No task here sends Outlook email or posts to social media. The existing private
  Power Automate flow owns delivery; no delivery success is inferred from a feed.

## Downstream acceptance and retries

The social task reads the dated receipt from **GitHub main**, checks it against
the current data/evidence snapshot and successful linked workflow, then applies
its existing four-story source review and per-day delivery de-duplication. It
does not require an old editor-task chat result to become current. Newsletter
generation remains from that same approved snapshot; external sending retains
its own permissions and per-day send guard.

Primary editor: fixed 07:00 HKT; checkpoints retain 08:45, 09:45 and 10:45 HKT.
09:30 is the release target, not a promise to override unavailable evidence.
The checkpoints close unresolved items and repair actual publication failures;
they do not add another planning round or repeatedly translate the candidate pool.

## Security and change review

The workflow keeps its existing permissions; no new secret, account access or
recipient is added. It uses normal pull_request, never pull_request_target.
Production commits, Pages deployment and receipts require main and a non-PR event.
Both CI writes refresh and compare the expected main SHA; no forced push is used.
The immutable evidence and all >=10/source/date/localization gates remain active.
Tests cover draft/conditional/human holds, missing claims, wrong dates, stale
receipts, bad live counts, newsletter mismatches, PR isolation and duplicate avoidance.
