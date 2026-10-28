# AI Marketing Daily — Daily Operating SOP v1.0

**Owner:** Carrie Hui · **Effective:** 2026-10-26 · **Timezone:** Asia/Hong_Kong  
**Authority:** Read [Editorial Constitution v1.0](./EDITORIAL_CONSTITUTION_v1.0.md) first; this SOP is subordinate to it.  
**Repository:** `carriehw/ai-marketing-daily` · **Live:** https://carriehw.github.io/ai-marketing-daily/?lang=zh

## A. Daily run contract (outcome, not just attempts)

Produce a verified **HKT-dated edition of the website** with matching content, archives and distribution assets **only when the entire pipeline can be completed safely**. Report the outcome explicitly as one of:
- **PUBLISHED & VERIFIED** — exact live URL, HKT date, number of articles, source-check coverage, archive link, tested build/revision evidence.
- **ALREADY CURRENT — AUDITED** — today's edition already live; no duplicate issue created; report material corrections, if any.
- **DRAFT / HELD** — evidence, editorial or approval gates not passed; no claim of publication.
- **FAILED** — tool, access, build, deploy or live-verification failure; report the failing step, last confirmed live date, remediation and whether readers may see an old issue.

**Never report “success” solely because GitHub accepted a commit or the home page returned HTTP 200.**

## B. Preflight: inspect and avoid collisions

1. Resolve **today's date and edition weekday in HKT**, not from UTC system time.
2. Read the current Constitution, this SOP, `data.json`, `seen-stories.json` and `seen-urls.json`, the current site, and recent GitHub commits. Determine whether another editor/routine **already prepared or published today's edition**.
3. Check repository write access and actual available execution tools. GitHub Pages `deploy.yml` **deploys committed artifacts**; it does **not itself collect news or execute the Python build scripts**. An automation with only permission to write JSON is **not** sufficient to publish a new issue.
4. If current live edition already has today's HKT date, **audit instead of replacing it blindly**. Make only separately verified corrections where safe and traceable.
5. If another update is in progress or newer repository files appear during editing, refresh the upstream state before any write; avoid overwriting a concurrent run.


## B1. Daily coverage service level (approved 2026-10-26)

- **Editorial floor: 10 individually verified, sufficiently marketing-relevant full news items per Hong Kong edition.**
- **Preferred full-coverage target: 12–18 verified items** across the existing five editorial categories, including **3 lead stories**, **7–10 additional main stories**, and, where useful, **2–5 short Radar signals**. Radar signals can be separate briefs and are not counted towards the 10 full-news floor unless they meet the same verification/content standard.
- Source discovery should expand across appropriate first-party and reputable independent sources when the preliminary set falls below 10; do not repeat yesterday's unchanged story, split one development artificially, invent facts, or upgrade unverifiable rumours to meet the count.
- If fewer than 10 independently verified meaningful items exist after reasonable discovery, **do not auto-publish a below-floor issue**. Keep the draft on hold, log `below_editorial_floor`, and notify Carrie with the count and reasons. Any exceptional below-floor edition needs explicit Publisher approval and a separately tested gate exception; never weaken a validator silently.
- **If the technical website checker expects at least eight cards and fewer than eight are verified, do not pad the issue**: review/update that gate, explicitly flag any exception, and only publish when the amended gate and evidence controls pass.
- The minimum quota and target refer to **daily full-issue totals**, not the homepage's **three Top Stories**.

## B1a. Staged automatic discovery, verification and recovery (from 2026-10-28)

**Daily target:** 08:00 HKT discovery and initial verification; aim to release by 09:30 HKT if—and only if—the entire evidence, multilingual build, archive and live acceptance gate passes. The timing goal is not a license to weaken journalism. Automation scheduling/execution may vary; verify actual runs and live site before making publication claims.

**Automation orchestration and active-task limit:** The active 08:00 AI Marketing Daily editor begins research. One companion daily task runs separately at **08:45, 09:45 and 10:45 HKT**, using hour-specific instructions. The 09:45 check is explicitly 15 minutes after the aspirational 09:30 release target. These runs are *not* one continuous background agent; each must read the latest upstream state. This arrangement avoids consuming more scheduled-task slots than the current account permits. Do not disable other users' reminders, newsletters or social-media tasks to add slots.

1. **08:00 — first-pass discovery:** Read current HKT edition, main SHA, original public site, Editorial Constitution, seen-URLs/stories, available draft. Cover first-party OpenAI/Google/Meta/Apple and other platform sources, global advertising/MarTech trade media, APAC and Chinese market reporting, advertising, media buying, search/GEO, CRM, brand safety and agency economics. Aim for a researched **candidate pool around 20–30 distinct developments** where the news cycle genuinely supports it; candidates are *not* editorially approved stories. Prioritise recent 24–72h and exact HKT date; relevant 3–5-day reports can be included only if they are not stale or already covered and there is a real development.
2. **08:45 — gap-first second pass:** If today's issue is already published and audited, stop. Otherwise read the 08:00 draft and fill *specific source coverage gaps*, cross-check original evidence, identify source publication/event dates, mark uncertain claims, and complete the highest-relevance candidate packets. Use the same date branch / draft; no restart from an empty feed.
3. **09:30 target / 09:45 verification checkpoint:** Audit the actual three-language public site, today's archive, search, evidence, newsletter feed and GitHub Actions. If a complete issue with at least **10 independently source-verified full stories** passes all gates, deploy and verify. Otherwise report `DRAFT — HELD` with source-read candidates **separate from** release-ready count, record blockers and hand off to the late retry.
4. **10:45 — conditional recovery:** If today's issue is live and valid, exit without duplicating copy, builds, user notifications or email. Otherwise continue source expansion and only publish once all gates pass. When still below the quality floor, leave prior good issue online and report the precise evidence gap / human approval required.
5. **Single shared state:** Save the day's progress to `editorial/drafts/YYYY-MM-DD.json`, preferably the deterministically named work branch `daily/YYYY-MM-DD`; preserve the prior candidate list, per-source locators, previous coverage, claim-level caveats, stage, source-read candidate count, approval status, release-ready count and next actions. Detect an existing branch/alternate draft; consolidate cautiously rather than discard it. Refresh branch/main SHA immediately before writes and fail on conflicting commits. No automatic merge to main until a full issue passes all release gates.
6. **Newsletter and downstream social:** Never rename yesterday's edition to today. Generate the current English HTML EDM/payload only from the same `editorial_approved` site edition after actual release. Sending is owned by the separate private Outlook Power Automate workflow; the news task must never send duplicate email, change private account settings, or initiate social posting. Late publication may miss the prior 10:30 dispatch; report it as such, with no fabricated confirmation.
7. **Progress versus success:** `source_read_candidates_count`, `release_ready_story_count`, `published_story_count` and `last_confirmed_live_edition` are different fields and must not be conflated. A successful scheduled automation run is not the same as a successful **website publication**. The day ends as `PUBLISHED & VERIFIED`, `ALREADY CURRENT — AUDITED`, `DRAFT — HELD`, or `FAILED`. Before declaring publication, verify live site bytes/edition and all mandatory controls; preserve a dated GitHub evidence and release trail.


## B1b. Verification-first execution priorities (2026-10-28)

This section refines B1a without changing the editorial floor, release gates, or existing schedule. Each run is independent and must inspect live state, main SHA, shared daily draft and evidence before acting.

**Priority order:** P0 audit today's live edition; P1 finish source verification and independent claim challenge on the strongest existing candidates; P2 complete editorial approval and Traditional Chinese, Simplified Chinese and English parity; P3 prepare evidence, archive, search, newsletter payload, builds and technical/live acceptance; P4 discover additional stories only when fewer than ten can qualify from the existing pool. Candidate counts never substitute for ready counts.

- **08:00:** Research and verification happen concurrently. Aim for a 20–25 item evidence-backed candidate pool only when the news cycle supports it, and aim for five fully checked story packets. Record actual counts, not aspirational numbers.
- **08:45:** Prioritise converting existing strong candidates to at least ten independently fact-checked, editor-approved, fully localized release-ready stories. Do not restart discovery or expand candidates merely to hit a funnel target. Build and publish immediately if every gate passes.
- **09:00–09:30:** This is an aspirational completion window, **not an additional scheduled run or a claim of continuous background work**. Complete publication within an active run when possible.
- **09:45:** First audit live production and its archive. If not current, finish the exact missing editorial or build gates and publish only if all pass; otherwise persist a story-level blocker list and next actions for 10:45. Distinguish editorially ready from technically release-ready.
- **10:45:** Recheck live edition and branch/main SHAs, then focus on the shortest path to ten genuinely ready stories and complete production acceptance. If still short, record final HELD and actual ready count; do not redate old stories or trigger duplicate EDM/social sends.

**Per-story state machine:** candidate → source_read → claim_checked → independent_reviewed → editorial_approved → localized_reviewed → full_release_ready. A story only counts as full_release_ready when source locators, material-claim review, editorial approval, all three languages and relevant evidence/technical prerequisites are complete. A structural evidence checker alone never constitutes independent factual review.

**Operational controls:** Persist candidate_count, source_read_count, independent_reviewed_count, editorial_approved_count, full_release_ready_count, published_count, last_confirmed_live_edition, blocker_by_story and next_actions in the shared date draft. Prebuild supporting assets as soon as editorial content is stable, but mark the newsletter payload approved only for the matching edition after publication/live acceptance. Re-read main and work-branch heads immediately before and after each write; stop on conflicts rather than overwrite newer work. No independent Outlook sends.

## B2. Three independent language editions (effective 2026-10-26)

- The verified fact base remains `data.json` with Traditional Chinese and English fields. Do **not** invent a separate set of news claims to fill the Simplified Chinese edition. Maintain source, date, headline qualifiers, accessible product status and brand/legal terms identically in all three versions.
- Publish independently addressable HTML pages and historic archives under `/zh-hant/`, `/zh-hans/` and `/en/`; each has **its own canonical**, language-marked `<html lang>`, localized metadata, reciprocal `hreflang`, independent share URL, and sitemap inclusion. Legacy `/?lang=zh` and `/?lang=en` keep working for older links.
- The Simplified version starts from OpenCC `t2s` converted published Chinese, then follows a controlled Mainland marketing glossary and issue-specific AI editorial review. **Automated script conversion cannot certify native Chinese expression or prove factual truth**; the issue's `editorial/localization_review/YYYY-MM-DD.json` record must contain one explicit caveat review per story and openly state the scope. Additional professional/native proofread is appropriate before relying on content in client campaigns.
- Each daily issue produces the same **number and order of underlying stories, original sources, source dates and unique stable story anchor IDs**, in all three languages.
- Release gate: `build.py` → `build_archive.py` → `build_search_index.py` → `build_locales.py`, with `verify_editorial.py`, `verify_dates.py`, `verify_ux.py`, `verify_discovery.py` and `verify_locales.py` all passing. GitHub Pages production must additionally pass `verify_locales_live.py`.
- **Never claim that three localized editions are live from source changes alone.** Verify each production homepage, dated archive, localized search asset and sitemap before announcing.
- Per-story card has one **「分享／複製」 / Share / Copy** control. The disclosure exposes exactly two actions: share the permanent article link or copy a sourced marketing team brief. Keep touch and keyboard usability, ESC dismissal and translation aligned.
- The archived older issues are originally published snapshots subsequently localized; changes of language do **not** mean their original source facts were retrospectively re-verified.

## C. Discovery and shortlist

Search selectively across:
- **Primary:** OpenAI, Google/Google Ads, Meta, Apple WebKit, Microsoft, Anthropic, TikTok, Tencent, ByteDance, Alibaba, LinkedIn, regulatory/industry bodies, original research and public filings.
- **Independent / trade reporting:** reputable global/APAC news outlets, Adweek, Campaign Asia, Digiday, AdExchanger, Search Engine Journal, TechCrunch, Marketing-Interactive, SocialBeta and credible China-market outlets as appropriate.

This is an **illustrative watch list**, never a blanket credibility endorsement. Capture source publication date and actual event date; exclude repeating mere rewrites of news already covered. Track true developments as follow-ups.

Look beyond model-launch hype: media-buying rules, search and measurement, brand safety, consumer behaviour, creative workflows, CRM, privacy, retail media, AI-led search and agency economics.

## D. Verification: hard stop for unsupported facts

For every candidate likely to appear, build an evidence record as in [evidence-template.json](./evidence-template.json). Record:
- Stable story ID; exact working source URLs and source type; event date, publication/update date and HKT verification timestamp.
- **Atomic pivotal claims**, verbatim evidence locator/excerpt, support strength (`verified` / `attributed` / `uncertain` / `rejected`), region/rollout caveats and whether the original text was accessible.
- A second-pass challenge to names, product version, money and units, percentages, samples, dates, causal claims, status/timing and headlines.
- Whether corroboration is required/available and outstanding ambiguities.

**Remove or hold unsupported pivotal claims.** No unverifiable quote, made-up source, assertion solely from an AI-generated summary, or extrapolated performance guarantee. For higher-risk items requiring human judgement, mark `needs_human_review` and do not auto-publish that item.

## E. Score, select, and package

1. Rate *already verified* candidates on Constitution's 100-point marketer-relevance rubric. Keep scoring rationale; don't pad categories.
2. Nominate up to three lead stories, verified main stories and optional Radar, with a clear editorial takeaway.
3. Each main story has: **What happened / Why marketers care / Recommended action / What remains uncertain if material / Source + actual date.**
4. Separate **Impact** (High, Medium, Low) from **Response** (Act Now, Test, Monitor, Inform). Existing website fields `action` (`影響生意`, `可即用`, `要留意`) remain compatible until a tested UI/schema migration; map without silently changing meaning.
5. Headlines must not upgrade a company's claim into an established independent fact or upgrade a pilot to general availability.
6. Prepare `title`, `summary`, `highlights`, `why`, and bilingual `*_en` with identical facts and numbers. Optional `followup` covers **what actually changed**; `pattern` must be identifiable as analysis.
7. Reader-facing detail adds genuine substance rather than repeating highlights or making an unsourced mini-essay.

## E1. Search, filtering and reusable Team Brief output

The website exposes today's story search, section and impact filters, a historical bilingual search catalogue, and a per-story **Copy Team Brief**. For every newly published story:

1. Supply complete, useful **`next_step` and `next_step_en`** fields when a concrete action is warranted. Next steps are editorial recommendations; they must be proportionate to the evidence and carry no invented benefit or measured outcome. If no responsible action exists, leave the next step empty rather than padding.
2. Keep **`summary`/`summary_en`, `why`/`why_en`, original `url`, source name and publication date** factual and bilingual, because they are used as the shareable team brief.
3. A team brief includes a **dated archive permalink and original source link**, never an unqualified claim that the team independently tested the product.
4. Run `build_search_index.py` **after** `build_archive.py` to update `archive/search-index.json`. The archive index contains historical *published* article metadata (not unpublished research); legacy archive records without stable story anchors resolve to the correct issue page.
5. Run `verify_discovery.py` and `node --check discovery.js` as part of the publication gate. Neither source-record checks nor index checks are a substitute for testing actual browser interactions.
6. Search and Copy buttons must preserve `?lang=zh`/`?lang=en` and must never send article sharing to a rolling homepage when dated permalinks exist.
7. Accessibility: controls must retain visible labels, keyboard navigation, minimum phone-friendly touch sizes, a live result count and a no-results state. Do not expose a disabled/inert control as working.
8. Use existing GoatCounter pageview measurement only as an indicator; do not claim shares, qualified leads or downloads that are not actually measured.

## F. Editing and independent review

- **First pass — Researcher:** source and evidence collection.
- **Second pass — Fact Checker:** reopen primary source(s) independently; explicitly compare headline and material claims with evidence. Do not accept the first AI writer's confidence as verification.
- **Final pass — Senior Marketing Editor:** assess relevance, commercial reasoning, language, sensible actions, title accuracy, share utility and consistency.
- **Safety exceptions:** legal/regulatory interpretation, market-moving information, exceptional performance claims, unresolved conflicting reporting, major reputational allegations and unsupported high-impact news: human editorial review or hold.

If evidence is missing, do not populate a “verified” field for appearance's sake. The site must not claim independent verification that didn't occur.

## G. Build and commit (existing repository mechanics)

Current known assets include:
`data.json`, `build.py`, `build_email.py`, `build_archive.py`, `build_ogimage.py`, `verify_email.py`, `verify_live.py` and archive manifests.

1. Re-read the current source files and their actual command-line instructions before execution; preserve section labels, branding, analytics, link anchors and existing hard-won presentation safeguards.
2. **Never update only `data.json` and call it a published website.** The repository's Pages deploy copies files; rendered `index.html`, archive, and distribution assets must be rebuilt and committed consistently.
3. Create a genuine `editorial/evidence/YYYY-MM-DD.json` packet covering **all** stories in that edition. Execute `python3 editorial/check_evidence.py --data data.json --evidence editorial/evidence/YYYY-MM-DD.json`. **Exit 1 blocks publication**. Then perform independent semantic source validation: a structural PASS proves the fields and review records are present, **not** that the news is factually true. The checker is currently not integrated into the legacy Pages deploy and must be invoked explicitly by the publishing operator. Unit-test CI: `.github/workflows/editorial-qa.yml`.
4. Keep article evidence records linked to the issued edition. Capture revision/commit SHA.
5. Run all compatible local checks and builds in the order required by the CURRENT code; don't guess script order. Verify no unintended changes to older archives, analytics, fonts, translated copy, share graphics, EDM and shared URLs.
6. Upload/commit coherently. A branch/PR is appropriate for structural code or policy changes; content publication can follow the established safe path when all checks pass.
7. Do not modify active production workflows, disable analytics, replace historical archives, or introduce secrets without explicit security review.

**Known mismatch to resolve:** current `verify_live.py` expects at least eight story cards, whereas this Constitution explicitly permits fewer verified stories. Update and test this guard before deliberately issuing a shorter edition; never add filler to satisfy a number.

## H. Verification after publication

Check with cache bypass where possible:
- Actual live `index.html` date and article fingerprint match the newly built edition.
- Actual live `archive/YYYY-MM-DD.html` exists and shows the intended HKT date.
- `archive/manifest.json` lists today with no loss of past archives; archive directory lists the issue.
- Primary source links point to relevant material, bilingual content and card anchors work, social share preview and fonts load.
- The delivered EDM (if in scope) is consistent with the website. Run `verify_email.py` if it is being generated.
- Use `verify_live.py` where executable; failing checks are **not** an editorial success.
- Correctness of today's published **news** must be checked separately from these technical verifications.

If any check fails, mark **FAILED**, preserve previous valid edition where possible, explain the last confirmed live date. Report errors immediately.

## I. Corrections and high-impact alerts

- Log `Correction`, `Update`, or `Retraction` as defined in the Constitution, with affected headline, exact change, source and GitHub revision.
- An active factual error in a top story is an editorial incident. Prioritise a corrected live article, not a silent rewrite.
- Avoid declaring dramatic financial, legal or brand-safety assertions without evidence. Place uncertainty in plain sight.

## J. Daily status report format (to Carrie)

```
AI Marketing Daily｜YYYY-MM-DD (HKT)
Status: PUBLISHED & VERIFIED / ALREADY CURRENT — AUDITED / DRAFT — HELD / FAILED
Live edition: [URL + verified date]  |  Archive: [URL]
Selected: N published / N held  |  Top stories: [up to three short headings]
Verification: [material claims checked, notable qualifications]
Corrections: [none / dated change & evidence]
Marketing angle: [one short practical observation]
Blocker / next step: [only if needed]
GitHub revision: [SHA / not committed]
```

## K. Future improvement, not falsely reported as deployed

- Structural evidence validation and unit-test CI now exist. **Remaining:** integrate the gate into the established production build-and-publish workflow after backfilling all new-issue evidence packets and running end-to-end failure-case tests. Structural validation is **not** factual verification.
- Establish stable article IDs and a corrections index, richer engagement instrumentation and Team Brief copy/share controls.
- Perform a live trial run with failure-case controls before claiming end-to-end autonomous publication.
- Keep existing weekly AI social-content preparation separate. Repurpose **verified** stories only after the site edition itself passes review.

**Revision:** v1.0 · **2026-10-26**.
