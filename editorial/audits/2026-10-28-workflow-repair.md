# Daily publication workflow repair — 2026-10-28

Carrie authorized correcting the publication workflow after the October 27–28
research and publishing iterations stalled.

## Verified result

- Repair PR [#12](https://github.com/carriehw/ai-marketing-daily/pull/12) merged
  at `8913e8c0e7d1c5bc959c2af24e83711ec06f40a0`.
- The main [build and acceptance run](https://github.com/carriehw/ai-marketing-daily/actions/runs/40646363612) completed
  successfully. It generated the shared release receipt automatically at
  **2026-10-28T14:52:17+08:00**.
- The accepted issue is **2026-10-28, 12 stories in each of English,
  Traditional Chinese and Simplified Chinese**. All **25** required live asset
  hashes and the newsletter data/evidence digests matched.
- The acceptance action was **AUDIT_ALREADY_CURRENT**. Configure Pages,
  upload and deploy steps were skipped. The public issue and feed were not
  published again. No email or social post was sent by this repair.
- Data digest: `5719411e8d097fc22397b85d3a2f4b421e90edc51b1eed6f60d9ac09176896a9`.
- Evidence digest: `27d4580faeb03e85853c14455f90ab6cca097b8fa4fd497d5c10fafafeb058a4`.
- The two unresolved candidates remain HELD in the compact queue. The quality
  threshold was not changed.

## Corrections

1. Store every genuinely completed article/evidence/localization tuple before
   the issue reaches ten. Reuse these exact objects at later checkpoints.
2. Submit one complete approved edition packet to the existing CI build. A
   research task without a local shell can submit via the GitHub connector.
3. CI validates inputs, builds all existing outputs, deploys only when required,
   verifies actual live assets/counts/digests, and writes one shared dated
   release receipt. Downstream tasks use it instead of stale task-chat HELD.
4. Policy and documentation changes run quality checks without forcing
   yesterday's issue through today's publication-date guard.
5. Chinese RSS preserves an existing issue's first build timestamp when
   rebuilding it, avoiding byte changes caused only by the clock.
6. The current SOP and saved prompts explain the real handoff, exact valid
   fields, per-story closure and publication evidence. October 28's fourteen
   candidates are not a permanent restriction on future days.

## Saved automation settings

Actual settings were read back after saving; IDs and schedules are in
[automation-config.json](../automation-config.json).

| Task | Saved behavior |
| --- | --- |
| Primary editor | Exact 07:00 Asia/Hong_Kong, next dated start October 29 |
| Checkpoints | Existing exact 08:45, 09:45 and 10:45 retained |
| Social preparation | Existing hourly 09:30–23:30 condition watch retained; shared release gate replaces the old task-chat gate |
| Legacy primary | Paused backup, preventing a duplicate daily run |
| Outlook fallback | Remains disabled |

The primary update API does not expose timing_mode. The flexible task was
paused and replaced with an enabled exact-schedule task
`6ae19b72c9f881918a06dc0b97f01464`.
The social task's original creative instructions and persistent completion
state were preserved verbatim. No other task or recipient was changed.

## Validation and limits

- **42** editorial/publication positive and negative controls passed.
- **4** Chinese EDM tests passed, including stable rebuild bytes and a new
  issue's new ID/time.
- Full PR CI and the merged main workflow passed existing source/date,
  trilingual, archive/search, browser, newsletter and sharing-image checks.
- Main-only write/deployment guards and expected-SHA protections remain.
- Release receipts preserve the approved evidence bytes; receipt commits use
  `[skip ci]`.
- The October 29 research run has not happened yet. Today's audit verifies the
  repaired execution path and saved settings; it does not assert future
  article availability or external Power Automate delivery.
