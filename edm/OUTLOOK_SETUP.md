# English AI Marketing Daily — Microsoft 365 Outlook delivery

This repository generates an English-only six-highlight team newsletter from
the **same verified daily issue** used for the website.

## Published files

- `edm/team.html` — fully styled email HTML, suitable for browser preview.
- `edm/subject.txt` — subject line.
- `edm/payload.json` — Power Automate transport payload with `edition_date`,
  `language`, `subject`, `headline_count`, `featured_count` and `html`.

Production endpoint after merge and successful deployment:

`https://carriehw.github.io/ai-marketing-daily/edm/payload.json`

No Outlook credentials or recipient addresses are stored in this public repo.

## What the repository does (automatically)

The existing `.github/workflows/deploy.yml` ensures all of the following
complete before publishing:

1. Edition date equals today's Asia/Hong_Kong date.
2. Editorial evidence gate, chronology checks and 10-story news minimum pass.
3. Generate `index.html`, archive and standard website email.
4. Generate `edm/team.html`, `edm/subject.txt`, `edm/payload.json`.
5. Run `verify_team_edm.py`: exactly 6 English stories; internal story links
   resolve to real article IDs; campaign tags and subject match; no employee
   email addresses; safe HTML size.
6. Deploy and verify the live issue. If build fails, artifacts are not deployed.

## Private Power Automate flow (one-time setup by licensed M365 account)

**Do not store colleagues' addresses in the GitHub repository.**
Power Automate needs an Outlook connection for the requested sending mailbox.
The native ChatGPT Outlook connector currently sends *plain text only*; it
cannot send this HTML directly.

1. At https://make.powerautomate.com select **Scheduled cloud flow**.
   Recurrence: every 1 day, time zone **(UTC+08:00) Beijing, Chongqing, Hong
   Kong, Urumqi** / China Standard Time, run at **10:30**.
2. Turn on trigger **Concurrency Control** with degree of parallelism **1**.
3. Add an **HTTP** action: method **GET**, URL
   `https://carriehw.github.io/ai-marketing-daily/edm/payload.json`.
   The general HTTP connector is Premium in most Microsoft 365 plans; confirm
   tenant/flow-owner licensing with IT.
4. Optionally **Parse JSON** on the HTTP response body, or access properties
   directly. Relevant expressions:
   - `body('HTTP')?['edition_date']`
   - `body('HTTP')?['subject']`
   - `body('HTTP')?['html']`
   - `body('HTTP')?['headline_count']`
   - `body('HTTP')?['featured_count']`
   - `body('HTTP')?['language']`
5. Use a **Condition** with ALL of:
   - `body('HTTP')?['edition_date']` equals
     `formatDateTime(convertTimeZone(utcNow(),'UTC','China Standard Time'),'yyyy-MM-dd')`
   - `body('HTTP')?['language']` equals `en`
   - `int(body('HTTP')?['headline_count'])` greater than or equals `10`
   - `int(body('HTTP')?['featured_count'])` equals `6`
   If any check fails, **do not send the team newsletter**; send the flow
   owner an internal exception alert instead.
6. In the YES branch, query Outlook **Sent Items** for today's *exact* EDM
   subject and expected sender. Skip sending if that edition already exists.
   Also add a unique-date condition so retried runs cannot accidentally send
   yesterday's edition. Avoid blind send retries after an ambiguous timeout.
7. **Office 365 Outlook — Send an email (V2)**:
   - To: the four approved internal recipients, added privately in this flow.
   - Subject: `body('HTTP')?['subject']`
   - Body (HTML): `body('HTTP')?['html']`
   - Send from the flow owner's authorized Outlook account.
   - Do not use the plain-text-only ChatGPT Outlook connector for this step.
8. First run a **manual test with the owner's own address only**. Inspect
   Outlook desktop/web and mobile rendering, links and spam filtering. Then
   enable the four-person live list.
9. **Only after the HTML flow passes end-to-end testing**, disable the
   separate ChatGPT 10:30 plain-text newsletter task to prevent duplicate mail.

## On failure / rollback

- Daily publish gate failed: the site remains on the last valid issue;
  Power Automate's date condition refuses to send stale content.
- Power Automate HTTP/Outlook errors: flow run history records failure; alert
  the owner instead of fabricating a success.
- Re-run risks: ensure Sent Items check occurs before any retry.
- Preserve the original bilingual website and old standard `email.html`.
- The HTML version is English only. Website remains bilingual.
