# -*- coding: utf-8 -*-
"""Build the daily EDM (email newsletter) from the SAME data.json that powers the
website, so the morning email always matches the site with zero re-keying.

Design = the SAME design system as the website (`build.py`), re-expressed in
email-safe HTML: table-only layout, inline styles (survives Gmail head-stripping),
bulletproof CTA, hidden preheader, responsive + dark-mode. English-first (uses
*_en fields; falls back to Chinese if an _en field is missing).

The palette, the signal badges, the five category colours, the followup block and
the "why it matters" block are all lifted from build.py's :root — not approximated.
Two things cannot cross into email and are handled, not ignored:

  * Webfonts. The site embeds Inter + IBM Plex Mono as data-URI @font-face.
    Gmail strips <style> and no major client honours an embedded webfont, so the
    email asks for Inter by NAME and falls back to the system sans. A reader with
    Inter installed sees the site's exact face; everyone else sees their system
    UI font at the same sizes and weights. The site has NO serif anywhere, so the
    email has none either (it used to open on a Georgia masthead).
  * Gradients. The site's dark identity zone is a 4-stop gradient. Outlook/Word
    renders no CSS gradient, so the masthead carries bgcolor="#11154a" (the
    gradient's navy stop) underneath the gradient — Outlook gets flat navy,
    everyone else gets the site's gradient.

Picks the top N items per section (default 2 — the routine puts the strongest
first in each section), so the email stays a ~2-minute skim while the site holds
the full list.

Outputs, next to data.json:
  email.html          -> pass to `mia-self email --html --body-file email.html`
  email-subject.txt   -> the subject line (single line)

Run (from a folder that has data.json, e.g. the routine's work dir):
      PYTHONIOENCODING=utf-8 python3 build_email.py
Options:
      python3 build_email.py 3                 # 3 items per section (positional)
      python3 build_email.py --picks 3
      python3 build_email.py --data path/to/data.json --out path/to/outdir
      (or set EDM_PICKS_PER_SECTION=3)
"""
import json, html, re, sys, os, argparse, hashlib, math, urllib.parse
from pathlib import Path
from datetime import datetime


def _canon_dates(iso, zh_fallback="", en_fallback=""):
    """Derive the display dates from the ISO date so the weekday in the subject
    line is never hand-mis-typed. Falls back to data.json values if invalid."""
    try:
        d = datetime.strptime((iso or "").strip(), "%Y-%m-%d")
        wk_zh = ["一", "二", "三", "四", "五", "六", "日"][d.weekday()]
        zh = f"{d.year}年{d.month}月{d.day}日 · 星期{wk_zh}"
        en = f"{d.strftime('%B')} {d.day}, {d.year} · {d.strftime('%A')}"
        return zh, en
    except Exception:
        return (zh_fallback or ""), (en_fallback or zh_fallback or "")

_ap = argparse.ArgumentParser(description="Build the daily EDM email from data.json")
_ap.add_argument("--data", help="path to data.json (default: ./data.json, then the script's own folder)")
_ap.add_argument("--out", help="output directory for email.html / email-subject.txt (default: data.json's folder)")
_ap.add_argument("--picks", type=int, help="items featured per section")
_ap.add_argument("picks_pos", nargs="?", type=int, help=argparse.SUPPRESS)  # backward-compat positional
_args = _ap.parse_args()

# resolve data.json: explicit --data, else cwd/data.json, else beside this script
_here = Path(__file__).parent
if _args.data:
    DATA = Path(_args.data)
elif (Path.cwd() / "data.json").is_file():
    DATA = Path.cwd() / "data.json"
else:
    DATA = _here / "data.json"

try:
    data = json.loads(DATA.read_text(encoding="utf-8"))
except FileNotFoundError:
    sys.exit(f"ERROR: data.json not found at {DATA} — pass --data or run from the folder that has it.")
except json.JSONDecodeError as e:
    sys.exit(f"ERROR: data.json invalid JSON near line {e.lineno}: {e}")

OUT = Path(_args.out) if _args.out else DATA.parent

# how many items per section to feature in the email
PICKS = _args.picks or _args.picks_pos or int(os.environ.get("EDM_PICKS_PER_SECTION", "2"))
PICKS = max(1, PICKS)

SITE_URL      = data.get("site_url", "https://carriehw.github.io/ai-marketing-daily/")

def _with_lang(u, lang="en"):
    """Force the landing language of the site from the email link, so a reader
    whose browser remembers Chinese still lands on the English briefing."""
    sep = "&" if "?" in u else "?"
    return f"{u}{sep}lang={lang}"

SITE_URL_EN = _with_lang(SITE_URL, "en")

# ---------------------------------------------------------------------------
# Per-story deep links: read the anchors OUT of index.html, never recompute them.
#
# build.py gives every card a content-derived id (`story_slug`, build.py:229) so a
# shared link keeps pointing at the story the reader saw. The email wants those same
# ids, and the obvious move — copy story_slug() over here — is the wrong one:
#
#   build.py binds `_STOP` TWICE. Line 225 defines the 23-word list story_slug's
#   docstring describes; line 464 REBINDS the same name to an 81-word
#   de-duplication list. story_slug is not called until line 1056, so at call time
#   it reads the SECOND list. A faithful copy of the function plus its documented
#   stopword list reproduces only 12 of 17 live anchors — the five that differ are
#   the ones whose titles contain a word like "ai"/"open"/"model" that only the
#   second list strips. Links still resolve (the resolver keys on the 6-hex URL
#   suffix), so the divergence is invisible until something compares strings.
#
# Parsing index.html costs one regex and cannot fork, because it is the output of
# whatever story_slug actually did this morning. If index.html is absent (email
# built before the site, or standalone), every link falls back to the section-level
# site URL — degraded, never wrong.
_ANCHORS = {}
_idx = OUT / "index.html"
if _idx.is_file():
    _html = _idx.read_text(encoding="utf-8", errors="replace")
    for _m in re.finditer(r'id="([a-z0-9][a-z0-9-]*-[0-9a-f]{6})"', _html):
        _ANCHORS.setdefault(_m.group(1).rsplit("-", 1)[1], _m.group(1))

def _norm_url(u):
    """Same normalisation story_slug hashes: host without www, path without a
    trailing slash. This is the half that is stable across a reworded headline."""
    p = urllib.parse.urlsplit(str(u or ""))
    return (p.netloc.lower().replace("www.", "") + p.path.rstrip("/")).encode()

# ---------------------------------------------------------------------------
# Campaign tagging. Without it the site counter files every email reader under
# "Direct" and the EDM cannot be told apart from someone opening the bookmark,
# so there is no way to answer "did anyone read it".
#
# Parameter names are not a matter of taste here — they are whatever the site's
# counter actually reads. Verified against the counter's own source and its
# client script on 2026-10-15:
#   - referrer comes from the FIRST of utm_source / ref / src / source
#   - campaign  comes from utm_campaign or campaign
#   - both are stripped from the stored path, so they do not fragment the page
#     into ten separate rows (hit.go, "Remove various tracking query parameters")
#
# Two measured constraints shape the format:
#
#   1. The query must come BEFORE the #anchor. A fragment is never sent to the
#      server at all — the client script builds its payload from
#      location.pathname + location.search, and location.hash appears nowhere in
#      it. "...#slug?utm_source=edm" would make the params part of the fragment:
#      invisible to the counter AND a broken anchor.
#   2. The site sets <link rel="canonical"> to itself, and the client prefers a
#      same-host canonical for the path it reports — so the path arrives WITHOUT
#      the query. The params still register, because the script sends
#      location.search separately as its own field, which is the field the
#      campaign is parsed from. Probed both branches to confirm rather than
#      inferring it: same-host canonical -> path "/ai-marketing-daily/",
#      search "?utm_source=edm&utm_campaign=..." sent intact.
# Read from `data` rather than DATE_ISO: that constant is bound further down
# (line ~183), so referencing it here is a NameError at import time.
#
# The adversarial no-date build exposed a split brain: the campaign id said
# "ai-daily-undated" while the subject still printed "October 14, 2026",
# because the subject recovers the date from date_display_en and this did not.
# One missing field must not yield two different answers about what day it is,
# so the campaign id uses the same recovery chain, and only says "undated" when
# no field anywhere carries a date.
def _campaign_date():
    iso = str(data.get("date", "")).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
        return iso
    for key in ("date_display_en", "date_display"):
        m = re.search(r"(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})",
                      str(data.get(key, "")))
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", str(data.get(key, "")))
        if m:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}",
                                         "%B %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
    return "undated"

_CAMPAIGN = "ai-daily-" + _campaign_date()

def _tag(url, content):
    """Append campaign params before any #fragment. `content` says WHICH link was
    clicked, so a headline click is distinguishable from the footer CTA."""
    frag = ""
    if "#" in url:
        url, frag = url.split("#", 1)
        frag = "#" + frag
    sep = "&" if "?" in url else "?"
    q = urllib.parse.urlencode({
        "utm_source": "edm",
        "utm_medium": "email",
        "utm_campaign": _CAMPAIGN,
        "utm_content": content,
    })
    return f"{url}{sep}{q}{frag}"

def site_link(it, content="headline"):
    """Deep link to this story ON THE SITE, or the site itself if no anchor exists."""
    suf = hashlib.sha1(_norm_url(it.get("url"))).hexdigest()[:6]
    slug = _ANCHORS.get(suf)
    return _tag(f"{SITE_URL_EN}#{slug}" if slug else SITE_URL_EN, content)

SITE_TITLE_EN = data.get("site_title_en", "AI Marketing Daily")
TAGLINE       = data.get("site_tagline", "AI Marketing Intelligence · HK / CN")
DATE_ISO      = data.get("date", "")
# Recompute the display dates from the ISO date — never trust a hand-written
# weekday (that's what put "July 21 · Monday" on a 22nd-Wednesday email).
_zh_d, DATE_EN = _canon_dates(DATE_ISO,
                              data.get("date_display", ""),
                              data.get("date_display_en", data.get("date_display", "")))
# Subject-line date: no weekday at all (Carrie's choice — keep the date, drop the
# weekday so no day-name can ever be wrong in the title). e.g. "July 22, 2026".
try:
    _sd = datetime.strptime((DATE_ISO or "").strip(), "%Y-%m-%d")
    DATE_SUBJECT = f"{_sd.strftime('%B')} {_sd.day}, {_sd.year}"
except Exception:
    DATE_SUBJECT = DATE_EN.split(" · ")[0] if DATE_EN else ""
sections      = data.get("sections", [])
sections_en   = data.get("sections_en", [])
# Hero copy — same keys and same defaults as build.py, so the email opens on the
# masthead the reader knows from the site instead of a separate intro paragraph.
HEADLINE_EN   = data.get("headline_en", "Less AI noise.\nMore marketing signal.")
STANDFIRST_EN = data.get(
    "standfirst_en",
    "Every morning. Each story answers three things: what happened, why it "
    "matters to marketers, and whether to act today.")
BYLINE        = data.get("byline", "Carrie Hui")
BYLINE_ROLE_EN = data.get("byline_role_en",
                          "AI Marketing Strategist \u00b7 Travel Retail & Greater China")
READ_MIN      = data.get("read_minutes") or max(3, round(len(data.get("items", [])) * 0.5))
# READ_MIN above is the SITE's number: it scales with all items and assumes the
# reader opens the summaries and the expandable detail. This email is now
# headlines plus one line each — measured at ~670 words, i.e. about 3 minutes.
# Printing the site's 8 minutes on it overstates the ask roughly fourfold, and a
# number in the hero gets read as a promise about THIS email. So the chip gets
# its own figure, derived from what the email actually contains: one headline
# plus one WHY line per featured story, ~45 words per card, at 220 wpm.
#
# The "Every story sourced" chip was removed rather than reworded. It is true of
# the data and it was true of the old email, which linked to each original; this
# email links only to the site, so the chip advertises something the reader
# cannot reach from here. The source names still appear in the footer, and the
# site carries the per-story links.

# ---------------------------------------------------------------------------
# DESIGN TOKENS — copied from build.py's :root, same hex values, same roles.
# If you change one here, change it there; the point of this block is that the
# email and the site are one design, not two that look similar.
# ---------------------------------------------------------------------------
PAPER, CARD, INK, MUTED, BODY, LINE = (
    "#F7F5EF", "#FFFFFF", "#101114", "#656A73", "#3C3F45", "#DEDBD2")
ACCENT, ACCENT_D, ACCENT_SOFT = "#5A42F4", "#4632D4", "#EBE8FF"
# the dark identity zone: gradient stops + the on-dark text layers
I_VIOLET, I_BLUE, I_NAVY, I_PLUM, LIME = (
    "#553FBA", "#2F5582", "#11154A", "#7D266B", "#D3FE66")
ON_DARK, ON_DARK_2, ON_DARK_CHIP = "#F7F5EF", "#D6D4E8", "#EDEBF6"
GREEN, AMBER = "#1D7656", "#A25900"

# Signal badges: tinted background + coloured text, exactly as the site renders
# them (.signal.act / .watch / .impact). The old email used white-on-solid, which
# read as three loud buttons; the site's version is a label, and the traffic-light
# encoding (green / amber / violet) is deliberately OUTSIDE the category hue arc.
ACT = {
    "可即用":   ("#E2F3EC", GREEN,  "Ready to use"),
    "要留意":   ("#FDF3E2", AMBER,  "Worth watching"),
    "影響生意": (ACCENT_SOFT, ACCENT, "Business impact"),
}
REG_EN = {"國際": "Global", "中國": "China", "香港": "HK"}

# Five category colours — (solid, tint, text). Solid = section header bg + the
# card's 5px top border; text = the source pill's colour. Site uses --cNt rather
# than --cN for pill text because the solid hue on its own tint only reaches
# 4.34–4.56:1 at 12px, under AA.
CATS = [
    ("#39689F", "#D9E6F6", "#2C619E"),
    ("#3F5BC8", "#D9DFF6", "#2F4EC7"),
    ("#6249D7", "#DED9F6", "#5438D6"),
    ("#9A3A9E", "#F5D9F6", "#972D9C"),
    ("#7D266B", "#F6D9F0", "#7D266B"),
]
# Emoji + one-line description per section, same source as build.py's _SEC_DEFAULTS.
SEC_META = {
    "AI 大模型 & 市場動態": ("\U0001F9E0", "The biggest moves in AI this morning."),
    "廣告平台 & 行銷科技": ("\U0001F4E3", "Platform rules, ad products and martech shifts."),
    "創意生產工具":       ("\U0001F3AC", "New tools and features for creative output."),
    "行業影響 & 品牌案例": ("\U0001F4C8", "Agency landscape, client moves and brand cases."),
    "即學技巧 & 玩法":     ("\u26A1", "Concrete plays you can try today."),
}


def _norm_sec(s):
    """Match section names ignoring spaces and full/half-width punctuation.

    Same guard build.py carries: data.json once shipped "AI大模型 & 市場動態"
    against a key written "AI 大模型 & 市場動態" — one space apart. The lookup
    missed silently and the section rendered with no description and a generic
    pin. A missing emoji is cosmetic; a missing description is a visibly emptier
    header than the other four, with no error to say why.
    """
    return re.sub(r"[\s\u3000&＆·・\-—]+", "", str(s or ""))

_SEC_META_N = {_norm_sec(k): v for k, v in SEC_META.items()}

# Fonts. No @font-face: Gmail strips <style>, and no major client loads an
# embedded webfont. So name Inter first — readers who have it (the site installs
# nothing, but designers and Mac users often do) get the site's exact face, and
# everyone else lands on their system UI sans at the same size and weight. The
# CJK fallbacks mirror build.py's stack so a Chinese fallback string renders in
# the same family the site would use.
SANS = ("Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
        "Arial,'Noto Sans TC','PingFang TC','PingFang HK','Microsoft JhengHei',sans-serif")
# Tabular numerals for counts and the section index, matching the site's use of
# IBM Plex Mono for exactly those.
MONO = ("'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace")

def esc(s):
    return html.escape("" if s is None else str(s))

def pick(it, en_key, zh_key):
    return it.get(en_key) or it.get(zh_key) or ""

# group items in the fixed section order
# build.py splits the headline on a literal "\n" into two display lines; the
# email does the same with <br> so the line break lands in the same place.
headline_html = "<br>".join(esc(l) for l in str(HEADLINE_EN).split("\n") if l.strip())

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

# The reading-time chip is a promise, so it is measured, not estimated.
#
# Two earlier attempts were both wrong in the same way: they added a per-card
# word count to a CHROME_WORDS constant. Chrome is not constant — the legend
# carries one row per category and the intro sentence changes with the
# remainder, so a constant calibrated on the ten-story issue under-promised on
# the one-story issue (measured 1.11 min, chip said 1) and no single value fixes
# both. The constant was the wrong instrument.
#
# Instead the page is rendered with a placeholder here, its visible text is
# counted after assembly, and the number is stamped in. See READ_TIME below.
EMAIL_READ_MIN = "@@READMIN@@"

# ---- item block -------------------------------------------------------------
# One story = one card, mirroring the site's .story: a 5px top border in the
# section colour, the source pill in that colour's text tone, then title /
# followup / summary / why-it-matters in that order. The site's own note applies
# here — exactly three type sizes inside a card and one label style, so the eye
# has a hierarchy instead of five competing levels.
def item_block(it, cat, is_last, is_lead=False):
    """One story, trimmed to the two things an email can carry: the headline and
    the one line that says why it matters. Everything deeper — the summary, the
    Since-yesterday delta, the original link — stays on the site, which is where
    the title now sends the reader (`site_link`, anchored to that exact card).

    What was removed and why, so a later edit does not restore it by accident:
      - summary (216 chars) and followup: the email became a scroll, not a scan
      - source pill + paywall badge: both describe the ORIGINAL article, and the
        email no longer links to it; the source names still appear in the footer
      - "Read original" button: the title is the link, and it goes to the site
      - the "WHY IT MATTERS" label on every card: once the WHY line became the
        only body copy, the label stopped distinguishing anything — ten identical
        uppercase lines, ~20px each. It survives on the lead card only, where it
        still does work: it teaches the reader what the violet block means, so
        the nine unlabelled ones that follow read correctly.

    is_lead marks the day's first story (first item of the first section — the
    same item the site treats as the lead; see the subject-line note below).
    It gets a larger headline, a larger WHY line and an eyebrow, so the issue
    opens on a story instead of on ten equal-weight cards.
    """
    solid, tint, ctext = cat
    act = it.get("action", "要留意")
    a_bg, a_fg, act_en = ACT.get(act, (ACCENT_SOFT, ACCENT, "Worth watching"))
    reg_en = REG_EN.get(it.get("region", ""), esc(it.get("region", "")))
    href = esc(site_link(it))
    title = esc(pick(it, "title_en", "title"))
    why = esc(pick(it, "why_en", "why"))
    # The WHY line is now the only body text on the card, so an item that arrives
    # without one must not render an empty violet box — the adversarial no-why
    # build produced exactly that (2 hollow shells). Omit the box; the title and
    # the deep link still carry the story.
    # Lead card: one step up in size, not a different design. Same card shell,
    # same colours, same two elements — a reader scanning sees weight, not a
    # second layout to learn.
    t_size, w_size, pad = ("19.5px", "14.5px", "18px 20px 16px 20px") if is_lead \
        else ("16.5px", "13.5px", "16px 20px 15px 20px")
    why_label = (f'''<div style="font-family:{SANS};font-size:10.5px;font-weight:800;letter-spacing:1.1px;text-transform:uppercase;color:{ACCENT};padding-bottom:3px;" class="accent-text">Why it matters</div>'''
                 if is_lead else "")
    eyebrow = (f'''<div style="font-family:{SANS};font-size:10.5px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:{solid};padding-bottom:6px;">Today&rsquo;s lead</div>'''
               if is_lead else "")
    why_box = (f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:10px 0 0 0;"><tr>
    <td style="border-left:3px solid {ACCENT};background-color:{ACCENT_SOFT};padding:10px 14px;" class="take-box">
      {why_label}<div style="font-family:{SANS};font-size:{w_size};line-height:1.58;color:{INK};" class="ink">{why}</div>
    </td>
  </tr></table>''' if why.strip() else "")
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 12px 0;">
 <tr><td bgcolor="{CARD}" class="card" style="background-color:{CARD};border:1px solid {LINE};border-top:5px solid {solid};border-radius:16px;padding:{pad};">
  {eyebrow}<div class="item-title" style="font-family:{SANS};font-size:{t_size};font-weight:700;line-height:1.32;letter-spacing:-.3px;">
    <a href="{href}" target="_blank" style="color:{INK};text-decoration:none;" class="ink">{title}</a>
  </div>
  {why_box}
  <div style="padding-top:10px;">
    <span style="display:inline-block;font-family:{SANS};font-size:11.5px;font-weight:800;color:{a_fg};background-color:{a_bg};border-radius:999px;padding:4px 11px;margin-right:6px;">{esc(act_en)}</span>
    <span class="region-pill" style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:600;color:{MUTED};border:1px solid {LINE};border-radius:999px;padding:3px 9px;">{reg_en}</span>
  </div>
 </td></tr>
</table>'''

# ---- section block ----------------------------------------------------------
# The site puts each category behind a solid colour bar carrying emoji, name,
# a one-line description and the item count. That bar IS the site's structure —
# it is what makes five sections scannable — so the email gets the same bar in
# the same colour, and the cards below inherit that colour as a 5px top border.
def section_block(idx, sec_zh, items, total_in_sec):
    solid, tint, ctext = CATS[(idx - 1) % len(CATS)]
    emoji, desc = _SEC_META_N.get(_norm_sec(sec_zh), ("", ""))
    desc_html = (f'<div class="sec-desc" style="font-family:{SANS};font-size:12.5px;'
                 f'line-height:1.45;color:{ON_DARK_CHIP};opacity:.9;'
                 f'padding-top:2px;">{esc(desc)}</div>'
                 if desc else "")
    emoji_cell = (f'<td valign="middle" style="font-size:20px;line-height:1;'
                  f'padding-right:11px;width:28px;">{emoji}</td>' if emoji else "")
    shown = len(items)
    count = (f"{shown} of {total_in_sec}" if shown < total_in_sec else f"{shown}")
    head = f'''<tr>
  <td class="bg-paper px" bgcolor="{PAPER}" style="padding:20px 24px 0 24px;background-color:{PAPER};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{solid}" style="background-color:{solid};border-radius:12px;">
      <tr>
        <td style="padding:13px 18px;" valign="middle">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
            {emoji_cell}
            <td valign="middle">
              <div style="font-family:{SANS};font-size:17px;font-weight:800;letter-spacing:-.4px;line-height:1.2;color:#FFFFFF;">{esc(sec_en.get(sec_zh, sec_zh))}</div>
              {desc_html}
            </td>
            <td valign="middle" align="right" style="font-family:{MONO};font-size:12px;font-weight:700;color:{ON_DARK_CHIP};white-space:nowrap;padding-left:10px;">{count}</td>
          </tr></table>
        </td>
      </tr>
    </table>
  </td>
</tr>'''
    blocks = "\n".join(
        item_block(it, (solid, tint, ctext), i == len(items) - 1,
                   is_lead=(idx == 1 and i == 0))
        for i, it in enumerate(items))
    body = f'''<tr>
  <td class="bg-paper px" bgcolor="{PAPER}" style="background-color:{PAPER};padding:14px 24px 0 24px;">
{blocks}
  </td>
</tr>'''
    return head + "\n" + body

# ---- "more on the site" line ------------------------------------------------
# She asked the email to say explicitly that the site carries more. The number is
# derived, never written by hand: total minus what this email actually featured.
# Singular/plural and the zero case are handled, because on a thin news day the
# email can feature everything and "0 more stories" would be a visible lie.
_rest = total - picked_count
rest_line = (f"{_rest} more {'story' if _rest == 1 else 'stories'} ran today, "
             f"all of {'it' if _rest == 1 else 'them'} there too."
             if _rest > 0 else
             "Every story that ran today is in this email.")

sections_html = "\n".join(
    section_block(i + 1, s, items, len(groups.get(s, [])))
    for i, (s, items) in enumerate(featured))

# ---- preheader (hidden preview text) ----------------------------------------
# The preheader is the third thing an inbox shows, after sender and subject, and
# it is the last line the reader sees before deciding to open. The old one
# repeated the lead headline the subject already carried, then hard-sliced at
# 150 characters mid-word ("...Blocks The Trade De").
#
# This version does the job the subject cannot: say what KIND of day it was and
# what the reader gets, in words that do not duplicate the subject. Built from
# the action tags already on each item, so it is derived from the issue rather
# than written fresh each morning by hand.
_acts = [it.get("action", "") for _, items in featured for it in items]
_ready = sum(1 for a in _acts if a == "可即用")
_impact = sum(1 for a in _acts if a == "影響生意")
_bits = []
if _impact: _bits.append(f"{_impact} with business impact")
if _ready:  _bits.append(f"{_ready} you can use today")
preheader = (f"{picked_count} picks, one line each on why it matters"
             + (" — " + " and ".join(_bits) if _bits else "")
             + f". {total - picked_count} more on the site." if total > picked_count
             else f"{picked_count} picks, one line each on why it matters.")
# Cut on a word boundary, never mid-word: 150 chars is roughly what the widest
# client shows, and a sliced word reads as a broken send.
if len(preheader) > 150:
    preheader = preheader[:150].rsplit(" ", 1)[0] + "…"
preheader = esc(preheader)

def cta(label="Read the full briefing &rarr;", content="cta-top"):
    """Bulletproof CTA in the site's accent violet. bgcolor on the <td> AND
    background-color on the <a> — Outlook ignores the latter, everything else
    needs it so the padded area is clickable. `content` tags the click so the
    top CTA, the bottom CTA and a headline are three separate numbers rather
    than one undifferentiated "someone clicked the email"."""
    return f'''<table role="presentation" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td align="center" bgcolor="{ACCENT}" style="background-color:{ACCENT};border-radius:999px;" class="hover-cta">
      <a href="{esc(_tag(SITE_URL_EN, content))}" target="_blank" class="cta-a" style="display:inline-block;font-family:{SANS};font-size:14.5px;font-weight:800;color:#FFFFFF;text-decoration:none;padding:13px 28px;border-radius:999px;background-color:{ACCENT};">{label}</a>
    </td>
  </tr>
</table>'''

legend = f'''<tr>
  <td class="bg-paper px" bgcolor="{PAPER}" style="background-color:{PAPER};padding:10px 24px 0 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{CARD}" style="background-color:{CARD};border:1px solid {LINE};border-radius:16px;" class="card">
      <tr><td style="padding:16px 18px;">
        <div style="font-family:{SANS};font-size:10.5px;font-weight:800;letter-spacing:1.1px;text-transform:uppercase;color:{MUTED};padding-bottom:9px;" class="muted">How to read the labels</div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td style="padding:3px 0;" class="stack"><span style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:800;color:{GREEN};background-color:#E2F3EC;border-radius:999px;padding:4px 11px;">Ready to use</span><span style="font-family:{SANS};font-size:12.5px;color:{BODY};" class="ink">&nbsp; try today / save time</span></td></tr>
          <tr><td style="padding:3px 0;" class="stack"><span style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:800;color:{AMBER};background-color:#FDF3E2;border-radius:999px;padding:4px 11px;">Worth watching</span><span style="font-family:{SANS};font-size:12.5px;color:{BODY};" class="ink">&nbsp; platform / trend shift</span></td></tr>
          <tr><td style="padding:3px 0;" class="stack"><span style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:800;color:{ACCENT};background-color:{ACCENT_SOFT};border-radius:999px;padding:4px 11px;">Business impact</span><span style="font-family:{SANS};font-size:12.5px;color:{BODY};" class="ink">&nbsp; agency / client / compliance</span></td></tr>
        </table>
      </td></tr>
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
  <!--[if mso]>
  <style>
    /* Outlook/Word renders no border-radius and no CSS gradient. Pills become
       rectangles there, which is fine; what is NOT fine is a dark masthead with
       no background at all, so every dark block also carries a bgcolor attribute. */
    table, td, div, p, a {{ font-family: Arial, sans-serif !important; }}
  </style>
  <![endif]-->
  <style>
    body {{ margin:0; padding:0; width:100% !important; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
    table {{ border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt; }}
    img {{ border:0; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; }}
    a {{ text-decoration:none; }}
    .hover-cta:hover {{ background-color:{ACCENT_D} !important; }}
    .cta-a:hover {{ background-color:{ACCENT_D} !important; }}
    .item-title a:hover {{ color:{ACCENT_D} !important; text-decoration:underline; text-underline-offset:3px; }}
    @media only screen and (max-width:620px) {{
      .container {{ width:100% !important; }}
      .px {{ padding-left:20px !important; padding-right:20px !important; }}
      .stack {{ display:block !important; width:100% !important; }}
      /* Mobile first screen. Measured on the 10-14 issue: the first story card
         started 523px down at phone width, so on a ~650px viewport the reader's
         opening view was masthead only — brand bar, 38px headline, standfirst,
         four chips, byline — and not one headline. The identity is already
         established by the sender name and the brand bar; repeating it at hero
         scale costs the reader their first story.

         So on phones the hero compresses rather than disappears: headline down
         to 25px, tighter vertical padding, and the two lowest-value blocks
         (standfirst, which paraphrases what the chips already say, and the
         byline, which the footer repeats verbatim) are hidden. Nothing unique
         to the issue is lost. Desktop keeps the full hero. */
      .h1 {{ font-size:25px !important; letter-spacing:-.9px !important; }}
      .hero-pad {{ padding-top:16px !important; padding-bottom:0 !important; }}
      .hero-head {{ padding-top:9px !important; }}
      .m-hide {{ display:none !important; max-height:0 !important;
                 overflow:hidden !important; mso-hide:all; }}
      .chips-pad {{ padding-top:11px !important; }}
      .intro-pad {{ padding-top:16px !important; padding-bottom:14px !important; }}
      /* The top CTA repeats the bottom CTA verbatim and costs 43px of the first
         screen; on a phone that is the difference between opening on a headline
         and opening on a button. Desktop keeps both. */
      .m-hide-cta {{ display:none !important; max-height:0 !important;
                     overflow:hidden !important; mso-hide:all; }}
      /* 12px of the remaining gap, from the only block above the fold carrying
         no content at all: the outer wrapper's top gutter — the margin between
         the client's chrome and the email. Desktop keeps 24px. */
      .outer-pad {{ padding-top:12px !important; }}
      /* The criterion that matters is "the first headline is READABLE above the
         fold", not "its block starts above the fold". Those differ by a line:
         with the gutter alone the block top reached 553px and the first line
         ended at 578px, so on iPhone SE Mail (~560px) the headline opened
         sliced through the middle — a screenshot caught what the block-top
         measurement called a pass.

         The remaining 18px comes from the section bar's description line, which
         wraps to two lines (38px) at phone width to say what the category name
         beside it already says ("Ad Platforms & MarTech" / "Platform rules, ad
         products and martech shifts"). It orients a reader scanning the whole
         site; it earns nothing in an email where the next thing is the story.
         Hiding it buys 38px against an 18px need, so the first line clears the
         fold with ~20px of margin rather than landing exactly on a budget that
         is itself approximate. Desktop keeps the description. */
      .sec-desc {{ display:none !important; max-height:0 !important;
                   overflow:hidden !important; mso-hide:all; }}
    }}
    /* Dark mode mirrors the site's ink/paper inversion rather than inventing a
       second palette: paper -> near-black ink, cards -> one step up, accent
       lightened only as much as it needs to clear the darker ground. */
    @media (prefers-color-scheme:dark) {{
      body, .bg-paper {{ background-color:#0C0D12 !important; }}
      .card {{ background-color:#15161C !important;
               border-right-color:#2A2C36 !important;
               border-bottom-color:#2A2C36 !important;
               border-left-color:#2A2C36 !important; }}
      .ink {{ color:#F2F0EA !important; }}
      .muted {{ color:#A3A7B2 !important; }}
      .accent-text {{ color:#AFA2FF !important; }}
      .take-box {{ background-color:#221C4A !important; border-left-color:#8B79FF !important; }}
      .region-pill {{ color:#A3A7B2 !important; border-color:#3A3D47 !important; }}
      .footer-bg {{ background-color:#07080C !important; }}
    }}
  </style>
</head>
<body class="bg-paper" style="margin:0;padding:0;background-color:{PAPER};">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{PAPER};opacity:0;">{preheader}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="bg-paper" style="background-color:{PAPER};width:100%;">
    <tr>
      <td align="center" class="outer-pad" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" class="container" style="width:600px;max-width:600px;">

          <!-- ============ Masthead: the site's dark identity zone ============
               The site runs a 135deg 4-stop gradient (violet -> blue -> navy ->
               plum). Outlook renders no gradient, so bgcolor="{I_NAVY}" sits
               underneath as a flat fallback — the navy stop, which is the one
               the on-dark text layers were contrast-checked against. Lime is the
               site's eyebrow accent and stays lime here. -->
          <tr>
            <td bgcolor="{I_NAVY}" style="background-color:{I_NAVY};background-image:linear-gradient(135deg,{I_VIOLET} 0%,{I_BLUE} 30%,{I_NAVY} 64%,{I_PLUM} 100%);padding:0;border-radius:4px 4px 0 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <!-- brand bar -->
                <tr>
                  <td class="px" style="padding:18px 32px 0 32px;">
                    <div style="font-family:{SANS};font-size:19px;font-weight:800;letter-spacing:-.4px;line-height:1.25;color:{LIME};">{esc(SITE_TITLE_EN)}</div>
                    <div style="font-family:{SANS};font-size:11.5px;font-weight:500;letter-spacing:1.8px;text-transform:uppercase;color:{ON_DARK_2};padding-top:2px;">{esc(TAGLINE)}</div>
                  </td>
                </tr>
                <!-- eyebrow + headline + standfirst -->
                <tr>
                  <td class="px hero-pad" style="padding:26px 32px 4px 32px;">
                    <div style="font-family:{SANS};font-size:11.5px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:{LIME};">Daily Brief&#12288;&middot;&#12288;{esc(DATE_EN)}</div>
                    <div class="h1 hero-head" style="font-family:{SANS};font-size:38px;font-weight:800;letter-spacing:-1.6px;line-height:1.04;color:{ON_DARK};padding:14px 0 0 0;">{headline_html}</div>
                    <p class="m-hide" style="margin:14px 0 0 0;font-family:{SANS};font-size:15px;line-height:1.55;color:{ON_DARK_2};max-width:430px;">{esc(STANDFIRST_EN)}</p>
                  </td>
                </tr>
                <!-- issue meta chips, same four facts as the site's .issue-meta -->
                <tr>
                  <td class="px chips-pad" style="padding:16px 32px 0 32px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
                      <td style="padding:0 6px 6px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11.5px;color:{ON_DARK_CHIP};border:1px solid rgba(247,245,239,.26);border-radius:999px;padding:5px 11px;"><strong>{total}</strong> stories &middot; <strong>{len(sections)}</strong> categories</span></td>
                      <td style="padding:0 6px 6px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11.5px;color:{ON_DARK_CHIP};border:1px solid rgba(247,245,239,.26);border-radius:999px;padding:5px 11px;"><strong>{picked_count}</strong> featured here</span></td>
                      <td style="padding:0 0 6px 0;"><span style="display:inline-block;font-family:{SANS};font-size:11.5px;color:{ON_DARK_CHIP};border:1px solid rgba(247,245,239,.26);border-radius:999px;padding:5px 11px;"><strong>{EMAIL_READ_MIN}</strong>-minute read</span></td>
                    </tr></table>
                  </td>
                </tr>
                <!-- byline -->
                <tr class="m-hide">
                  <td class="px m-hide" style="padding:10px 32px 24px 32px;">
                    <div style="font-family:{SANS};font-size:12px;color:{ON_DARK_2};">Curated by <strong style="color:{ON_DARK};">{esc(BYLINE)}</strong> &nbsp;&middot;&nbsp; {esc(BYLINE_ROLE_EN)}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Intro + CTA -->
          <tr>
            <td class="bg-paper px intro-pad" bgcolor="{PAPER}" style="background-color:{PAPER};padding:24px 32px 20px 32px;">
              <p style="margin:0 0 16px 0;font-family:{SANS};font-size:14.5px;line-height:1.6;color:{BODY};" class="ink"><strong style="color:{INK};" class="ink">Tap any headline</strong> to open that story on the site, with the full summary and the original source. {rest_line}</p>
              <div class="m-hide-cta">{cta()}</div>
            </td>
          </tr>

{sections_html}

          {legend}

          <!-- Secondary CTA -->
          <tr>
            <td class="bg-paper px" bgcolor="{PAPER}" align="center" style="background-color:{PAPER};padding:20px 32px 28px 32px;">
              {cta("See all " + str(total) + " stories &rarr;", "cta-bottom")}
              <p style="margin:13px 0 0 0;font-family:{SANS};font-size:12px;line-height:1.5;color:{MUTED};" class="muted">Read it in English or &#20013;&#25991; &mdash; toggle at the top right of the site.</p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td class="footer-bg px" bgcolor="{INK}" style="background-color:{INK};padding:26px 32px 30px 32px;border-radius:0 0 4px 4px;">
              <p style="margin:0 0 10px 0;font-family:{SANS};font-size:11.5px;line-height:1.55;color:#9B9FA9;">Sources: {sources_note_en}</p>
              <p style="margin:0 0 4px 0;font-family:{SANS};font-size:13px;font-weight:800;letter-spacing:-.2px;color:#FFFFFF;"><span style="color:{LIME};">{esc(SITE_TITLE_EN)}</span> &nbsp;&middot;&nbsp; <span style="color:#FFFFFF;">Curated by {esc(BYLINE)}</span></p>
              <p style="margin:0 0 12px 0;font-family:{SANS};font-size:11.5px;line-height:1.5;color:#8A8E98;">For informational reference only. &nbsp;&middot;&nbsp; <a href="{esc(_tag(SITE_URL_EN, "footer"))}" target="_blank" style="color:{LIME};text-decoration:underline;">{esc(SITE_URL.replace("https://","").rstrip("/"))}</a></p>
              <p style="margin:0;font-family:{SANS};font-size:11px;line-height:1.5;color:#7A7E87;">You are receiving this briefing as part of the AI Marketing Daily distribution. To adjust your subscription, reply to this email.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
'''

# ---- reading time, measured on the assembled page ---------------------------
# Counted from the rendered text instead of predicted from the data, so the chip
# cannot drift when the chrome changes. What is counted is what a reader reads:
#   - <style> and comments removed (never rendered)
#   - the preheader div removed (display:none; it is inbox preview text, and
#     counting it would charge the reader for words they never see in the body)
#   - .m-hide-cta kept: it is the desktop superset. Counting the widest version
#     rounds the promise upward, which is the safe direction for a commitment.
# 220 wpm is the conventional screen-reading rate; CJK runs count at 2.5
# characters per word-equivalent, which matters only if a future issue mixes
# languages into the English email (today it does not — see the assert).
_WPM = 220

def _visible_words(doc):
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", doc)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?is)<div style=\"display:none;max-height:0;.*?</div>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[​‌͏\xa0]", " ", s)
    cjk = len(re.findall(r"[㐀-鿿豈-﫿]", s))
    latin = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-\.$%]*", s))
    return latin + cjk / 2.5, latin, cjk

assert page.count("@@READMIN@@") == 1, f"read-time placeholder count={page.count('@@READMIN@@')}"
# Count with the placeholder gone, else READMIN itself scores as a word.
_w, _latin, _cjk = _visible_words(page.replace("@@READMIN@@", " "))
_read_min = max(1, int(math.ceil(_w / _WPM - 1e-9)))
page = page.replace("@@READMIN@@", str(_read_min))

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "email.html").write_text(page, encoding="utf-8")
# ---- subject line ----------------------------------------------------------
# The old subject spent its first 20 characters on a bracketed brand tag and its
# last 30 on counts. Measured against the two cut-offs that actually exist:
# iPhone Mail shows ~35 characters and Gmail desktop ~70, so the reader saw
# "[AI Marketing Daily] October 14, 20" — a date, inside a label, and nothing
# about today. Brand recognition is already carried by the sender name, which
# sits next to the subject in every client.
#
# New shape: the lead story first, so the most specific thing in the email is
# the thing that survives truncation; the date and the count follow for the
# clients that have room. Truncation is cut at a word boundary so no client
# shows half a word.
# "Lead story" = the first item in the first section, i.e. data.json's item #1.
# That is not my invention: the site already treats item #1 as the day's lead —
# build.py builds og:description from items[:3] (build.py:1293) and the JSON-LD
# headline list from items[:25] in file order (build.py:1420), both unsorted. So
# the email leading with the same story keeps the subject line, the share card
# and the page in agreement. There is no rank/score/priority field on an item
# (checked: the only fields are action, region, source, section, title, summary,
# why, detail, highlights, followup, time, url), so file order is the only
# editorial signal that exists, and the morning research writes it deliberately.
_lead = pick(featured[0][1][0], "title_en", "title") if featured and featured[0][1] else ""
_lead = _lead.split(":")[0].split(" — ")[0].strip()
if len(_lead) > 52:
    _lead = _lead[:52].rsplit(" ", 1)[0] + "…"
# "and 0 more" is arithmetically correct and reads as a bug (the one-item
# adversarial build produced exactly that). Drop the clause when there is no
# remainder to report.
_more = f" · and {total - 1} more" if total > 1 else ""
_date_tail = f" — {DATE_SUBJECT}" if DATE_SUBJECT else ""
subject = (f"{_lead}{_more}{_date_tail}"
           if _lead else
           f"AI Marketing Daily · {DATE_SUBJECT} ({total} stories)")
(OUT / "email-subject.txt").write_text(subject + "\n", encoding="utf-8")

print(f"OK {OUT / 'email.html'}  featured={picked_count} (picks/section={PICKS})  total={total}")
print("SUBJECT:", subject)
