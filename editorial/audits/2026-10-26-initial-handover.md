# Editorial source audit — 2026-10-26 (HKT)

**Type:** Initial desk handover QA. **Status:** 1 material headline/summary concern **OPEN**; not a published correction.  
**Repository:** `carriehw/ai-marketing-daily`  
**Date:** 2026-10-26  
**Evidence:** GitHub `data.json` snapshot read 2026-10-26 (16 stories at the time of inspection, SHA `ec8df9d33e2134b11c04216bc695c0c7d2d5261f`). This snapshot may change; re-fetch before applying edits.

## Finding A — Apple Safari identity resolution claim is over-broad

- **Current title at review:** 「Apple正式表態：封鎖第三方Cookie已不足，廣告識別符一律攔截」.
- **Current summary at review:** says an all-encompassing block of advertising identifiers and all tracking approaches.
- **Current reported source:** Campaign Asia, citing Apple's response to industry concerns.
- **Primary reference (confirmed):** Apple WebKit, [Blocking Identity Resolution Infrastructure](https://webkit.org/blog/18438/blocking-identity-resolution-infrastructure/), **published 2026-10-19**.
- **Primary-source claim:** iOS/iPadOS/macOS/visionOS 27 Safari and WebKit block network access at **domain level to third-party identity-resolution infrastructure** used for cross-site tracking. WebKit specifically distinguishes first-party personalisation from cross-site tracking.
- **Editorial discrepancy:** the broad statement **“all advertising identifiers are blocked”** is not supported by the cited primary explanation; the site appears to overstate scope. This is a technical materiality issue for agency measurement/attribution decisions.
- **Recommended headline:** 「Apple擴大Safari跨網站追蹤防護：封鎖第三方身份識別基建」.
- **Recommended summary:** 「Apple WebKit說明，OS 27系列的Safari與WebKit在網域層級封鎖指定第三方身份解析基建的連線，以防止跨網站追蹤；第一方個人化不屬於此項防護的目標。」
- **Marketer takeaway (editorial inference):** audit dependency on third-party identity-resolution vendors; test actual audience matching and conversion measurement by browser and OS rather than claiming universal loss of ad identifiers.
- **Status:** **REQUIRES CORRECTION**; not changed on live website in this audit. Requires re-reading current head, coordinated rebuild of `data.json`, `index.html`, dated archive, EDM and post-deploy verification.

## Finding B — ChatGPT Ads cumulative advertiser metric now qualified

- `data.json` snapshot headlined 「ChatGPT廣告累計客戶破10萬、新增26國至89國；廣告僅出現在Free與Go方案」.
- **Primary source:** [OpenAI news, 2026-10-21](https://openai.com/index/chatgpt-ads-expands-26-new-countries/): over **100,000 advertisers have run campaigns since launch**, rollout to **89 countries** including 26 new markets; over 1.2 billion weekly ChatGPT users does not establish ad-addressable users.
- **Separate earlier metric:** [OpenAI August 31, 2026](https://openai.com/index/expanding-access-to-ai-with-chatgpt-ads/) announced **$1 billion annualised revenue run rate**; do not attribute this metric to 21 Oct's announcement or imply $1B realised annual revenue.
- **Review status:** primary headline correctly says **累計** and Free/Go scope; prior material overstatement appears addressed in this snapshot. Supporting commentary includes third-party advertiser-count estimates that require separate direct-methodology checks before declaring fully verified. No blanket “verified all claims” conclusion.

## Process / follow-up

1. **No substantive production article edits made as part of this audit.** Active content editing may be concurrent, so partial updates without rendered archive/site rebuild risk desynchronisation.
2. GitHub **Issues are disabled** for this repository (create attempt returned 410); use versioned audit files and commit history for review queue until an alternative tracker exists.
3. Next daily run should resolve the open Apple issue with source-linked correction, rebuilding all relevant outputs and verifying deployed HTML and archive.
4. Do not claim completion of the new automated fact-checking CI gate merely because an editorial constitution and evidence template now exist.

**Owner:** Carrie Hui / AI Marketing Daily Editorial Desk
