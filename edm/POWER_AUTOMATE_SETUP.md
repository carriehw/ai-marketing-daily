# AI Marketing Daily — English HTML delivery

## Status
Outlook template corrections and a standard-connector transport are implemented in source. The Power Automate flow remains a manual review flow until an actual successful send and the owner's Outlook Desktop, Web and Mobile approval. Do not activate recurring delivery or disable the original text task before that approval.

## Canonical source and standard transport
- Canonical JSON: https://carriehw.github.io/ai-marketing-daily/edm/payload.json
- Browser HTML: https://carriehw.github.io/ai-marketing-daily/edm/team.html
- RSS transport: https://carriehw.github.io/ai-marketing-daily/edm/payload-feed.xml

The RSS item description contains base64 of the identical UTF-8 bytes from payload.json, generated in the same build. It contains no recipients or credentials. Decoding yields the original JSON and its html property, avoiding RSS HTML sanitisation. verify_team_edm.py verifies byte equality. Use the standard RSS List all RSS feed items action during review. HTTP GET of the canonical JSON is an alternative only when Premium licensing is available.

## Private Power Automate flow
1. Manual trigger during review; concurrency 1. Production recurrence only after owner approval: daily 10:30, China Standard Time (Hong Kong).
2. RSS: List all RSS feed items from payload-feed.xml. Abort when no item exists.
3. Compose Current_issue with json(base64ToString(first(body('List_all_RSS_feed_items'))?['summary'])). Match action names to the designer's code view.
4. Require edition_date equal convertTimeZone(utcNow(),'UTC','China Standard Time','yyyy-MM-dd'), language en, verification_status editorial_approved, headline_count at least 10, featured_count exactly 6, and nonempty html. Missing or invalid fields fail closed. Do not use yesterday's edition as fallback.
5. Query the connected mailbox's Sent Items for the exact test subject (including template version) or exact production subject. Stop if a matching send exists. Test and production have separate identities. Disable blind retries on Send an email (V2); an ambiguous timeout requires inspection before retry. Use durable private per-edition reservation/logging before production activation; an Outlook query alone is not atomic exactly-once delivery.
6. Office 365 Outlook Send an email (V2), using the authorised mailbox connection. Set HTML body using the Current_issue html expression; do not paste into the visual rich-text editor. Set only the owner's private address during review. Store recipients in the private flow only.
7. Run exactly one test. Verify actual Outlook Desktop/Web/Mobile fonts, CTA, six card spacings and labels, date and links. A browser preview is not an Outlook rendering test.
8. Following explicit owner approval, configure approved private recipients and daily schedule, verify the complete flow, and only then disable the original text task.

## Template corrections
Every text element declares Arial/Helvetica/sans-serif inline. Card content and labels use presentation-table cells, fixed-height spacer rows, explicit line heights and padding. The CTA uses a coloured and padded table cell; classic Outlook may show square corners. A conditional 620px wrapper supports classic Outlook and fluid width supports mobile. No JavaScript or external font dependency.

