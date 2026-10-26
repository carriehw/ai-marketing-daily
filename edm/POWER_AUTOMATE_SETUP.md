# AI Marketing Daily — HTML Outlook Newsletter

## Status
The generator and deployment integration are staged in the GitHub feature branch. The Microsoft 365 Power Automate flow is NOT yet created, tested or activated. The existing ChatGPT plain-text Outlook schedule stays active until a real HTML test succeeds.

## Endpoints after merge and a successful, verified deploy
- HTML email: https://carriehw.github.io/ai-marketing-daily/email-zh.html
- RSS bridge: https://carriehw.github.io/ai-marketing-daily/edm/feed.xml
- Edition JSON: https://carriehw.github.io/ai-marketing-daily/edm/manifest.json

Every build runs AFTER the editorial evidence gate, requires at least 10 independent verified news stories, builds six priority highlights and links to the website. Missing live story anchors stop the EDM build.

## Standard-connector Power Automate flow (requires one-time Microsoft 365 login)
Go to https://make.powerautomate.com using the approved company account.

1. Create a Scheduled cloud flow called AI Marketing Daily — HTML Morning Brief. Schedule DAILY 10:30, time zone (UTC+08:00) Beijing/Hong Kong or China Standard Time. Enable trigger concurrency of 1 where offered.
2. Add RSS connector action "List all RSS feed items". URL: https://carriehw.github.io/ai-marketing-daily/edm/feed.xml
3. Condition (Expression): greater(length(body('List_all_RSS_feed_items')), 0). If false terminate without sending.
4. Compose action called Current_issue. Input Expression: first(body('List_all_RSS_feed_items'))
5. Condition for today's HKT issue: equals(outputs('Current_issue')?['title'], concat('AI Marketing Daily｜',convertTimeZone(utcNow(),'UTC','China Standard Time','yyyy-MM-dd'),'｜今日 6 大重點')). Otherwise stop — no old news.
6. Outlook "Get emails (V3)" in Sent Items. Search current edition subject. If already sent, do not send again. Confirm the query's results correspond exactly to the subject; subject-filter scope may be limited to latest 250 mails.
7. Outlook "Send an email (V2)". Phase 1 PRIVATE TEST: To = Carrie.hui@i-click.com; Subject = outputs('Current_issue')?['title']; HTML Body = outputs('Current_issue')?['summary']; save copy to Sent Items.
8. Run a private manual test. Verify six cards, correct Traditional Chinese fonts, no literal HTML tags, styling, mobile layout and links. Microsoft RSS FeedItem summary is a string; HTML preservation requires REAL testing.
9. If test succeeds, change To to exactly: Matthew.wong@i-click.com;Phyllis.wong@i-click.com;Cindy.swchan@i-click.com;Carrie.hui@i-click.com
10. Disable existing ChatGPT task "AI Daily 團隊 Outlook Newsletter" BEFORE enabling the production Power Automate flow. Confirm one email on next daily run.

If the RSS action sanitizes HTML or sends literal markup: DO NOT launch this flow. Use the Premium HTTP alternative, or an approved SharePoint/OneDrive sync, after confirming licensing and IT permissions.

## Premium HTTP alternative — more faithful HTML
Scheduled recurrence; HTTP GET edm/manifest.json; only proceed if its date equals today's HKT date, stories >= 10 and highlights=6; HTTP GET email-zh.html; use the returned raw HTML as the Outlook Send an email (V2) body in HTML source view; check Sent Items to prevent repeats; first send PRIVATE TEST to Carrie. This requires the approved HTTP Premium connector.

## Editorial and failure handling
If today's edition has failed evidence verification, the website is out of date, links are missing or Outlook rendering is malformed, HOLD delivery and notify Carrie. No fallback to yesterday's edition and no parallel plain-text plus HTML broadcasts. Actual GO-LIVE requires a successful Power Automate run from Carrie's company mailbox and receipt verified in Outlook Desktop/mobile.
