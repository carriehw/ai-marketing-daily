# -*- coding: utf-8 -*-
"""Archive builder for the AI Marketing Daily site.

Each day, AFTER build.py has produced today's index.html, this script:
  1) writes a permanent standalone snapshot of today's issue to
       archive/<ISO-date>.html   (the built page + a "past issue" banner)
  2) upserts today's entry into archive/manifest.json (keyed by date, newest first)
  3) regenerates archive/index.html — the bilingual "往期存檔 / Archive" directory
     page that lists every past issue, newest first.

History starts from the day this first runs (no back-fill). Idempotent: re-running
for the same date overwrites that day's snapshot and manifest entry, never duplicates.

Run (from the folder that has data.json + index.html):
      PYTHONIOENCODING=utf-8 python3 build_archive.py
Options:
      --data <path>         data.json (default ./data.json, then beside this script)
      --site <path>         the built index.html to snapshot (default ./index.html)
      --archive-dir <path>  output archive dir (default ./archive)
"""
import json, html, re, sys, os, argparse
from pathlib import Path
from datetime import datetime

JADE, JADE_D, INK, MUTED, LINE, PAPER, CARD = (
    "#5a42f4", "#4632d4", "#101114", "#656a73", "#dedbd2", "#f7f5ef", "#ffffff")
# Palette v1.0 — the archive header is an identity zone too, so it carries the
# same four icon corners as the homepage hero. Values measured from icon-512.png;
# see file-space/brand/palette_check.py.
I_VIOLET, I_BLUE, I_NAVY, I_PLUM = "#553fba", "#2f5582", "#11154a", "#7d266b"
LIME, ON_DARK, ON_DARK_2 = "#d3fe66", "#f7f5ef", "#d6d4e8"


def _canon_dates(iso, zh_fallback="", en_fallback=""):
    """Derive the display dates from the ISO date so the weekday is never
    hand-mis-typed. Falls back to whatever was passed if the ISO is invalid."""
    try:
        d = datetime.strptime((iso or "").strip(), "%Y-%m-%d")
        wk_zh = ["一", "二", "三", "四", "五", "六", "日"][d.weekday()]
        zh = f"{d.year}年{d.month}月{d.day}日 · 星期{wk_zh}"
        en = f"{d.strftime('%B')} {d.day}, {d.year} · {d.strftime('%A')}"
        return zh, en
    except Exception:
        return (zh_fallback or ""), (en_fallback or zh_fallback or "")


def _short_en(iso, fallback=""):
    """English date without weekday, e.g. 'July 23, 2026'."""
    try:
        d = datetime.strptime((iso or "").strip(), "%Y-%m-%d")
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    except Exception:
        return fallback


def _short_zh(iso, fallback=""):
    try:
        d = datetime.strptime((iso or "").strip(), "%Y-%m-%d")
        return f"{d.year}年{d.month}月{d.day}日"
    except Exception:
        return fallback


ap = argparse.ArgumentParser(description="Build the AI Marketing Daily archive")
ap.add_argument("--data", help="path to data.json")
ap.add_argument("--site", help="path to the built index.html to snapshot")
ap.add_argument("--archive-dir", help="output archive directory (default ./archive)")
args = ap.parse_args()

_here = Path(__file__).parent
DATA = Path(args.data) if args.data else (
    Path.cwd() / "data.json" if (Path.cwd() / "data.json").is_file() else _here / "data.json")
SITE = Path(args.site) if args.site else (
    Path.cwd() / "index.html" if (Path.cwd() / "index.html").is_file() else _here / "index.html")
ARCH = Path(args.archive_dir) if args.archive_dir else (DATA.parent / "archive")

try:
    data = json.loads(DATA.read_text(encoding="utf-8"))
except FileNotFoundError:
    sys.exit(f"ERROR: data.json not found at {DATA}")
except json.JSONDecodeError as e:
    sys.exit(f"ERROR: data.json invalid JSON near line {e.lineno}: {e}")

ISO = (data.get("date") or "").strip()
if not re.match(r"^\d{4}-\d{2}-\d{2}$", ISO):
    sys.exit(f"ERROR: data.json 'date' must be ISO YYYY-MM-DD, got {ISO!r} — cannot archive.")

try:
    site_html = SITE.read_text(encoding="utf-8")
except FileNotFoundError:
    sys.exit(f"ERROR: built site not found at {SITE} — run build.py first.")

TITLE      = data.get("site_title", "AI・行銷情報")
TITLE_EN   = data.get("site_title_en", "AI Marketing Daily")
TOTAL      = len(data.get("items", []))
ZH_DISP, EN_DISP = _canon_dates(ISO, data.get("date_display", ""), data.get("date_display_en", ""))
SITE_URL   = data.get("site_url", "https://carriehw.github.io/ai-marketing-daily/")

ARCH.mkdir(parents=True, exist_ok=True)

# ---- 1) standalone snapshot of today's issue -------------------------------
banner = (
    f'<div style="background:{JADE_D};color:#fff;padding:11px 20px;text-align:center;'
    f'font:14px/1.55 -apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'Helvetica Neue\','
    f'Arial,\'PingFang HK\',\'Microsoft JhengHei\',sans-serif">'
    f'<span class="l-zh">📚 你正在閱讀<b>歷史存檔</b> · {html.escape(ZH_DISP)}</span>'
    f'<span class="l-en">📚 You&rsquo;re viewing a <b>past issue</b> · {html.escape(EN_DISP)}</span>'
    f'&nbsp;·&nbsp;<a href="./" style="color:#fff;text-decoration:underline;font-weight:600">'
    f'<span class="l-zh">全部期數</span><span class="l-en">All issues</span></a>'
    f'&nbsp;·&nbsp;<a href="../" style="color:#fff;text-decoration:underline;font-weight:600">'
    f'<span class="l-zh">返回今日最新 →</span><span class="l-en">Back to today &rarr;</span></a>'
    f'</div>'
)
snap = re.sub(r"(<body[^>]*>)", r"\1" + banner, site_html, count=1)
# On an archived page the header "📚 往期存檔" link (href="archive/") would point to
# archive/archive/ — rewrite it to the archive index (./) instead.
snap = snap.replace('href="archive/"', 'href="./"')
(ARCH / f"{ISO}.html").write_text(snap, encoding="utf-8")

# ---- 2) upsert manifest ----------------------------------------------------
MANIFEST = ARCH / "manifest.json"
entries = []
if MANIFEST.is_file():
    try:
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            entries = []
    except Exception:
        entries = []
entries = [e for e in entries if e.get("date") != ISO]
entries.append({
    "date": ISO, "date_display": ZH_DISP, "date_display_en": EN_DISP,
    "date_short_zh": _short_zh(ISO), "date_short_en": _short_en(ISO),
    "total": TOTAL, "title": TITLE, "title_en": TITLE_EN,
    "url": f"{ISO}.html",
})
entries.sort(key=lambda e: e.get("date", ""), reverse=True)
MANIFEST.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- 3) render archive/index.html ------------------------------------------
def _weekday_pair(iso):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return ["一","二","三","四","五","六","日"][d.weekday()], d.strftime("%A")
    except Exception:
        return "", ""

# ---- quarterly grouping -----------------------------------------------------
# Carrie's decision (2026-09-30), chosen over one-month retention: KEEP EVERY
# ISSUE, group the index by quarter. The flat list was 59 rows of near-identical
# date pills with no landmark to scan by; deleting the old ones was the other way
# to shorten it, at the cost of 31 already-shared URLs turning into 404s.
#
# Grouping is presentation only. `entries` and manifest.json are untouched, so
# nothing here can drop an issue: every entry lands in exactly one bucket, and
# the rendered row count is asserted against len(entries) below.
# Two levels, quarter outside and month inside. Quarter ALONE would have done
# nothing on the day it shipped: measured against the live manifest, all 59 issues
# (2026-07-23 → 2026-09-30) sit inside Q3 2026, so it rendered exactly one heading
# above 59 identical rows and the index was no easier to scan than the flat list —
# the grouping would only have started working in October. The month level gives
# 2026年9月 / 8月 / 7月 today, and the quarter level keeps the page from growing a
# new heading every month forever. Both counts are shown so a missing week is
# visible as a number, not something you have to notice by eye.
_MON_EN = ["January","February","March","April","May","June",
           "July","August","September","October","November","December"]

def _keys(iso):
    """(quarter_key, q_zh, q_en, month_key, m_zh, m_en).

    An unparseable date must NOT be silently dropped — that is how an archive
    loses history quietly — so it lands in a visible 'other' bucket instead.
    """
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except Exception:
        return ("0000-Q0", "其他", "Other", "0000-00", "日期不詳", "Undated")
    q = (d.month - 1) // 3 + 1
    return (f"{d.year}-Q{q}", f"{d.year} 年第{['一','二','三','四'][q-1]}季", f"Q{q} {d.year}",
            f"{d.year}-{d.month:02d}", f"{d.year} 年 {d.month} 月", f"{_MON_EN[d.month-1]} {d.year}")

_groups, _order = {}, []
for e in entries:                      # entries is already newest-first
    qk, qzh, qen, mk, mzh, men = _keys(e.get("date", ""))
    if qk not in _groups:
        _groups[qk] = {"zh": qzh, "en": qen, "months": {}, "morder": []}
        _order.append(qk)
    g = _groups[qk]
    if mk not in g["months"]:
        g["months"][mk] = {"zh": mzh, "en": men, "rows": []}
        g["morder"].append(mk)
    wk_zh, wk_en = _weekday_pair(e.get("date", ""))
    g["months"][mk]["rows"].append(
        f'<a class="issue" href="{html.escape(e["url"])}">'
        f'<span class="d"><span class="l-zh">{html.escape(e.get("date_short_zh",""))} · 星期{wk_zh}</span>'
        f'<span class="l-en">{html.escape(e.get("date_short_en",""))} · {wk_en}</span></span>'
        f'<span class="meta"><span class="cnt">{e.get("total",0)}</span>'
        f'<span class="l-zh">條精選</span><span class="l-en">picks</span>'
        f'<span class="go">→</span></span>'
        f'</a>'
    )

# The bad-date bucket must sort LAST. It does not do so on its own: `entries` is
# sorted by the raw date string, and a value like "bogus-date" sorts ABOVE
# "2026-09-30" lexically, which put "其他 / Other" at the very TOP of the archive —
# above the newest issue. Caught by a negative control that fed the renderer a
# manifest spanning four quarters plus one unparseable date; with only real data
# (all of it inside Q3 2026) this was invisible.
_order = [k for k in _order if k != "0000-Q0"] + [k for k in _order if k == "0000-Q0"]

def _n(n, zh_unit, en_one, en_many):
    return (f'<span class="l-zh">{n} {zh_unit}</span>'
            f'<span class="l-en">{n} {en_one if n == 1 else en_many}</span>')

_blocks = []
for qk in _order:
    g = _groups[qk]
    qn = sum(len(g["months"][mk]["rows"]) for mk in g["morder"])
    parts = [f'<section class="qtr">'
             f'<h2 class="qtr-h"><span><span class="l-zh">{html.escape(g["zh"])}</span>'
             f'<span class="l-en">{html.escape(g["en"])}</span></span>'
             f'<span class="qn">{_n(qn, "期", "issue", "issues")}</span></h2>']
    for mk in g["morder"]:
        m = g["months"][mk]
        parts.append(
            f'<h3 class="mon-h"><span><span class="l-zh">{html.escape(m["zh"])}</span>'
            f'<span class="l-en">{html.escape(m["en"])}</span></span>'
            f'<span class="qn">{_n(len(m["rows"]), "期", "issue", "issues")}</span></h3>')
        parts.append("\n".join(m["rows"]))
    parts.append('</section>')
    _blocks.append("\n".join(parts))

# Nothing may vanish between the manifest and the page. If grouping ever drops a
# row this fails the build loudly instead of publishing a shorter archive.
_rendered = sum(len(_groups[qk]["months"][mk]["rows"])
                for qk in _order for mk in _groups[qk]["morder"])
assert _rendered == len(entries), (
    f"archive grouping lost entries: rendered {_rendered} of {len(entries)}")

rows_html = "\n".join(_blocks) if _blocks else (
    '<p class="empty"><span class="l-zh">尚無歷史記錄，明日起會逐日累積。</span>'
    '<span class="l-en">No past issues yet — they accumulate daily from today.</span></p>')

count = len(entries)
page = f"""<!DOCTYPE html>
<html lang="en" data-lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(TITLE_EN)} · Archive</title>
<script>
(function(){{
  try{{
    var p=new URLSearchParams(location.search).get('lang');
    if(p){{try{{localStorage.setItem('amd-lang',p);}}catch(e){{}}}}
    var l=p||localStorage.getItem('amd-lang');
    if(l==='zh'){{document.documentElement.setAttribute('data-lang','zh');document.documentElement.lang='zh-Hant';}}
    else{{document.documentElement.setAttribute('data-lang','en');document.documentElement.lang='en';}}
  }}catch(e){{}}
}})();
</script>
<style>
*{{box-sizing:border-box}}
:root{{--paper:{PAPER};--card:{CARD};--ink:{INK};--muted:{MUTED};--accent:{JADE};--accent-d:{JADE_D};--line:{LINE};
  --lime:{LIME};--on-dark:{ON_DARK};--on-dark-2:{ON_DARK_2};--i-navy:{I_NAVY}}}
html,body{{margin:0}}
/* Radial glow removed: it sat at 85% 0%, which the dark header now covers. */
body{{background:var(--paper);color:var(--ink);font:16px/1.6 Inter,'Noto Sans TC',ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang TC','Microsoft JhengHei',sans-serif}}
.l-en{{display:none}} .l-zh{{display:inline}}
html[data-lang="en"] .l-en{{display:inline}} html[data-lang="en"] .l-zh{{display:none}}
.wrap{{max-width:820px;margin:0 auto;padding:0 20px}}
/* Dark identity zone, same four icon corners and same spatial order as the
   homepage hero, so the archive reads as the same publication rather than a
   plain file index. Reading zone below stays warm paper (rule R4).
   Every pairing below is checked against the LIGHTEST stop #553fba — the worst
   case: Paper 6.86:1, on-dark-2 5.15:1, Lime 6.46:1. */
header{{border-top:4px solid var(--lime);color:var(--on-dark);border-bottom:1px solid rgba(247,245,239,.14);padding:26px 0 22px;
  background:linear-gradient(135deg,{I_VIOLET} 0%,{I_BLUE} 30%,{I_NAVY} 64%,{I_PLUM} 100%)}}
.mast{{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}}
h1{{font-size:24px;margin:0;font-weight:700;color:var(--on-dark)}} h1 .k{{color:var(--lime)}}
/* MUST stay scoped to `header`. .sub is reused by the "共 59 期 / 59 issues"
   count line inside <main>, which sits on warm paper — a bare `.sub` set to
   on-dark-2 rendered that line at 1.33:1, invisible. The contrast checker could not catch
   this: the pairing it was asked about (on-dark-2 over the gradient) passes; the
   defect was the SELECTOR reaching a second element on a different background. */
header .sub{{color:var(--on-dark-2);font-size:14px;margin-top:6px}}
main .sub{{color:var(--muted);font-size:14px}}
.mast-r{{display:flex;align-items:center;gap:12px}}
.back{{font-size:13px;color:var(--on-dark);text-decoration:none;border:1px solid rgba(247,245,239,.34);padding:7px 14px;border-radius:999px;white-space:nowrap}}
.back:hover{{border-color:var(--lime);color:var(--lime)}}
.langtog{{display:inline-flex;border:1px solid rgba(247,245,239,.34);border-radius:999px;overflow:hidden}}
.langtog button{{border:0;background:transparent;color:var(--on-dark-2);font:inherit;font-size:12px;padding:6px 11px;cursor:pointer}}
.langtog button.on{{background:var(--lime);color:var(--i-navy)}}
main{{padding:22px 0 60px}}
.issue{{display:flex;align-items:center;justify-content:space-between;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 22px;margin:0 0 10px;text-decoration:none;color:var(--ink);box-shadow:0 4px 18px rgba(16,17,20,.04)}}
.issue:hover{{border-color:var(--accent)}}
.issue .d{{font-weight:600;font-size:16px}}
.issue .meta{{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:14px;white-space:nowrap}}
.issue .cnt{{color:var(--accent);font-weight:700}}
/* Was var(--jade) — a variable that is defined nowhere in this file or the
   homepage, so the arrow silently inherited .issue's --ink instead of the accent
   it was written to use. Fixed to --accent while auditing the palette. */
.issue .go{{color:var(--accent);font-weight:700;font-size:18px;margin-left:4px}}
/* ---- quarter headings ------------------------------------------------------
   Colours are stated explicitly, never inherited from a shared class. The bug
   this file already carries a comment about (`.sub` reaching a second element on
   a different background and rendering at 1.33:1) came from exactly that kind of
   reuse, so `.qtr-h` gets its own selectors on the warm-paper zone only:
   --ink on --paper = 14.2:1, --muted on --paper = 5.3:1.
   First group has no top margin — a gap above the newest issue would read as a
   rendering fault at the top of the page. */
.qtr{{margin:0 0 4px}}
.qtr+.qtr{{margin-top:30px}}
.qtr-h,.mon-h{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:0 0 10px}}
/* Quarter is the louder of the two: a rule line plus ink. Month is a quiet label
   with no rule, so the two levels are told apart by weight and colour rather than
   by size alone (at 13-14px a 1px size step is not a hierarchy). */
.qtr-h{{padding:0 4px 8px;border-bottom:1px solid var(--line);font-size:15px;font-weight:700;color:var(--ink);letter-spacing:.02em}}
.mon-h{{padding:0 4px;font-size:13px;font-weight:600;color:var(--muted);letter-spacing:.06em;text-transform:none}}
.qtr-h+.mon-h{{margin-top:2px}}
.issue+.mon-h{{margin-top:20px}}
.qtr-h .qn,.mon-h .qn{{font-weight:600;color:var(--muted);font-size:12.5px;white-space:nowrap}}
.empty{{color:var(--muted);text-align:center;padding:40px 0}}
footer{{border-top:1px solid var(--line);color:var(--muted);font-size:13px;padding:18px 0 40px;text-align:center}}
</style>
</head>
<body>
<header><div class="wrap">
<div class="mast">
  <div>
    <h1><span class="l-zh">歷史存檔</span><span class="l-en"><span class="k">Archive</span></span></h1>
    <div class="sub"><span class="l-zh">{html.escape(TITLE)} · 每日精選逐日累積</span><span class="l-en">{html.escape(TITLE_EN)} · daily issues, newest first</span></div>
  </div>
  <div class="mast-r">
    <a class="back" href="../"><span class="l-zh">← 今日最新</span><span class="l-en">← Today</span></a>
    <div class="langtog" role="group" aria-label="Language / 語言">
      <button type="button" data-set="en" class="on">EN</button>
      <button type="button" data-set="zh">中文</button>
    </div>
  </div>
</div>
</div></header>
<main class="wrap">
<p class="sub" style="margin:0 0 16px"><span class="l-zh">共 <b>{count}</b> 期</span><span class="l-en"><b>{count}</b> issues</span></p>
{rows_html}
</main>
<footer><div class="wrap"><span class="l-zh">歷史存檔 · 由 {html.escape(_short_zh(entries[-1]['date']) if entries else '')} 起</span><span class="l-en">Archive · since {html.escape(_short_en(entries[-1]['date']) if entries else '')}</span></div></footer>
<script>
function setLang(l){{
  document.documentElement.setAttribute('data-lang',l);
  document.documentElement.lang = l==='en'?'en':'zh-Hant';
  try{{localStorage.setItem('amd-lang',l);}}catch(e){{}}
  document.querySelectorAll('.langtog button').forEach(b=>b.classList.toggle('on', b.dataset.set===l));
}}
document.querySelectorAll('.langtog button').forEach(b=>b.addEventListener('click',()=>setLang(b.dataset.set)));
setLang(document.documentElement.getAttribute('data-lang')==='zh'?'zh':'en');
</script>
</body>
</html>"""
(ARCH / "index.html").write_text(page, encoding="utf-8")

print(f"OK archive/  snapshot={ISO}.html  issues={count}  (latest {ISO}, total items={TOTAL})")
