#!/usr/bin/env python3
"""Build an English-only, Outlook-safe AI Marketing Daily team EDM.

Inputs: verified data.json and generated index.html. Outputs:
  edm/team.html     – previewable email-safe HTML
  edm/subject.txt   – subject for the current issue
  edm/payload.json  – public, read-only Power Automate handoff (no recipients)

This only generates artifacts. Sending is owned by the separately authorised
Microsoft 365 flow, after the production issue/date checks.
"""
import datetime as dt
import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
ISSUE = dt.date.fromisoformat(DATA["date"])
TODAY = ISSUE.isoformat()
ITEMS = DATA["items"]
assert len(ITEMS) >= 10, "Not enough verified stories to make a team EDM"
SITE = DATA.get("site_url", "https://carriehw.github.io/ai-marketing-daily/").split("?")[0].rstrip("/") + "/"
OUT = ROOT / "edm"
OUT.mkdir(exist_ok=True)

# Follow the site's actual story IDs, not an independently reimplemented slug.
PAGE = (ROOT / "index.html").read_text(encoding="utf-8")
ANCHORS = {}
for name in re.findall(r'id="([a-z0-9][a-z0-9-]*-[0-9a-f]{6})"', PAGE):
    ANCHORS.setdefault(name.rsplit("-", 1)[-1], name)

def esc(x):
    return html.escape(str(x or ""), quote=True)

def track(url, placement):
    bits = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(bits.query, keep_blank_values=True)
    query.extend([
        ("utm_source", "edm"),
        ("utm_medium", "email"),
        ("utm_campaign", "ai-daily-" + TODAY),
        ("utm_content", placement),
    ])
    return urllib.parse.urlunsplit((bits.scheme, bits.netloc, bits.path,
                                   urllib.parse.urlencode(query), bits.fragment))

def url_for(item, placement):
    original = urllib.parse.urlsplit(item["url"])
    key = (original.netloc.lower().replace("www.", "") + original.path.rstrip("/")).encode()
    suffix = hashlib.sha1(key).hexdigest()[:6]
    anchor = ANCHORS.get(suffix)
    if not anchor:
        raise ValueError("Missing on-site article anchor: " + item["title_en"])
    return track(SITE + "?lang=en#" + anchor, placement)

# Relevance-first; break ties by the site's editorial order. Cap category
# concentration at two, so this remains useful across agency disciplines.
WEIGHTS = {"影響生意": 0, "可即用": 1, "要留意": 2}
ordered = sorted(enumerate(ITEMS), key=lambda x:(WEIGHTS.get(x[1].get("action"), 3), x[0]))
picked, counts = [], {}
for _, story in ordered:
    section = story["section"]
    if counts.get(section, 0) >= 2:
        continue
    picked.append(story)
    counts[section] = counts.get(section, 0) + 1
    if len(picked) == 6:
        break
if len(picked) < 6:
    for _, story in ordered:
        if story not in picked:
            picked.append(story)
        if len(picked) == 6:
            break
assert len(picked) == 6
for story in picked:
    for field in ("title_en", "summary_en", "why_en", "url", "section", "source"):
        if not str(story.get(field, "")).strip():
            raise ValueError("Selected story missing English EDM field " + field)

NAVY, VIOLET, LIME = "#11154A", "#5A42F4", "#D3FE66"
PAPER, WHITE, INK, MUTED = "#F7F5EF", "#FFFFFF", "#101114", "#656A73"
BORDER, TINT = "#DEDBD2", "#EBE8FF"
FONT = "Arial,'Helvetica Neue',Helvetica,sans-serif"
LABELS = {"影響生意": "BUSINESS IMPACT", "可即用": "READY TO USE", "要留意": "WORTH WATCHING"}
PILL = {"影響生意": ("#EBE8FF", "#5438D6"), "可即用": ("#E2F3EC", "#1D7656"),
        "要留意": ("#FDF3E2", "#A25900")}
CATCOLORS = {"AI 大模型 & 市場動態": "#39689F",
             "廣告平台 & 行銷科技": "#3F5BC8",
             "創意生產工具": "#6249D7",
             "行業影響 & 品牌案例": "#9A3A9E",
             "即學技巧 & 玩法": "#7D266B"}
def pill(story):
    bg, fg = PILL.get(story.get("action"), (TINT, VIOLET))
    return '<span style="display:inline-block;background:%s;color:%s;padding:5px 9px;border-radius:99px;font:700 10px %s;letter-spacing:.5px">%s</span>' % (
        bg, fg, FONT, esc(LABELS.get(story.get("action"), "SIGNAL")))

def card(story, i):
    link = esc(url_for(story, "story-%d" % (i+1)))
    accent = CATCOLORS.get(story["section"], VIOLET)
    intro = '<div style="font-size:10px;font-weight:800;color:%s;letter-spacing:1.4px;padding-bottom:8px">TODAY’S TOP STORY</div>' % accent if i == 0 else ""
    fsize = "22" if i == 0 else ("18" if i < 3 else "16")
    summary = "" if i >= 3 else '<p style="margin:9px 0 0;font-size:14px;line-height:1.55;color:#3C3F45">%s</p>' % esc(story["summary_en"])
    why = '<div style="background:%s;border-left:3px solid %s;padding:10px 13px;margin-top:12px;font-size:13px;line-height:1.5;color:%s"><b style="color:%s">WHY IT MATTERS</b> — %s</div>' % (
        TINT, VIOLET, INK, VIOLET, esc(story["why_en"])) if i < 3 else '<p style="margin:8px 0 0;font-size:13px;line-height:1.5;color:#3C3F45">%s</p>' % esc(story["why_en"])
    return '''<tr><td style="padding:0 22px 12px"><table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr>
<td bgcolor="#FFFFFF" style="background:#FFFFFF;border:1px solid %s;border-top:4px solid %s;border-radius:14px;padding:18px 20px">
%s<div style="font-size:11px;font-weight:700;letter-spacing:.45px;color:%s;padding-bottom:7px">%s &nbsp;·&nbsp; %s</div>
<a href="%s" style="font:%s 700 %spx/1.28 %s;color:%s;text-decoration:none">%s</a>
%s%s<div style="padding-top:12px">%s</div>
</td></tr></table></td></tr>''' % (
        BORDER, accent, intro, accent, esc(story["source"]), "",
        link, "", fsize, FONT, INK, esc(story["title_en"]), summary, why, pill(story))

actions = []
seen_actions = set()
for story in picked:
    action = str(story.get("next_step_en", "")).strip()
    if action and action.lower() not in seen_actions:
        actions.append(action)
        seen_actions.add(action.lower())
    if len(actions) == 3:
        break

thesis = str(DATA.get("thesis_en", "")).strip()
if not thesis:
    thesis = "The six AI and marketing developments your team should review today."
SUBJECT = "AI Marketing Daily | %s | 6 key highlights" % TODAY
DATE = ISSUE.strftime("%d %B %Y")
site_link = esc(track(SITE + "?lang=en", "read-full-brief"))
actions_html = "".join('<tr><td valign="top" style="padding:0 10px 10px 0;color:%s;font-size:15px;font-weight:800">0%d</td><td style="padding:0 0 10px;font-size:14px;line-height:1.5;color:%s">%s</td></tr>' % (VIOLET,i+1,INK,esc(a)) for i,a in enumerate(actions))
stories_html = "".join(card(story, i) for i,story in enumerate(picked))
preheader = "Six verified stories, what they mean for marketers, and what to do next."
doc = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>
@media only screen and (max-width:620px) {
  .wrap { width:100%% !important; }
  .mobile-pad { padding-left:18px !important;padding-right:18px !important; }
  .mobile-heading { font-size:28px !important; }
}
</style></head>
<body style="margin:0;padding:0;background:%s;font-family:%s">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">%s</div>
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" bgcolor="%s" style="background:%s"><tr><td align="center" style="padding:20px 0">
<table class="wrap" role="presentation" width="620" cellpadding="0" cellspacing="0" border="0" style="width:620px;max-width:100%%">
<tr><td bgcolor="%s" style="background:%s;background-image:linear-gradient(115deg,#553FBA,#2F5582,#11154A,#7D266B);border-radius:18px 18px 0 0;padding:25px 28px 28px">
<div style="font-size:19px;font-weight:800;color:%s;letter-spacing:-.3px">AI Marketing Daily</div>
<div style="font-size:10px;letter-spacing:1.8px;color:#D6D4E8;padding-top:4px">AI MARKETING INTELLIGENCE · HK / CN</div>
<div style="font-size:11px;color:%s;font-weight:800;letter-spacing:1.2px;margin-top:23px">MORNING BRIEF · %s</div>
<div class="mobile-heading" style="font-size:37px;line-height:1.07;letter-spacing:-1px;font-weight:800;color:#FFFFFF;margin-top:12px">Less AI noise.<br>More marketing signal.</div>
<div style="font-size:13px;color:#EDEBF6;margin-top:15px">6 key highlights &nbsp;·&nbsp; %d stories on the site</div>
</td></tr>
<tr><td bgcolor="%s" style="background:%s;padding:22px 22px 8px">
<div style="font-size:11px;font-weight:800;letter-spacing:1.4px;color:%s">TODAY’S BIG PICTURE</div>
<div style="font-size:18px;font-weight:700;line-height:1.4;color:%s;margin:9px 0 10px">%s</div>
<div style="font-size:12px;color:%s">Curated for the agency team · Carrie Hui</div>
</td></tr>
<tr><td bgcolor="%s" style="background:%s;padding:20px 22px 14px">
<div style="font-size:20px;font-weight:800;color:%s">Top 6 Key Highlights</div>
<div style="font-size:12px;color:%s;margin-top:4px">What happened. Why it matters. Where to read more.</div>
</td></tr>
%s
<tr><td bgcolor="%s" style="background:%s;padding:15px 22px 14px">
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr><td bgcolor="#EBE8FF" style="background:#EBE8FF;border-left:4px solid %s;border-radius:9px;padding:19px">
<div style="font-size:17px;font-weight:800;color:%s;margin-bottom:15px">What Marketers Should Do</div>
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0">%s</table>
</td></tr></table></td></tr>
<tr><td bgcolor="%s" style="background:%s;padding:12px 22px 27px;text-align:center">
<table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td bgcolor="%s" style="background:%s;border-radius:30px">
<a href="%s" style="display:inline-block;padding:14px 26px;color:#FFFFFF;font:700 14px %s;text-decoration:none">Read the full briefing &#8594;</a></td></tr></table>
<div style="font-size:12px;line-height:1.6;color:%s;margin-top:12px">Read all %d stories, their source links and deeper analysis on the website.</div>
</td></tr>
<tr><td bgcolor="#11154A" style="background:#11154A;border-radius:0 0 16px 16px;padding:18px 24px;color:#D6D4E8;font-size:11px;line-height:1.6">
AI Marketing Daily · Curated by Carrie Hui<br>
Internal agency briefing · Headlines link to the online edition.<br>
%s
</td></tr>
</table></td></tr></table></body></html>''' % (
    esc(SUBJECT), PAPER, FONT, esc(preheader), PAPER, PAPER,
    NAVY, NAVY, LIME, LIME, esc(DATE), len(ITEMS),
    PAPER, PAPER, VIOLET, INK, esc(thesis), MUTED,
    PAPER, PAPER, INK, MUTED, stories_html,
    PAPER, PAPER, VIOLET, INK, actions_html,
    PAPER, PAPER, VIOLET, VIOLET, site_link, FONT, MUTED, len(ITEMS),
    esc(DATE))
assert len(doc.encode("utf-8")) < 102400, "EDM HTML too large"
(OUT / "team.html").write_text(doc, encoding="utf-8")
(OUT / "subject.txt").write_text(SUBJECT + "\n", encoding="utf-8")
payload = {
    "edition_date": TODAY,
    "language": "en",
    "subject": SUBJECT,
    "headline_count": len(ITEMS),
    "featured_count": len(picked),
    "html": doc,
}
(OUT / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print("Generated English team EDM: %s, %d featured of %d" % (TODAY, len(picked), len(ITEMS)))
