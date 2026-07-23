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
    "#0E7C66", "#0A5C4C", "#1A2A2E", "#5E6E6A", "#DBE2D9", "#F6F7F4", "#FFFFFF")


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
    f'<span class="l-zh">📚 你而家睇緊<b>往期存檔</b> · {html.escape(ZH_DISP)}</span>'
    f'<span class="l-en">📚 You&rsquo;re viewing a <b>past issue</b> · {html.escape(EN_DISP)}</span>'
    f'&nbsp;·&nbsp;<a href="./" style="color:#fff;text-decoration:underline;font-weight:600">'
    f'<span class="l-zh">往期目錄</span><span class="l-en">All issues</span></a>'
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

rows = []
for e in entries:
    wk_zh, wk_en = _weekday_pair(e.get("date",""))
    rows.append(
        f'<a class="issue" href="{html.escape(e["url"])}">'
        f'<span class="d"><span class="l-zh">{html.escape(e.get("date_short_zh",""))} · 星期{wk_zh}</span>'
        f'<span class="l-en">{html.escape(e.get("date_short_en",""))} · {wk_en}</span></span>'
        f'<span class="meta"><span class="cnt">{e.get("total",0)}</span>'
        f'<span class="l-zh">條精選</span><span class="l-en">picks</span>'
        f'<span class="go">→</span></span>'
        f'</a>'
    )
rows_html = "\n".join(rows) if rows else (
    '<p class="empty"><span class="l-zh">未有往期記錄，明日起會逐日累積。</span>'
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
:root{{--paper:{PAPER};--card:{CARD};--ink:{INK};--muted:{MUTED};--jade:{JADE};--jade-d:{JADE_D};--line:{LINE}}}
html,body{{margin:0}}
body{{background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang HK','Microsoft JhengHei',sans-serif}}
.l-en{{display:none}} .l-zh{{display:inline}}
html[data-lang="en"] .l-en{{display:inline}} html[data-lang="en"] .l-zh{{display:none}}
.wrap{{max-width:820px;margin:0 auto;padding:0 20px}}
header{{border-top:4px solid var(--jade);background:var(--card);border-bottom:1px solid var(--line);padding:26px 0 22px}}
.mast{{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}}
h1{{font-size:24px;margin:0;font-weight:700}} h1 .k{{color:var(--jade)}}
.sub{{color:var(--muted);font-size:14px;margin-top:6px}}
.mast-r{{display:flex;align-items:center;gap:12px}}
.back{{font-size:13px;color:var(--jade-d);text-decoration:none;border:1px solid var(--line);padding:7px 14px;border-radius:4px;white-space:nowrap}}
.back:hover{{border-color:var(--jade);color:var(--jade)}}
.langtog{{display:inline-flex;border:1px solid var(--line);border-radius:4px;overflow:hidden}}
.langtog button{{border:0;background:transparent;color:var(--muted);font:inherit;font-size:12px;padding:6px 11px;cursor:pointer}}
.langtog button.on{{background:var(--jade);color:#fff}}
main{{padding:22px 0 60px}}
.issue{{display:flex;align-items:center;justify-content:space-between;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px 18px;margin:0 0 10px;text-decoration:none;color:var(--ink)}}
.issue:hover{{border-color:var(--jade)}}
.issue .d{{font-weight:600;font-size:16px}}
.issue .meta{{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:14px;white-space:nowrap}}
.issue .cnt{{color:var(--jade-d);font-weight:700}}
.issue .go{{color:var(--jade);font-weight:700;font-size:18px;margin-left:4px}}
.empty{{color:var(--muted);text-align:center;padding:40px 0}}
footer{{border-top:1px solid var(--line);color:var(--muted);font-size:13px;padding:18px 0 40px;text-align:center}}
</style>
</head>
<body>
<header><div class="wrap">
<div class="mast">
  <div>
    <h1><span class="l-zh">往期存檔</span><span class="l-en"><span class="k">Archive</span></span></h1>
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
<footer><div class="wrap"><span class="l-zh">往期存檔 · 由 {html.escape(_short_zh(entries[-1]['date']) if entries else '')} 起</span><span class="l-en">Archive · since {html.escape(_short_en(entries[-1]['date']) if entries else '')}</span></div></footer>
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
