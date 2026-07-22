# -*- coding: utf-8 -*-
"""Build a single-file daily marketing-intelligence briefing index.html from data.json.

Bilingual edition (繁中 / English): a 中 | EN toggle in the masthead switches the
WHOLE page between Cantonese/Traditional-Chinese and English, persisted in
localStorage. Both languages are rendered into the page and toggled via a
`data-lang` attribute on <html> + CSS — no reload, works offline.

Each card shows an ACTION tag (可即用 / 要留意 / 影響生意) plus a REGION tag
(國際 / 中國 / 香港); both are auto-translated for the EN view.

Config keys in data.json (optional unless noted):
  site_title     : masthead brand      (default "AI・行銷情報")
  site_title_en  : masthead brand (EN)  (default "AI Marketing Daily")
  site_tagline   : uppercase tag        (default "AI Marketing Intelligence")
  site_url       : canonical URL        (default "" -> Share button uses location.href)
  date           : ISO date (<title>)                        [required]
  date_display   : human date shown in hero (中文)
  date_display_en: human date shown in hero (English)
  sources_note   : footer source list (中文)
  sources_note_en: footer source list (English)
  sections       : ordered section names (中文)              [required]
  sections_en    : ordered section names (English, same order/length as sections)
  items[]        : {title, summary, source, url, time, section, action, region, why,
                    title_en, summary_en, why_en}             [required core fields]

Any missing *_en field falls back to its Chinese value, so the site never breaks
on a day the translations are incomplete — it just shows Chinese in the EN view.

Run:  PYTHONIOENCODING=utf-8 python3 build.py
"""
import json, html, re, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent


def _canon_dates(iso, zh_fallback="", en_fallback=""):
    """Derive the display dates from the ISO date so the weekday is never
    hand-mis-typed. Falls back to whatever data.json provided if the ISO date
    is missing/invalid."""
    try:
        d = datetime.strptime((iso or "").strip(), "%Y-%m-%d")
        wk_zh = ["一", "二", "三", "四", "五", "六", "日"][d.weekday()]
        zh = f"{d.year}年{d.month}月{d.day}日 · 星期{wk_zh}"
        en = f"{d.strftime('%B')} {d.day}, {d.year} · {d.strftime('%A')}"
        return zh, en
    except Exception:
        return (zh_fallback or ""), (en_fallback or zh_fallback or "")

# --- Load data.json with a clear error instead of a raw traceback -------------
_data_path = ROOT / "data.json"
try:
    _raw = _data_path.read_text(encoding="utf-8")
except FileNotFoundError:
    sys.exit(f"ERROR: {_data_path} not found. Create data.json next to build.py "
             f"(structure: scripts/data.sample.json).")
try:
    data = json.loads(_raw)
except json.JSONDecodeError as e:
    sys.exit(f"ERROR: data.json is not valid JSON — {e}. Fix the syntax near line {e.lineno}.")

for _key in ("sections", "items", "date"):
    if _key not in data:
        sys.exit(f"ERROR: data.json is missing the required top-level key '{_key}'.")

# Always recompute the display dates from the ISO date (weekday is never trusted
# from hand-written fields — that's how a wrong 星期/weekday slips into the site).
_zh_d, _en_d = _canon_dates(data.get("date", ""),
                            data.get("date_display", ""),
                            data.get("date_display_en", ""))
data["date_display"] = _zh_d
data["date_display_en"] = _en_d

SITE_TITLE    = data.get("site_title", "AI・行銷情報")
SITE_TITLE_EN = data.get("site_title_en", "AI Marketing Daily")
SITE_TAGLINE  = data.get("site_tagline", "AI Marketing Intelligence")
SITE_URL      = data.get("site_url", "")

# action tag -> css class + English label
ACT = {"可即用": "a-use", "要留意": "a-watch", "影響生意": "a-biz"}
ACT_EN = {"可即用": "Ready to use", "要留意": "Worth watching", "影響生意": "Business impact"}
# region tag -> css class + English label
REG = {"國際": "r-intl", "中國": "r-cn", "香港": "r-hk"}
REG_EN = {"國際": "Global", "中國": "China", "香港": "HK"}

SEC_ID = {s: f"sec{i}" for i, s in enumerate(data["sections"])}
# section -> English name (parallel array, fall back to the Chinese name)
_sections_en = data.get("sections_en", [])
SEC_EN = {}
for _i, _s in enumerate(data["sections"]):
    SEC_EN[_s] = _sections_en[_i] if _i < len(_sections_en) else _s

_MONTH_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def _time_en(t):
    """'7月19日' -> 'Jul 19'; leave anything else untouched."""
    m = re.match(r"\s*(\d{1,2})月(\d{1,2})日\s*$", t or "")
    if m:
        mm = int(m.group(1))
        if 1 <= mm <= 12:
            return f"{_MONTH_EN[mm-1]} {int(m.group(2))}"
    return t or ""

def bi(zh, en=None):
    """Emit both-language spans; CSS shows the active one. Falls back to zh."""
    zh_s = "" if zh is None else str(zh)
    en_s = zh_s if en is None or en == "" else str(en)
    return (f'<span class="l-zh">{html.escape(zh_s)}</span>'
            f'<span class="l-en">{html.escape(en_s)}</span>')

# --- Validate items: warn (don't crash) --------------------------------------
def _cjk(s):
    return len(re.findall(r"[一-鿿]", s or ""))

_sections = set(data["sections"])
_warn = 0
for _i, _it in enumerate(data["items"], 1):
    _t = _it.get("title", f"(item #{_i}無標題)")
    for _f in ("title", "summary", "source", "url", "time", "section", "action", "region", "why"):
        if not _it.get(_f):
            print(f"WARN item {_i} 「{_t}」: 缺欄位 '{_f}'", file=sys.stderr); _warn += 1
    for _f in ("title_en", "summary_en", "why_en"):
        if not _it.get(_f):
            print(f"WARN item {_i} 「{_t}」: 缺英文欄位 '{_f}' → EN view 會 fallback 顯示中文", file=sys.stderr); _warn += 1
    _sec = _it.get("section", "")
    if _sec and _sec not in _sections:
        print(f"WARN item {_i} 「{_t}」: section '{_sec}' 唔喺五版塊之列 → 呢張卡會被丟走！", file=sys.stderr); _warn += 1
    if _it.get("action") and _it["action"] not in ACT:
        print(f"WARN item {_i} 「{_t}」: action '{_it['action']}' 唔啱（要 可即用/要留意/影響生意）→ 用預設色", file=sys.stderr); _warn += 1
    if _it.get("region") and _it["region"] not in REG:
        print(f"WARN item {_i} 「{_t}」: region '{_it['region']}' 唔啱（要 國際/中國/香港）→ 中性色", file=sys.stderr); _warn += 1
    if _cjk(_it.get("summary")) > 60:
        print(f"WARN item {_i} 「{_t}」: summary {_cjk(_it['summary'])} 中文字 >60，建議收短", file=sys.stderr); _warn += 1
    if _cjk(_it.get("why")) > 35:
        print(f"WARN item {_i} 「{_t}」: why {_cjk(_it['why'])} 中文字 >35，建議收短", file=sys.stderr); _warn += 1
    _u = _it.get("url", "")
    if _u and not _u.startswith(("http://", "https://")):
        print(f"WARN item {_i} 「{_t}」: url 唔係 http/https：{_u}", file=sys.stderr); _warn += 1

if len(_sections_en) and len(_sections_en) != len(data["sections"]):
    print(f"WARN sections_en 有 {len(_sections_en)} 個，同 sections 嘅 {len(data['sections'])} 個唔一致 → 部分版塊 EN 會 fallback 中文", file=sys.stderr); _warn += 1

groups = {s: [] for s in data["sections"]}
for it in data["items"]:
    groups.setdefault(it["section"], []).append(it)

for _s in data["sections"]:
    if not groups.get(_s):
        print(f"WARN 版塊「{_s}」今日冇內容（每版塊建議最少 1 條）", file=sys.stderr); _warn += 1

cards, n = {}, 0
for s in data["sections"]:
    out = []
    for it in groups[s]:
        n += 1
        url = html.escape(str(it.get("url", "")))
        act = it.get("action", "要留意")
        act_cls = ACT.get(act, "a-watch")
        reg = it.get("region", "")
        reg_cls = REG.get(reg, "r-other")
        src = html.escape(str(it.get("source", "")))
        tm = str(it.get("time", ""))
        out.append(f'''<article class="card">
<div class="ctop"><span class="no">{n:02d}</span><span class="chips"><span class="chip act {act_cls}">{bi(act, ACT_EN.get(act, act))}</span><span class="chip region {reg_cls}">{bi(reg, REG_EN.get(reg, reg))}</span></span></div>
<h3><a href="{url}" target="_blank" rel="noopener noreferrer">{bi(it.get("title",""), it.get("title_en"))}</a></h3>
<p class="sum">{bi(it.get("summary",""), it.get("summary_en"))}</p>
<p class="why"><b>{bi("點解重要", "Why it matters")}</b>{bi(it.get("why",""), it.get("why_en"))}</p>
<div class="cfoot"><span class="src">{src}　·　{bi(tm, _time_en(tm))}</span><a class="more" href="{url}" target="_blank" rel="noopener noreferrer">{bi("閱讀原文 ↗", "Read more ↗")}</a></div>
</article>''')
    cards[s] = "\n".join(out)

total = n
stats = "".join(
    f'<a class="stat" href="#{SEC_ID[s]}"><b>{len(groups[s])}</b><span>{bi(s, SEC_EN.get(s, s))}</span></a>'
    for s in data["sections"])
nav = "".join(
    f'<a href="#{SEC_ID[s]}">{bi(s, SEC_EN.get(s, s))}<i>{len(groups[s])}</i></a>'
    for s in data["sections"])
sections_html = "\n".join(
    f'<section id="{SEC_ID[s]}"><h2>{bi(s, SEC_EN.get(s, s))}<em>{bi(str(len(groups[s]))+" 條", str(len(groups[s]))+" items")}</em></h2><div class="grid">{cards[s]}</div></section>'
    for s in data["sections"])

date_disp    = data.get("date_display", "")
date_disp_en = data.get("date_display_en", date_disp)
sources_note = data.get("sources_note", "")
sources_note_en = data.get("sources_note_en", sources_note)

page = f'''<!doctype html>
<html lang="en" data-lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(SITE_TITLE_EN)} · {data.get("date","")}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>
/* Language on entry, resolved before paint (no flash):
   1) ?lang=en|zh in the URL wins — lets the newsletter force a language regardless
      of a visitor's stored choice — and is remembered for next time.
   2) otherwise a previously toggled choice (localStorage) wins.
   3) otherwise English (the page default on the <html> tag). */
(function(){{try{{
  var p=(location.search.match(/[?&]lang=(en|zh)/)||[])[1];
  if(p){{try{{localStorage.setItem('amd-lang',p);}}catch(e){{}}}}
  var l=p||localStorage.getItem('amd-lang');
  if(l==='zh'){{document.documentElement.setAttribute('data-lang','zh');document.documentElement.lang='zh-Hant';}}
  else if(l==='en'){{document.documentElement.setAttribute('data-lang','en');document.documentElement.lang='en';}}
}}catch(e){{}}}})();
</script>
<style>
:root{{--paper:#F6F7F4;--card:#FFFFFF;--ink:#1A2A2E;--muted:#5E6E6A;--jade:#0E7C66;--jade-d:#0A5C4C;--line:#DBE2D9}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang HK","PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif;line-height:1.6}}
/* --- language toggle: show the active language, hide the other --- */
.l-en{{display:none}}
html[data-lang="en"] .l-en{{display:inline}}
html[data-lang="en"] .l-zh{{display:none}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 20px}}
header{{border-top:4px solid var(--jade);background:var(--card);border-bottom:1px solid var(--line)}}
.mast{{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:26px 0 6px}}
.mast h1{{font-family:"Songti TC","STSong","Noto Serif TC","PMingLiU",serif;font-size:clamp(28px,5vw,40px);margin:0;letter-spacing:.05em}}
.mast h1 span{{color:var(--jade)}}
.mast-r{{display:flex;flex-direction:column;align-items:flex-end;gap:8px}}
.tag{{font-size:12px;letter-spacing:.24em;color:var(--muted);text-transform:uppercase}}
.langtog{{display:inline-flex;border:1px solid var(--line);border-radius:99px;overflow:hidden;background:var(--card)}}
.langtog button{{font:inherit;font-size:12px;letter-spacing:.04em;padding:5px 14px;border:0;background:transparent;color:var(--muted);cursor:pointer}}
.langtog button+button{{border-left:1px solid var(--line)}}
.langtog button.on{{background:var(--jade);color:#fff}}
.langtog button:focus-visible{{outline:2px solid var(--ink);outline-offset:2px}}
.dateline{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:0 0 14px;color:var(--muted);font-size:14px}}
.dateline b{{color:var(--ink);font-weight:600}}
#share{{border:1px solid var(--jade);background:var(--jade);color:#fff;font:inherit;font-size:13px;padding:7px 18px;border-radius:4px;cursor:pointer}}
#share:hover{{background:var(--jade-d)}}
#share:focus-visible{{outline:2px solid var(--ink);outline-offset:2px}}
.legend{{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:0 0 16px;font-size:12px;color:var(--muted)}}
.legend .chip{{margin-right:2px}}
.stats{{display:grid;grid-template-columns:repeat({len(data["sections"])},1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:24px}}
.stat{{background:var(--card);text-align:center;padding:14px 4px;text-decoration:none;color:var(--ink)}}
.stat b{{display:block;font-size:26px;color:var(--jade);font-variant-numeric:tabular-nums;font-family:"Songti TC","Noto Serif TC",serif}}
.stat span{{font-size:11.5px;color:var(--muted);line-height:1.3;display:block}}
.stat:hover{{background:#EEF4EF}}
nav{{position:sticky;top:0;z-index:5;background:rgba(246,247,244,.95);backdrop-filter:blur(4px);border-bottom:1px solid var(--line)}}
nav .wrap{{display:flex;gap:6px;overflow-x:auto;padding:10px 20px}}
nav a{{white-space:nowrap;font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);background:var(--card);padding:5px 12px;border-radius:99px}}
nav a i{{font-style:normal;color:var(--jade);margin-left:5px;font-variant-numeric:tabular-nums}}
nav a:hover{{border-color:var(--jade);color:var(--jade-d)}}
section{{scroll-margin-top:64px;margin:32px 0}}
h2{{font-family:"Songti TC","STSong","Noto Serif TC","PMingLiU",serif;font-size:21px;margin:0 0 14px;padding-bottom:8px;border-bottom:2px solid var(--ink);display:flex;align-items:baseline;gap:10px}}
h2 em{{font-style:normal;font-size:13px;color:var(--muted);font-family:"PingFang HK","Microsoft JhengHei",sans-serif;font-weight:400}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px 18px;display:flex;flex-direction:column;gap:8px}}
.ctop{{display:flex;justify-content:space-between;align-items:center;gap:8px}}
.no{{font-family:"Songti TC","Noto Serif TC",serif;font-size:20px;color:var(--jade);font-variant-numeric:tabular-nums}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}
.chip{{font-size:11px;padding:2px 9px;border-radius:99px;white-space:nowrap}}
.act{{color:#fff;font-weight:600}}
.a-use{{background:#1E8E5A}}.a-watch{{background:#2F6DB0}}.a-biz{{background:#C4622D}}
.region{{border:1px solid var(--line);color:var(--muted)}}
.card h3{{margin:0;font-size:16.5px;line-height:1.45;text-wrap:balance}}
.card h3 a{{color:var(--ink);text-decoration:none}}
.card h3 a:hover{{color:var(--jade-d);text-decoration:underline}}
.card h3 a:focus-visible{{outline:2px solid var(--jade);outline-offset:2px}}
.sum{{margin:0;font-size:14px;color:#38484C;flex:1}}
.why{{margin:0;font-size:13px;line-height:1.55;color:var(--jade-d);background:#EDF4F0;border-left:3px solid var(--jade);padding:6px 10px;border-radius:0 4px 4px 0}}
.why b{{display:inline-block;font-size:11px;font-weight:600;color:#fff;background:var(--jade);border-radius:3px;padding:0 6px;margin-right:7px;vertical-align:1px}}
.cfoot{{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:12.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:8px}}
.src{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.more{{color:var(--jade);text-decoration:none;font-weight:500;white-space:nowrap}}
.more:hover{{color:var(--jade-d);text-decoration:underline}}
footer{{border-top:1px solid var(--line);margin-top:44px;padding:22px 0 40px;font-size:13px;color:var(--muted)}}
footer b{{color:var(--ink)}}
#toast{{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;padding:9px 20px;border-radius:6px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .25s,transform .25s}}
#toast.on{{opacity:1;transform:translateX(-50%) translateY(0)}}
#sharebox{{display:none;gap:8px;align-items:center;padding:0 0 16px}}
#sharebox.on{{display:flex}}
#sharebox input{{flex:1;font:inherit;font-size:13px;padding:7px 10px;border:1px solid var(--jade);border-radius:4px;color:var(--ink);background:#fff;min-width:0}}
#sharebox span{{font-size:12px;color:var(--muted);white-space:nowrap}}
@media (max-width:640px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style>
</head>
<body>
<header><div class="wrap">
<div class="mast">
  <h1>{bi(SITE_TITLE, SITE_TITLE_EN)}</h1>
  <div class="mast-r">
    <span class="tag">{html.escape(SITE_TAGLINE)}</span>
    <div class="langtog" role="group" aria-label="Language / 語言">
      <button type="button" data-set="en" class="on" aria-label="English">EN</button>
      <button type="button" data-set="zh" aria-label="繁體中文">中文</button>
    </div>
  </div>
</div>
<div class="dateline"><span><b>{bi(date_disp, date_disp_en)}</b>　·　<span class="l-zh">今日精選 <b>{total}</b> 條</span><span class="l-en"><b>{total}</b> picks today</span></span><button id="share">{bi("分享俾同事", "Share")}</button></div>
<div id="sharebox"><span>{bi("長按/全選複製：", "Long-press / select all to copy:")}</span><input type="text" readonly value="{html.escape(SITE_URL)}"></div>
<div class="legend"><span class="chip act a-use">{bi("可即用", "Ready to use")}</span>{bi("今日試得／慳時間", "try today / save time")}　<span class="chip act a-watch">{bi("要留意", "Worth watching")}</span>{bi("平台或趨勢變動", "platform / trend shift")}　<span class="chip act a-biz">{bi("影響生意", "Business impact")}</span>{bi("agency 生態／客戶／合規", "agency / client / compliance")}</div>
<div class="stats">{stats}</div>
</div></header>
<nav><div class="wrap">{nav}</div></nav>
<main class="wrap">
{sections_html}
</main>
<footer><div class="wrap">
<p><span class="l-zh">今日共 <b>{total}</b> 條精選　·　每日更新　·　為 AI 驅動 agency 而設</span><span class="l-en"><b>{total}</b> picks today　·　updated daily　·　built for AI-driven agencies</span></p>
<p>{bi("數據源：", "Sources: ")}{bi(sources_note, sources_note_en)}</p>
<p>{bi("內容僅供資訊參考。", "For informational reference only.")}</p>
</div></footer>
<div id="toast"></div>
<script>
const SHARE_URL={json.dumps(SITE_URL) if SITE_URL else "location.href"};
const MSG={{zh:'連結已複製，可以直接 send 俾同事', en:'Link copied — share it with your team'}};
function curLang(){{return document.documentElement.getAttribute('data-lang')==='en'?'en':'zh'}}
function setLang(l){{
  document.documentElement.setAttribute('data-lang',l);
  document.documentElement.lang=(l==='en'?'en':'zh-Hant');
  try{{localStorage.setItem('amd-lang',l)}}catch(e){{}}
  document.querySelectorAll('.langtog button').forEach(b=>b.classList.toggle('on', b.dataset.set===l));
}}
document.querySelectorAll('.langtog button').forEach(b=>b.addEventListener('click',()=>setLang(b.dataset.set)));
setLang(curLang()); // sync button highlight with the pre-paint language
function toast(m){{const el=document.getElementById('toast');el.textContent=m;el.classList.add('on');setTimeout(()=>el.classList.remove('on'),2200)}}
function legacyCopy(){{const ta=document.createElement('textarea');ta.value=SHARE_URL;ta.style.cssText='position:fixed;opacity:0';document.body.appendChild(ta);ta.select();let ok=false;try{{ok=document.execCommand('copy')}}catch(e){{}}ta.remove();return ok}}
function showBox(){{const b=document.getElementById('sharebox');b.classList.add('on');const inp=b.querySelector('input');inp.value=SHARE_URL;inp.focus();inp.select()}}
document.getElementById('share').addEventListener('click',async()=>{{
  const msg=MSG[curLang()];
  if(navigator.share){{try{{await navigator.share({{title:document.title,url:SHARE_URL}});return}}catch(e){{if(e.name==='AbortError')return}}}}
  try{{await navigator.clipboard.writeText(SHARE_URL);toast(msg);return}}catch(e){{}}
  if(legacyCopy()){{toast(msg);return}}
  showBox();
}});
</script>
</body>
</html>
'''

(ROOT / "index.html").write_text(page, encoding="utf-8")
print(f"OK index.html total={total} sections=" + ",".join(f"{s}:{len(groups[s])}" for s in data["sections"])
      + (f"  ⚠ {_warn} warning(s) — 見上面 stderr" if _warn else "  (0 warnings)"))
