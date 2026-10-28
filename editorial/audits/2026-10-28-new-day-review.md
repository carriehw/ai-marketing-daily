# New-day automation review — 2026-10-28

## Coverage and evidence boundary

Reviewed discovery, original-source reading, actual second-pass checks, scoring,
formal approval, trilingual completion, persistent article handoff, edition
submission, CI build, Pages deployment conditions, live acceptance, shared
release receipts, social preparation gating and the newsletter payload handoff.

The saved 07:00 HKT primary task is enabled with exact scheduling; it has no
first-run record yet. Existing issue CI/live acceptance is tested. A complete
October 29 unattended discovery-to-publication run has not happened.
The separate private Power Automate flow and actual recipient delivery logs
were not accessible in this review. Payload publication does not certify delivery.

## Additional findings and fixes

- PR #13 fixes a real NameError when an article's source date equals the issue
  date. A literal newline escape had left the same-day allowlist assignment
  inside a comment. Six synthetic controls reproduced failures before the fix
  and passed afterward, without changing source/approval/human-hold gates.
- The first main #13 audit passed the 25-asset plan and root/discovery/locale
  validators, then failed on a second read of the dated archive. Its message did
  not expose the fetch error or observed digest. The identical version succeeded
  on rerun (run 40667841144, attempt 2), consistent with an intermittent live-read
  problem; the old diagnostic cannot establish its exact HTTP/digest cause.
- PR #14 adds bounded retries of only unmatched assets (three reads maximum,
  5s and 10s pauses) in both planning and acceptance, and records the actual
  fetch error or observed hash. Persistent incorrect bytes still fail closed.
- Total controls: 51 editorial/date/publication tests plus 4 Chinese EDM tests.
  These validate program rules, not the truth of future news.

## Tomorrow's failure triage

| Observed stage | Evidence to inspect | Likely failure area |
| --- | --- | --- |
| No primary run after its scheduled time | Automation run record | Schedule/platform execution |
| Run exists, fewer than ten completed approved article packets | Dated queue, per-story packets and exact next actions | Editorial closure, source access, genuine undersupply, or run stopping before work is persisted |
| Ten completed approvals, no publication CI | Main SHA and dated edition packet | Submission not performed, GitHub write access or a concurrent SHA conflict |
| CI starts and fails | Named failed step, actual fetch/hash errors | Input/localization/date gate, build, live access or deployment |
| Website has a valid dated receipt, email not received | Separate Power Automate run and delivery records | External delivery flow, not proof of website failure |

Based on the October 27–28 history, the first editorial handoff remains the
largest unproven operational risk: discovery and translated drafts must become
complete source-reviewed, formally approved, persisted articles.

The last scheduled editorial checkpoint is 10:45 HKT. A later unresolved
editorial/submission problem currently has no additional editor checkpoint that
day. Social preparation checks do not perform the editor's work. This review
does not add or claim an all-day editor or a new recovery schedule.

## Final observed acceptance

Both fixes are merged (PRs [#13](https://github.com/carriehw/ai-marketing-daily/pull/13)
and [#14](https://github.com/carriehw/ai-marketing-daily/pull/14)).
The final [main workflow](https://github.com/carriehw/ai-marketing-daily/actions/runs/40668536711) succeeded and automatically
wrote the dated receipt at **2026-10-28T18:00:31+08:00**. It confirmed 12 stories
per language and all 25 matching live assets. Its action was AUDIT_ALREADY_CURRENT;
Pages configuration/upload/deploy were skipped. No email or social post was sent.
