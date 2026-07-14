# -*- coding: utf-8 -*-
"""Build a single-file daily marketing-intelligence briefing index.html from data.json.

Marketer edition: each card shows an ACTION tag (可即用 / 要留意 / 影響生意)
plus a REGION tag (國際 / 中國 / 香港).

Config keys in data.json (optional unless noted):
  site_title   : masthead brand      (default "AI・行銷情報")
  site_tagline : uppercase tag        (default "AI Marketing Intelligence")
  site_url     : canonical URL        (default "" -> Share button uses location.href)
  date         : ISO date (<title>)                        [required]
  date_display : human date shown in hero
  sources_note : footer source list
  sections     : ordered section names                     [required]
  items[]      : {title, summary, source, url, time, section, action, region, why}  [required]

Run:  PYTHONIOENCODING=utf-8 python build.py
"""
import json, html, re, sys
from pathlib import Path

ROOT = Path(__file__).parent

# --- Load data.json with a clear error instead of a raw traceback -------------
# This script runs unattended every morning, so a missing/broken data.json must
# say exactly what to fix rather than dump a stack trace no one is watching.
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

SITE_TITLE   = data.get("site_title", "AI・行銷情報")
SITE_TAGLINE = data.get("site_tagline", "AI Marketing Intelligence")
SITE_URL     = data.get("site_url", "")

# action tag -> css class (semantic colours, separate from jade accent)
ACT = {"可即用": "a-use", "要留意": "a-watch", "影響生意": "a-biz"}
# region tag -> css class
REG = {"國際": "r-intl", "中國": "r-cn", "香港": "r-hk"}

SEC_ID = {s: f"sec{i}" for i, s in enumerate(data["sections"])}

# --- Validate items: warn (don't crash) so a typo shows up instead of silently -
# producing a wrong-coloured tag or a dropped card. Editorial limits per
# references/editorial-style-guide.md: summary <= 60 CJK chars, why <= 35.
def _cjk(s):
    return len(re.findall(r"[一-鿿]", s or ""))

_sections = set(data["sections"])
_warn = 0
for _i, _it in enumerate(data["items"], 1):
    _t = _it.get("title", f"(item #{_i}無標題)")
    for _f in ("title", "summary", "source", "url", "time", "section", "action", "region", "why"):
        if not _it.get(_f):
            print(f"WARN item {_i} 「{_t}」: 缺欄位 '{_f}'", file=sys.stderr); _warn += 1
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
        e = {k: html.escape(str(v)) for k, v in it.items()}
        act = it.get("action", "要留意")
        act_cls = ACT.get(act, "a-watch")
        reg = it.get("region", "")
        reg_cls = REG.get(reg, "r-other")
        out.append(f'''<article class="card">
<div class="ctop"><span class="no">{n:02d}</span><span class="chips"><span class="chip act {act_cls}">{html.escape(act)}</span><span class="chip region {reg_cls}">{e.get("region","")}</span></span></div>
<h3><a href="{e["url"]}" target="_blank" rel="noopener noreferrer">{e["title"]}</a></h3>
<p class="sum">{e.get("summary","")}</p>
<p class="why"><b>點解重要</b>{e.get("why", "")}</p>
<div class="cfoot"><span class="src">{e.get("source","")}　·　{e.get("time","")}</span><a class="more" href="{e["url"]}" target="_blank" rel="noopener noreferrer">閱讀原文 ↗</a></div>
</article>''')
    cards[s] = "\n".join(out)

total = n
stats = "".join(
    f'<a class="stat" href="#{SEC_ID[s]}"><b>{len(groups[s])}</b><span>{html.escape(s)}</span></a>'
    for s in data["sections"])
nav = "".join(
    f'<a href="#{SEC_ID[s]}">{html.escape(s)}<i>{len(groups[s])}</i></a>'
    for s in data["sections"])
sections_html = "\n".join(
    f'<section id="{SEC_ID[s]}"><h2>{html.escape(s)}<em>{len(groups[s])} 條</em></h2><div class="grid">{cards[s]}</div></section>'
    for s in data["sections"])

brand = html.escape(SITE_TITLE)

page = f'''<title>{brand} · {data.get("date","")}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{{--paper:#F6F7F4;--card:#FFFFFF;--ink:#1A2A2E;--muted:#5E6E6A;--jade:#0E7C66;--jade-d:#0A5C4C;--line:#DBE2D9}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang HK","PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif;line-height:1.6}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 20px}}
header{{border-top:4px solid var(--jade);background:var(--card);border-bottom:1px solid var(--line)}}
.mast{{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:26px 0 6px}}
.mast h1{{font-family:"Songti TC","STSong","Noto Serif TC","PMingLiU",serif;font-size:clamp(28px,5vw,40px);margin:0;letter-spacing:.05em}}
.mast h1 span{{color:var(--jade)}}
.tag{{font-size:12px;letter-spacing:.24em;color:var(--muted);text-transform:uppercase}}
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
<header><div class="wrap">
<div class="mast"><h1>{brand}</h1><span class="tag">{html.escape(SITE_TAGLINE)}</span></div>
<div class="dateline"><span><b>{html.escape(data.get("date_display",""))}</b>　·　今日精選 <b>{total}</b> 條</span><button id="share">分享俾同事</button></div>
<div id="sharebox"><span>長按/全選複製：</span><input type="text" readonly value="{html.escape(SITE_URL)}"></div>
<div class="legend"><span class="chip act a-use">可即用</span>今日試得／慳時間　<span class="chip act a-watch">要留意</span>平台或趨勢變動　<span class="chip act a-biz">影響生意</span>agency 生態／客戶／合規</div>
<div class="stats">{stats}</div>
</div></header>
<nav><div class="wrap">{nav}</div></nav>
<main class="wrap">
{sections_html}
</main>
<footer><div class="wrap">
<p>今日共 <b>{total}</b> 條精選　·　每日更新　·　為 AI 驅動 agency 而設</p>
<p>數據源：{html.escape(data.get("sources_note",""))}</p>
<p>內容僅供資訊參考。</p>
</div></footer>
<div id="toast">連結已複製，可以直接 send 俾同事</div>
<script>
const SHARE_URL={json.dumps(SITE_URL) if SITE_URL else "location.href"};
function toast(m){{const el=document.getElementById('toast');el.textContent=m;el.classList.add('on');setTimeout(()=>el.classList.remove('on'),2200)}}
function legacyCopy(){{const ta=document.createElement('textarea');ta.value=SHARE_URL;ta.style.cssText='position:fixed;opacity:0';document.body.appendChild(ta);ta.select();let ok=false;try{{ok=document.execCommand('copy')}}catch(e){{}}ta.remove();return ok}}
function showBox(){{const b=document.getElementById('sharebox');b.classList.add('on');const inp=b.querySelector('input');inp.value=SHARE_URL;inp.focus();inp.select()}}
document.getElementById('share').addEventListener('click',async()=>{{
  if(navigator.share){{try{{await navigator.share({{title:document.title,url:SHARE_URL}});return}}catch(e){{if(e.name==='AbortError')return}}}}
  try{{await navigator.clipboard.writeText(SHARE_URL);toast('連結已複製，可以直接 send 俾同事');return}}catch(e){{}}
  if(legacyCopy()){{toast('連結已複製，可以直接 send 俾同事');return}}
  showBox();
}});
</script>
'''

(ROOT / "index.html").write_text(page, encoding="utf-8")
print(f"OK index.html total={total} sections=" + ",".join(f"{s}:{len(groups[s])}" for s in data["sections"])
      + (f"  ⚠ {_warn} warning(s) — 見上面 stderr" if _warn else "  (0 warnings)"))
