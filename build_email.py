# -*- coding: utf-8 -*-
"""Build the daily EDM (email newsletter) from the SAME data.json that powers the
website, so the morning email always matches the site with zero re-keying.

Design = the approved "AI Marketing Daily" EDM: editorial jade palette, table-only
layout, inline styles (survives Gmail head-stripping), bulletproof CTA, hidden
preheader, responsive + dark-mode. English-first (uses *_en fields; falls back to
Chinese if an _en field is missing).

Picks the top N items per section (default 2 — the routine puts the strongest
first in each section), so the email stays a ~2-minute skim while the site holds
the full list.

Outputs, next to data.json:
  email.html          -> pass to `mia-self email --html --body-file email.html`
  email-subject.txt   -> the subject line (single line)

Run:  PYTHONIOENCODING=utf-8 python3 build_email.py [picks_per_section]
      (or set EDM_PICKS_PER_SECTION=3)
"""
import json, html, re, sys, os
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data.json"

try:
    data = json.loads(DATA.read_text(encoding="utf-8"))
except FileNotFoundError:
    sys.exit(f"ERROR: {DATA} not found — run build.py's data.json step first.")
except json.JSONDecodeError as e:
    sys.exit(f"ERROR: data.json invalid JSON near line {e.lineno}: {e}")

# how many items per section to feature in the email
try:
    PICKS = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("EDM_PICKS_PER_SECTION", "2"))
except ValueError:
    PICKS = 2
PICKS = max(1, PICKS)

SITE_URL      = data.get("site_url", "https://carriehw.github.io/ai-marketing-daily/")
SITE_TITLE_EN = data.get("site_title_en", "AI Marketing Daily")
TAGLINE       = data.get("site_tagline", "AI Marketing Intelligence · HK / CN")
DATE_EN       = data.get("date_display_en", data.get("date_display", ""))
DATE_ISO      = data.get("date", "")
sections      = data.get("sections", [])
sections_en   = data.get("sections_en", [])

# action tag (zh) -> (pill bg colour, English label)
ACT = {
    "可即用":   ("#1E8E5A", "Ready to use"),
    "要留意":   ("#2F6DB0", "Worth watching"),
    "影響生意": ("#C4622D", "Business impact"),
}
REG_EN = {"國際": "Global", "中國": "China", "香港": "HK"}

# palette
PAPER, CARD, INK, MUTED, JADE, JADE_D, LINE = (
    "#F6F7F4", "#FFFFFF", "#1A2A2E", "#5E6E6A", "#0E7C66", "#0A5C4C", "#DBE2D9")
SANS = ("-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,"
        "'PingFang HK','Microsoft JhengHei',sans-serif")
SERIF = "Georgia,'Times New Roman',serif"

def esc(s):
    return html.escape("" if s is None else str(s))

def pick(it, en_key, zh_key):
    return it.get(en_key) or it.get(zh_key) or ""

# group items in the fixed section order
groups = {s: [] for s in sections}
for it in data.get("items", []):
    groups.setdefault(it.get("section", ""), []).append(it)

sec_en = {s: (sections_en[i] if i < len(sections_en) else s) for i, s in enumerate(sections)}

featured = []  # (section_zh, [items])
for s in sections:
    picks = groups.get(s, [])[:PICKS]
    if picks:
        featured.append((s, picks))
picked_count = sum(len(v) for _, v in featured)
total = len(data.get("items", []))

# ---- item block -------------------------------------------------------------
def item_block(it, is_last):
    act = it.get("action", "要留意")
    bg, act_en = ACT.get(act, ("#2F6DB0", "Worth watching"))
    reg_en = REG_EN.get(it.get("region", ""), esc(it.get("region", "")))
    url = esc(it.get("url", SITE_URL))
    title = esc(pick(it, "title_en", "title"))
    summary = esc(pick(it, "summary_en", "summary"))
    why = esc(pick(it, "why_en", "why"))
    border = "" if is_last else f"border-bottom:1px solid {LINE};"
    pad = "padding:14px 0 0 0;" if is_last else "padding:14px 0 18px 0;"
    return f'''<div style="{pad}{border}">
  <span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:700;color:#FFFFFF;background-color:{bg};border-radius:999px;padding:3px 10px;margin-right:6px;">{esc(act_en)}</span>
  <span class="region-pill" style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:600;color:{MUTED};border:1px solid {LINE};border-radius:999px;padding:2px 10px;">{reg_en}</span>
  <div class="item-title" style="margin-top:10px;font-family:{SANS};font-size:16px;font-weight:700;line-height:1.35;">
    <a href="{url}" target="_blank" style="color:{INK};text-decoration:none;" class="ink">{title}</a>
  </div>
  <p style="margin:7px 0 0 0;font-family:{SANS};font-size:13.5px;line-height:1.5;color:#3C4B47;" class="ink">{summary}</p>
  <p style="margin:8px 0 0 0;font-family:{SANS};font-size:12.5px;line-height:1.45;color:{MUTED};" class="muted"><strong style="color:{JADE_D};" class="jade-text">Why it matters:</strong> {why}</p>
</div>'''

# ---- section block ----------------------------------------------------------
def section_block(idx, sec_zh, items):
    head = f'''<tr>
  <td class="card px" style="background-color:{CARD};padding:16px 32px 4px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};border-top:1px solid {LINE};">
    <div style="font-family:{SERIF};font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:{JADE_D};" class="jade-text">{idx:02d} &mdash; {esc(sec_en.get(sec_zh, sec_zh))}</div>
  </td>
</tr>'''
    blocks = "\n".join(item_block(it, i == len(items) - 1) for i, it in enumerate(items))
    body = f'''<tr>
  <td class="card px" style="background-color:{CARD};padding:4px 32px 8px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};">
{blocks}
  </td>
</tr>'''
    return head + "\n" + body

sections_html = "\n".join(
    section_block(i + 1, s, items) for i, (s, items) in enumerate(featured))

# ---- preheader (hidden preview text) ----------------------------------------
pre_titles = []
for _, items in featured:
    for it in items:
        pre_titles.append(pick(it, "title_en", "title").split(":")[0].strip())
        break
preheader = "Today's AI marketing intel: " + "; ".join(pre_titles[:3]) + " & more."
preheader = esc(preheader[:150])

def cta(label="Read the full briefing &rarr;"):
    return f'''<table role="presentation" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td align="center" bgcolor="{JADE}" style="background-color:{JADE};border-radius:8px;" class="hover-cta">
      <a href="{esc(SITE_URL)}" target="_blank" class="cta-a" style="display:inline-block;font-family:{SANS};font-size:15px;font-weight:700;color:#FFFFFF;text-decoration:none;padding:14px 30px;border-radius:8px;background-color:{JADE};">{label}</a>
    </td>
  </tr>
</table>'''

legend = f'''<tr>
  <td class="card px" style="background-color:#F1F5F1;padding:18px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};border-top:1px solid {LINE};">
    <div style="font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{MUTED};margin-bottom:10px;" class="muted">How to read the labels</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="padding:3px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:700;color:#FFFFFF;background-color:#1E8E5A;border-radius:999px;padding:3px 10px;">Ready to use</span><span style="font-family:{SANS};font-size:12.5px;color:#3C4B47;" class="ink">&nbsp; Actionable now &mdash; a tool or tactic you can apply today.</span></td></tr>
      <tr><td style="padding:3px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:700;color:#FFFFFF;background-color:#2F6DB0;border-radius:999px;padding:3px 10px;">Worth watching</span><span style="font-family:{SANS};font-size:12.5px;color:#3C4B47;" class="ink">&nbsp; An emerging trend to keep on the radar.</span></td></tr>
      <tr><td style="padding:3px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:700;color:#FFFFFF;background-color:#C4622D;border-radius:999px;padding:3px 10px;">Business impact</span><span style="font-family:{SANS};font-size:12.5px;color:#3C4B47;" class="ink">&nbsp; A shift with direct commercial consequences.</span></td></tr>
    </table>
  </td>
</tr>'''

sources_note_en = esc(data.get("sources_note_en", data.get("sources_note", "")))
# keep footer source line short — first ~200 chars
if len(sources_note_en) > 220:
    sources_note_en = sources_note_en[:217] + "&hellip;"

page = f'''<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>{esc(SITE_TITLE_EN)} &middot; {esc(DATE_ISO)}</title>
  <style>
    body {{ margin:0; padding:0; width:100% !important; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
    table {{ border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt; }}
    img {{ border:0; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; }}
    a {{ text-decoration:none; }}
    .hover-cta:hover {{ background-color:{JADE_D} !important; }}
    .item-title a:hover {{ color:{JADE_D} !important; }}
    @media only screen and (max-width:620px) {{
      .container {{ width:100% !important; }}
      .px {{ padding-left:20px !important; padding-right:20px !important; }}
      .stack {{ display:block !important; width:100% !important; }}
      .masthead-date {{ display:block !important; padding-top:6px !important; text-align:left !important; }}
    }}
    @media (prefers-color-scheme:dark) {{
      body, .bg-paper {{ background-color:#0F1715 !important; }}
      .card {{ background-color:#16211E !important; }}
      .ink {{ color:#EDF2EE !important; }}
      .muted {{ color:#A9B8B2 !important; }}
      .jade-text {{ color:#5FCBAE !important; }}
      .region-pill {{ color:#A9B8B2 !important; border-color:#3A4A45 !important; }}
      .footer-bg {{ background-color:#0B1210 !important; }}
    }}
  </style>
</head>
<body class="bg-paper" style="margin:0;padding:0;background-color:{PAPER};">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{PAPER};opacity:0;">{preheader}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="bg-paper" style="background-color:{PAPER};width:100%;">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" class="container" style="width:600px;max-width:600px;">

          <tr><td style="height:4px;line-height:4px;font-size:4px;background-color:{JADE};">&nbsp;</td></tr>

          <!-- Masthead -->
          <tr>
            <td class="card px" style="background-color:{CARD};padding:26px 32px 18px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr><td style="font-family:{SERIF};font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{MUTED};" class="muted">{esc(TAGLINE)}</td></tr>
                <tr><td style="padding-top:6px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
                    <td class="stack" valign="bottom" style="font-family:{SERIF};font-size:30px;font-weight:700;line-height:1.15;color:{INK};"><span class="brandmark ink">{esc(SITE_TITLE_EN)}</span></td>
                    <td class="stack masthead-date" valign="bottom" align="right" style="font-family:{SANS};font-size:13px;color:{MUTED};white-space:nowrap;"><span class="muted">{esc(DATE_EN)}</span></td>
                  </tr></table>
                </td></tr>
                <tr><td style="padding-top:10px;">
                  <span style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:600;color:{JADE};background-color:#EAF4F0;border:1px solid #CDE6DD;border-radius:999px;padding:4px 12px;" class="jade-text">{total} picks today</span>
                </td></tr>
              </table>
            </td>
          </tr>

          <!-- Intro + CTA -->
          <tr>
            <td class="card px" style="background-color:{CARD};padding:8px 32px 26px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};">
              <p style="margin:0 0 18px 0;font-family:{SANS};font-size:15px;line-height:1.55;color:{INK};" class="ink">A tight morning read on how AI is reshaping search, ad platforms, creative production and the China market &mdash; {picked_count} hand-picked stories that actually move the needle.</p>
              {cta()}
              <p style="margin:14px 0 0 0;font-family:{SANS};font-size:12px;line-height:1.5;color:{MUTED};" class="muted">Read it in English or &#20013;&#25991; &mdash; toggle at the top right of the site.</p>
            </td>
          </tr>

{sections_html}

          {legend}

          <!-- Secondary CTA -->
          <tr>
            <td class="card px" align="center" style="background-color:{CARD};padding:24px 32px 26px 32px;border-left:1px solid {LINE};border-right:1px solid {LINE};border-top:1px solid {LINE};">
              {cta()}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td class="footer-bg px" style="background-color:{INK};padding:26px 32px 30px 32px;border-radius:0 0 4px 4px;">
              <p style="margin:0 0 10px 0;font-family:{SANS};font-size:11.5px;line-height:1.55;color:#AEBFBA;">Sources: {sources_note_en}</p>
              <p style="margin:0 0 4px 0;font-family:{SERIF};font-size:13px;font-weight:700;color:#FFFFFF;">Curated by Mia &middot; {esc(SITE_TITLE_EN)}</p>
              <p style="margin:0 0 12px 0;font-family:{SANS};font-size:11.5px;line-height:1.5;color:#8CA39D;">For informational reference only. &nbsp;&middot;&nbsp; <a href="{esc(SITE_URL)}" target="_blank" style="color:#5FCBAE;text-decoration:underline;">{esc(SITE_URL.replace("https://","").rstrip("/"))}</a></p>
              <p style="margin:0;font-family:{SANS};font-size:11px;line-height:1.5;color:#6E827C;">You are receiving this briefing as part of the AI Marketing Daily distribution. To adjust your subscription, reply to this email.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
'''

(ROOT / "email.html").write_text(page, encoding="utf-8")
subject = f"[AI Marketing Daily] {DATE_EN} · Top picks across {len(featured)} sections ({total} today)"
(ROOT / "email-subject.txt").write_text(subject + "\n", encoding="utf-8")

print(f"OK email.html  featured={picked_count} (picks/section={PICKS})  total={total}")
print("SUBJECT:", subject)
