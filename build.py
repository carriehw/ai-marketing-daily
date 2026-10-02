# -*- coding: utf-8 -*-
"""Build the daily "AI・行銷情報" briefing index.html from data.json.

Editorial edition (v2) — the card anatomy and page furniture now follow the
weekly brief at carriehw.github.io/carrie-ai-intelligence:

  masthead nav → hero (headline + meta chips + slim byline) → optional signal
  block → per-section coloured header → full story cards → footer

Bilingual (繁中 / English): a 中｜EN toggle switches the WHOLE page, persisted in
localStorage. Both languages are rendered and toggled via `data-lang` on <html>
plus CSS — no reload, works offline.

CARD ANATOMY (each block degrades gracefully if its field is absent)
  source pill · date · number
  headline (links to the original)
  昨日續篇 Since Yesterday  ← items[].followup (OPTIONAL — see "follow-ups" below)
  重點摘要 Key Highlights   ← items[].highlights[] (2–3 bullets); falls back to summary
  行業洞察 Industry Insight ← items[].why
  趨勢觀察 Pattern Watch    ← items[].pattern (OPTIONAL — forward-looking)
  signal tag · region tag · 閱讀原文 →

FOLLOW-UPS: SAY WHAT MOVED, DO NOT DELETE THE STORY
  Two different things get confused, so keep them apart:

  (a) The SAME ARTICLE twice. Same link on two days, or two cards for one link on
      one day. That is a genuine duplicate and the dedup pass below removes it.

  (b) A FOLLOW-UP — a DIFFERENT article that advances a story already published.
      Yesterday「OpenAI 失控 Agent 呼叫 DeepSeek 評估漏洞」, today「OpenAI 取消
      Astra 6.1 發布，欺騙性行為測試不達標」. Do NOT drop this as a duplicate:
      dropping it hides the outcome, which is the part the reader was waiting for.
      Instead fill `followup` with ONE sentence covering three things —
        1. where the earlier piece left off (name the day),
        2. what is DIFFERENT today,
        3. the latest state of the thread.
      e.g. followup: "9 月 28 日我們報過該 Agent 主動呼叫外部模型試探漏洞；今日
           OpenAI 直接取消 Astra 6.1 發布，理由是欺騙性行為測試不達標 —— 從
           『發現風險』走到『因風險停船』。"
      It renders as 昨日續篇 above 重點摘要, i.e. the first thing after the headline.

  The cross-day detection pass matches HEADLINES against seen-stories.json (7-day
  window). When it recognises a thread and `followup` is empty it prints a WARN
  telling the editor to add the sentence — explicitly NOT to delete the card.
  Use `pattern` for where the thread is heading; `followup` for what already moved.

Config keys in data.json (optional unless noted):
  site_title     : masthead brand      (default "AI・行銷情報")
  site_title_en  : masthead brand (EN)  (default "AI Marketing Daily")
  site_tagline   : uppercase tag        (default "AI Marketing Intelligence")
  site_url       : canonical URL        (default "" -> Share button uses location.href)
  date           : ISO date (<title>)                        [required]
  date_display   : human date shown in hero (中文)
  date_display_en: human date shown in hero (English)
  headline / headline_en   : hero headline (default "少一點 AI 噪音。多一點行銷訊號。")
  standfirst / standfirst_en: hero paragraph under the headline
  byline / byline_en       : slim credit line (default "Carrie Hui")
  byline_role / byline_role_en : role after the name
  weekly_url     : link to the weekly brief (shown in the byline when set)
  thesis / thesis_en       : today's one-sentence signal (accent block; omitted if absent)
  thesis_note / thesis_note_en : supporting paragraph under the thesis
  read_minutes   : integer, shown as a hero chip (default: estimated from item count)
  sources_note   : footer source list (中文)
  sources_note_en: footer source list (English)
  sections       : ordered section names (中文)              [required]
  sections_en    : ordered section names (English, same order/length as sections)
  section_emoji  : per-section emoji (same order; defaults per known section)
  section_desc / section_desc_en : one-line descriptor per section (same order)
  items[]        : {title, summary, source, url, time, section, action, region, why,
                    title_en, summary_en, why_en,
                    highlights[], highlights_en[], pattern, pattern_en,
                    followup, followup_en}

Any missing *_en field falls back to its Chinese value, so the site never breaks
on a day the translations are incomplete — it just shows Chinese in the EN view.

Run:  PYTHONIOENCODING=utf-8 python3 build.py
"""
import json, html, os, re, sys, hashlib, urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

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
    sys.exit(f"ERROR: data.json is not valid JSON — line {e.lineno} col {e.colno}: {e.msg}")

for _key in ("sections", "items", "date"):
    if _key not in data:
        sys.exit(f"ERROR: data.json missing required key '{_key}'.")
if not isinstance(data["items"], list) or not data["items"]:
    sys.exit("ERROR: data.json 'items' must be a non-empty list.")

SITE_TITLE    = data.get("site_title", "AI・行銷情報")
SITE_TITLE_EN = data.get("site_title_en", "AI Marketing Daily")
SITE_TAGLINE  = data.get("site_tagline", "AI Marketing Intelligence")
SITE_URL      = data.get("site_url", "")
WEEKLY_URL    = data.get("weekly_url", "")
# Carrie's own profile — this brief is her personal masthead, so the byline links
# out to her. Defaulted here rather than required in data.json: the routine writes
# data.json fresh every morning, and a field it forgets would silently drop the
# link on that day's issue only, which is the kind of gap nobody notices.
LINKEDIN_URL  = data.get("linkedin_url", "https://www.linkedin.com/in/carriehuiww/")
ISO           = str(data.get("date", "")).strip()

# --- Traffic counting --------------------------------------------------------
# GoatCounter rather than Google Analytics, for reasons that are constraints and
# not taste: this page is served from GitHub Pages with no server of its own, so
# first-party logging is not available at all; GA4 sets identifiers and puts the
# site inside GDPR/PDPO consent-banner territory for a daily brief that has no
# login and collects nothing else. GoatCounter stores no cookie and no device
# identifier, which keeps the page consent-free.
#
# The account lives HERE and not only in data.json — same reasoning as
# LINKEDIN_URL above, and for a sharper reason. The routine writes data.json
# fresh every morning from a session that has never seen yesterday's file. A
# config key it forgets raises nothing: the page builds, the deploy succeeds,
# every byte checks out, and the counter simply stops. Telling the routine to
# carry the key forward would mean fetching the 150KB+ data.json back from the
# repo to read one field, and that GET returns http_500 through the proxy (the
# same large-file trap the routine already documents for index.html). An
# instruction that cannot be followed is not a safeguard. So the default sits in
# code, where a fresh session cannot drop it; data.json still overrides.
#
# The default is a verified account, not a guess — an endpoint that does not
# exist would load on every reader's device, fail, and report nothing, and a
# counter that looks wired while measuring zero is worse than no counter, because
# the zero reads as "nobody visited" rather than "never connected". Measured
# 2026-10-02: /count?test=1 on this code -> HTTP 200, while the same path on a
# nonexistent account -> HTTP 400, so the 200 really does identify the account.
# To switch counting off, set `"analytics": {"provider": ""}` in data.json.
_AN_DEFAULT = {"provider": "goatcounter", "code": "carriehuiww"}
_an = data.get("analytics")
if not isinstance(_an, dict) or not _an:
    _an = dict(_AN_DEFAULT)
_an_provider = str(_an.get("provider", "")).strip().lower()
_an_code = str(_an.get("code", "")).strip()
# Self-hosted or custom domain allowed; default to the hosted service.
_an_host = str(_an.get("host", "")).strip() or (
    f"https://{_an_code}.goatcounter.com" if _an_code else "")
# The counting endpoint and the script live on DIFFERENT hosts, and conflating
# them is a silent-zero bug. Measured 2026-10-02:
#   https://carriehuiww.goatcounter.com/count.js  -> 404
#   https://gc.zgo.at/count.js                    -> 200, 9213 bytes
# (validity control: a nonexistent *.goatcounter.com returns 400, so the 404 is
# a real "this path does not exist here", not a catch-all.) The per-site
# subdomain accepts the /count hit only; the script is served centrally. Build
# the src from `script_host` and keep data-goatcounter pointing at her /count —
# count.js reads the endpoint via querySelector('script[data-goatcounter]'), it
# does not infer it from its own src, so the two may differ.
_an_script = (str(_an.get("script_host", "")).strip().rstrip("/")
              or "https://gc.zgo.at") + "/count.js"
_analytics = ""
if _an_provider == "goatcounter" and _an_code and _an_host:
    _an_ep = _an_host.rstrip("/") + "/count"
    _analytics = f'''
<script>
/* Cookie-free hit counter. Three guards, each for a specific failure:
   1. DNT / Global Privacy Control — honoured before the request, not by asking
      the vendor to honour it. If the reader signalled no tracking, the script is
      never fetched, so there is nothing to opt out of afterwards.
   2. localhost / file:// — otherwise every local build-and-check run in this
      pipeline would post a hit and inflate the numbers I then report to her.
   3. A load error is swallowed. The counter must never be able to break the
      page it is measuring. */
(function(){{try{{
  var n=navigator;
  if(n.doNotTrack==='1'||n.msDoNotTrack==='1'||window.doNotTrack==='1'
     ||n.globalPrivacyControl===true)return;
  var h=location.hostname;
  if(location.protocol==='file:'||h==='localhost'||h==='127.0.0.1'||h==='')return;
  var s=document.createElement('script');
  s.async=true;s.defer=true;
  s.src='{_an_script}';
  s.setAttribute('data-goatcounter','{_an_ep}');
  s.onerror=function(){{}};
  document.head.appendChild(s);
}}catch(e){{}}}})();
</script>'''

# action tag -> css class + English label
ACT = {"可即用": "act", "要留意": "watch", "影響生意": "impact"}
ACT_EN = {"可即用": "Ready to use", "要留意": "Worth watching", "影響生意": "Business impact"}
# region tag -> css class + English label
REG = {"國際": "r-intl", "中國": "r-cn", "香港": "r-hk"}
REG_EN = {"國際": "Global", "中國": "China", "香港": "HK"}

SEC_ID = {s: f"sec{i}" for i, s in enumerate(data["sections"])}
# Colour class per section, 1-based to match the --c1..--c5 CSS vars; a 6th
# section wraps round to c1 rather than falling back to grey.
SEC_CLS = {s: f"c{(i % 5) + 1}" for i, s in enumerate(data["sections"])}

_STOP = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "its",
         "with", "from", "as", "is", "are", "all", "by", "into", "out", "up", "new"}


def story_slug(it):
    """Content-derived anchor id, so a shared link keeps pointing at the story
    the reader actually saw.

    Every card used to be s1..s27, renumbered by that morning's section order.
    Measured against the real archived pages, `#s7` resolved to four different
    stories on four consecutive days (9/25 阿里 Token Foundry, 9/28 CTV 代理,
    9/29 ChatGPT Sponsored Agents, 9/30 Amazon 買量後台) — so a link a colleague
    pasted into Slack pointed at unrelated news within a day.

    Shape: <up-to-5 English title words>-<6 hex of the normalised URL>.
    The hash is the durable half: it is taken from host+path with `www.` and any
    trailing slash removed, so the same story keeps the same suffix even when the
    headline is reworded between days. Verified on the two URLs that recur in
    seen-stories.json — the ChatGPT Sponsored Agents piece ran on 9/20 and 9/29
    under different headlines and both resolve to `…-92c832`; Canva ProSuite
    likewise to `…-b2a652`. That is why RESOLVER below is keyed on the suffix,
    not on the whole slug.
    """
    en = str(it.get("title_en") or it.get("title") or "")
    words = [w for w in re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-").split("-") if w]
    head = "-".join([w for w in words if w not in _STOP][:5]) or "story"
    p = urllib.parse.urlsplit(str(it.get("url") or ""))
    norm = (p.netloc.lower().replace("www.", "") + p.path.rstrip("/")).encode()
    return f"{head}-{hashlib.sha1(norm).hexdigest()[:6]}"
# section -> English name (parallel array, fall back to the Chinese name)
_sections_en = data.get("sections_en", [])
SEC_EN = {}
for _i, _s in enumerate(data["sections"]):
    SEC_EN[_s] = _sections_en[_i] if _i < len(_sections_en) else _s

# section -> emoji + descriptor. data.json may override via parallel arrays;
# otherwise fall back to the defaults for the five standing sections.
_SEC_DEFAULTS = {
    "AI 大模型 & 市場動態": ("🧠", "今日 AI 產業最大的動作。", "The biggest moves in AI this morning."),
    "廣告平台 & 行銷科技": ("📣", "平台規則、廣告產品與行銷科技的變動。", "Platform rules, ad products and martech shifts."),
    "創意生產工具":       ("🎬", "出稿、剪輯、生圖的新工具與功能。", "New tools and features for creative output."),
    "行業影響 & 品牌案例": ("📈", "代理商生態、客戶動向與品牌實例。", "Agency landscape, client moves and brand cases."),
    "即學技巧 & 玩法":     ("⚡", "今天就能實際操作的做法。", "Concrete plays you can try today."),
}
_emoji_in   = data.get("section_emoji", [])
_desc_in    = data.get("section_desc", [])
_desc_en_in = data.get("section_desc_en", [])
SEC_EMOJI, SEC_DESC, SEC_DESC_EN = {}, {}, {}


def _norm_sec(s):
    """Match section names ignoring spaces and full/half-width punctuation.

    data.json shipped "AI大模型 & 市場動態" while _SEC_DEFAULTS keys on
    "AI 大模型 & 市場動態" — one space apart. The dict lookup missed, fell through
    to ("📌", "", ""), and the first category rendered with an EMPTY description
    and a generic pin emoji while the other four were fine. No error, no warning:
    a silent downgrade, visible only by measuring that the rendered .cat-desc had
    no text rects at all. Normalising both sides makes spacing irrelevant.
    """
    return re.sub(r"[\s　]+", "", (s or "")).replace("＆", "&")


_SEC_DEFAULTS_N = {_norm_sec(k): v for k, v in _SEC_DEFAULTS.items()}
_missing_desc = []
for _i, _s in enumerate(data["sections"]):
    _d = _SEC_DEFAULTS_N.get(_norm_sec(_s), ("📌", "", ""))
    if _d[1] == "" and not (_i < len(_desc_in) and _desc_in[_i]):
        _missing_desc.append(_s)
    SEC_EMOJI[_s]   = _emoji_in[_i]   if _i < len(_emoji_in)   and _emoji_in[_i]   else _d[0]
    SEC_DESC[_s]    = _desc_in[_i]    if _i < len(_desc_in)    and _desc_in[_i]    else _d[1]
    SEC_DESC_EN[_s] = _desc_en_in[_i] if _i < len(_desc_en_in) and _desc_en_in[_i] else (_d[2] or SEC_DESC[_s])

if _missing_desc:
    print("WARN 分類說明缺失（會渲染成空白的 .cat-desc）：" + "、".join(_missing_desc),
          "\n     → 在 _SEC_DEFAULTS 補這個分類，或在 data.json 的 section_desc 補上對應位置。",
          file=sys.stderr)

_MONTH_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def _time_en(t):
    """「7月15日」 -> 「Jul 15」; anything else passes through unchanged."""
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


def bi_attr(zh, en=None):
    """Bilingual text for an ATTRIBUTE value (aria-label, title, alt).

    `bi()` must never be used here. It emits two <span> ELEMENTS, and an attribute
    cannot contain elements — the markup gets escaped into the value, so a screen
    reader announces the literal string
    `<span class="l-zh">回到頁首</span><span class="l-en">Back to top</span>`.
    Measured in the rendered DOM: three attributes were doing exactly that
    (#totop, #a2hs-x, and the LinkedIn byline link).

    The language toggle works by CSS on `data-lang`, which can only reach elements,
    so there is no way to switch an attribute at all — both languages have to sit in
    the one value. `zh / en` is the form the page already uses at the language
    switcher (`aria-label="Language / 語言"`), so it stays consistent with that.
    Returns a RAW string: escape at the call site, once, like any other attribute.
    """
    zh_s = "" if zh is None else str(zh)
    en_s = "" if en is None else str(en)
    if not en_s or en_s == zh_s:
        return zh_s
    return f"{zh_s} / {en_s}"

# =============================================================================
# DEDUP PASS — a story may appear ONCE per issue, and should not repeat a story
# published in the last 7 days. Same-URL repeats are DROPPED (they are the
# "one story, two cards" failure); near-duplicate titles and cross-day repeats
# are flagged loudly for the editor to resolve.
# =============================================================================
_warn = 0

def _norm_url(u):
    """Canonical form for comparison: drop scheme, www, tracking query, trailing /."""
    u = (u or "").strip()
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)
    u = re.split(r"[?#]", u)[0]
    return u.rstrip("/").lower()

# Outlets that meter or wall their articles. Readers were clicking through and
# landing on a subscribe screen with no warning, which reads as a broken link.
# Flagging the card sets the expectation, and the expandable 詳細內容 means the
# substance is still on the page. data.json can extend this via "paywall_domains",
# and any single item can force the flag on/off with "paywall": true/false.
_PAYWALL_DOMAINS = {
    "adage.com", "campaignasia.com", "the-decoder.com", "techcrunch.com",
    "wsj.com", "ft.com", "nytimes.com", "bloomberg.com", "economist.com",
    "theinformation.com", "businessinsider.com", "digiday.com", "adexchanger.com",
    "marketingweek.com", "campaignlive.co.uk", "campaignlive.com", "forbes.com",
    "hbr.org", "washingtonpost.com", "theatlantic.com", "wired.com",
    "technologyreview.com", "nikkei.com", "scmp.com", "caixin.com",
    "cailianpress.com", "36kr.com", "theverge.com", "axios.com", "semafor.com",
}
_PAYWALL_DOMAINS |= {str(d).strip().lower().lstrip(".")
                     for d in (data.get("paywall_domains") or []) if str(d).strip()}

def _host(u):
    """Bare registrable-ish host: no scheme, no www, no port, no path."""
    h = re.sub(r"^https?://", "", (u or "").strip(), flags=re.I)
    h = re.split(r"[/?#]", h)[0]
    h = re.sub(r"^www\.", "", h, flags=re.I)
    return h.split(":")[0].lower()

def _is_paywalled(it):
    """Explicit per-item flag wins; otherwise match the host or any parent domain
    (so news.adage.com and adage.com both hit the adage.com entry)."""
    if "paywall" in it:
        return bool(it["paywall"])
    h = _host(it.get("url", ""))
    if not h:
        return False
    parts = h.split(".")
    return any(".".join(parts[i:]) in _PAYWALL_DOMAINS for i in range(len(parts) - 1))

def _is_bare_domain(u):
    """True when the url is a homepage/section index rather than an article
    permalink — those make distinct stories look identical and defeat dedup."""
    p = _norm_url(u)
    if not p:
        return False
    path = p.split("/", 1)[1] if "/" in p else ""
    if not path:
        return True
    # one short slug with no hyphen/digits (e.g. "news", "blog") is still an index
    return "/" not in path and len(path) < 12 and not re.search(r"[-_0-9]", path)

# Words too common in this beat to identify a story. Two cards both saying
# 「AI 模型」 tell us nothing; two both saying 「fable」「5.1」 are the same story.
_STOP = set("""ai the and for a an of to in on at is are with new news blog api app
report update launch open source model models data cloud tech beta pro max plus
模型 行銷 品牌 工具 平台 功能 推出 發布 上線 生成 內容 廣告 用戶 企業 市場 測試 支援
客戶 代理 業務 服務 系統 版本 團隊 公司 收入 增長 影響 宣布 表示 全球 香港 中國 美國
今日 已經 可以 一個 呢個 嘅係 同埋 以及""".split())

def _terms(t):
    """Distinctive terms in a headline: latin words/version numbers plus CJK
    trigrams. Used to tell 'same story, new angle' from 'different story that
    merely names the same vendor'."""
    t = (t or "").lower()
    out = set(re.findall(r"[a-z][a-z0-9.+-]{2,}|\d+\.\d+", t))
    cj = re.sub(r"[^一-鿿]+", "", t)
    out |= {cj[i:i+3] for i in range(len(cj) - 2)}
    return {x for x in out if x not in _STOP}

_CJ3 = re.compile(r"^[一-鿿]{3}$")

def _merge_phrases(shared):
    """Glue overlapping CJK trigrams back into the phrase they came from.

    _terms() slides a 3-char window, so the single phrase 程序化廣告 emits
    {程序化, 序化廣, 化廣告} — three "terms" that are one piece of evidence. Counting
    them separately made any two headlines sharing ONE ordinary phrase look like a
    3-term match, which is why 「IAB Europe：86% 廣告業者已用 AI 處理程序化廣告」 was
    reported as a follow-up to 「Scope3 更名為 Apostra…程序化廣告」 — unrelated stories
    that merely use the same industry term. Merging first means the evidence count
    counts distinct phrases, which is what the 2+ threshold was always meant to mean."""
    parts = sorted(x for x in shared if _CJ3.match(x))
    other = sorted(x for x in shared if not _CJ3.match(x))
    grew = True
    while grew:
        grew = False
        for a in list(parts):
            for b in list(parts):
                if a == b:
                    continue
                if a[-2:] == b[:2]:                 # 程序化 + 序化廣 -> 程序化廣
                    parts = [p for p in parts if p not in (a, b)] + [a + b[2:]]
                    grew = True
                    break
            if grew:
                break
    parts = [p for p in parts if not any(p != q and p in q for q in parts)]
    return set(parts) | set(other)

# Phrases that name a whole category rather than a specific story. Two headlines
# sharing only these are about the same INDUSTRY, not the same event, so they must
# not count as follow-up evidence on their own.
_GENERIC = {"agent", "agents", "platform", "chatbot", "assistant", "copilot",
            "程序化廣告", "推出對話", "對話式", "生成式", "大模型", "智能體",
            "程序化", "廣告主", "媒體代理", "代理商", "人工智能", "自動化"}

# Document frequency across today's items: a term used by many cards (e.g.
# "google" on a Google-heavy day) carries no identifying power.
_TERMS = [_terms(i.get("title", "")) for i in data["items"]]
_DF = {}
for _s in _TERMS:
    for _x in _s:
        _DF[_x] = _DF.get(_x, 0) + 1

def _rare(s):
    return {x for x in s if _DF.get(x, 0) <= 2}

def _shared_terms(i, j):
    """Story-specific phrases two headlines have in common. Empirically: 0–1 shared
    phrase = unrelated stories about the same vendor; 2+ = the same story re-angled.

    Trigrams are merged and category words dropped before counting, so 「Nvidia 推出
    Open Agent Safety Platform」 and 「Meta 發布 Enterprise Platform，Muse Agent…」 no
    longer count as one story on the strength of agent+platform alone."""
    _sh = _merge_phrases(_rare(_TERMS[i]) & _rare(_TERMS[j]))
    return {x for x in _sh if x not in _GENERIC and len(x) >= 3}

def _title_key(t):
    """Strip everything but CJK chars and latin word chars, for fuzzy compare."""
    return re.sub(r"[^\w一-鿿]+", "", (t or "")).lower()

def _bigrams(s):
    return {s[i:i+2] for i in range(len(s) - 1)} or ({s} if s else set())

def _similar(a, b):
    """Character-bigram Jaccard — works for both Chinese and English titles."""
    A, B = _bigrams(_title_key(a)), _bigrams(_title_key(b))
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

# ---- 1) same URL twice in this issue ----------------------------------------
# A repeated PERMALINK is the "one story, two cards" bug -> drop the later card.
# A repeated BARE DOMAIN (e.g. anthropic.com/news) is more often two different
# stories that were both under-linked, so only drop when the headlines also look
# alike — otherwise keep both and shout about the url. Dropping there would
# silently delete real news.
_drop = set()
_by_url = {}
for _i, _it in enumerate(data["items"]):
    _k = _norm_url(_it.get("url", ""))
    if not _k:
        continue
    if _k not in _by_url:
        _by_url[_k] = _i
        continue
    _j = _by_url[_k]
    _first = data["items"][_j]
    _sh = _shared_terms(_i, _j)
    # A real permalink can only describe one story. A bare domain needs the
    # headline evidence too — 2+ shared rare terms means it's the same story.
    if not _is_bare_domain(_it.get("url", "")) or len(_sh) >= 2:
        print(f"DROP 重複：「{_it.get('title','')}」（{_it.get('section','')}）"
              f"\n     同「{_first.get('title','')}」（{_first.get('section','')}）係同一則報道"
              + (f"，共同關鍵詞：{'、'.join(sorted(_sh))}" if _sh else "")
              + f"\n     連結：{_it.get('url','')}"
              f"\n     → 一則新聞全份只出一張卡。要補實操角度，寫入原卡嘅 pattern 欄，唔好開第二張。",
              file=sys.stderr)
        _warn += 1
        _drop.add(_i)
    else:
        print(f"WARN 兩則唔同新聞共用同一條連結：\n"
              f"     [{_first.get('section','')}] {_first.get('title','')}\n"
              f"     [{_it.get('section','')}] {_it.get('title','')}\n"
              f"     共用：{_it.get('url','')}\n"
              f"     → 兩張卡都留，各自要補回原文 permalink。", file=sys.stderr)
        _warn += 1

# ---- 2) different urls, same story re-angled -> warn -------------------------
# This is the failure the URL check cannot see: the same event written up twice
# from two outlets (or rewritten as a how-to) and filed under two sections.
for _i in range(len(data["items"])):
    if _i in _drop:
        continue
    for _j in range(_i + 1, len(data["items"])):
        if _j in _drop or _norm_url(data["items"][_i].get("url", "")) == _norm_url(data["items"][_j].get("url", "")):
            continue
        _a, _b = data["items"][_i], data["items"][_j]
        _sh = _shared_terms(_i, _j)
        if len(_sh) >= 2 or _similar(_a.get("title", ""), _b.get("title", "")) >= 0.55:
            print(f"WARN 疑似同一則新聞出兩次"
                  + (f"（共同關鍵詞：{'、'.join(sorted(_sh))}）" if len(_sh) >= 2 else "（標題高度相似）")
                  + f"：\n     [{_a.get('section','')}] {_a.get('title','')}\n"
                  f"     [{_b.get('section','')}] {_b.get('title','')}\n"
                  f"     → 若係同一件事，只留一張卡，另一個角度寫入 pattern 欄。", file=sys.stderr)
            _warn += 1

if _drop:
    data["items"] = [_it for _i, _it in enumerate(data["items"]) if _i not in _drop]

# ---- 3) bare-domain urls -> warn (breaks dedup AND the reader's trust) -------
for _it in data["items"]:
    if _is_bare_domain(_it.get("url", "")):
        print(f"WARN 唔係原文永久連結：「{_it.get('title','')}」→ {_it.get('url','')}"
              f"\n     → 要指向該篇文章嘅 permalink，唔好只填網域首頁。", file=sys.stderr)
        _warn += 1

# ---- 4) cross-day repeat -> warn against the last 7 days of seen-urls.json ---
# seen-urls.json shape: {"2026-09-02": ["example.com/a", ...], ...}
# The file is updated at the end of this script (idempotent: today's own entry
# is rewritten, never compared against itself).
_seen_path = ROOT / "seen-urls.json"
_seen = {}
if _seen_path.is_file():
    try:
        _seen = json.loads(_seen_path.read_text(encoding="utf-8"))
        if not isinstance(_seen, dict):
            _seen = {}
    except Exception:
        print("WARN seen-urls.json 讀唔到／格式唔對 → 當空，跨日查重今日跳過", file=sys.stderr)
        _seen = {}

_recent = {}   # normalized url -> the date it was published
if ISO:
    try:
        _today = datetime.strptime(ISO, "%Y-%m-%d")
        for _d, _urls in _seen.items():
            if _d == ISO:                     # never compare today against itself
                continue
            try:
                _age = (_today - datetime.strptime(_d, "%Y-%m-%d")).days
            except Exception:
                continue
            if 0 <= _age <= 7:
                for _u in (_urls or []):
                    _recent.setdefault(_norm_url(_u), _d)
    except Exception:
        pass

for _it in data["items"]:
    _prev = _recent.get(_norm_url(_it.get("url", "")))
    if _prev:
        print(f"WARN 七日內出過：「{_it.get('title','')}」（{_prev} 已出）→ {_it.get('url','')}"
              f"\n     → 若有新進展，寫入原卡跟進；若冇新料，今日剔走。", file=sys.stderr)
        _warn += 1

# ---- 5) cross-day FOLLOW-UP: same developing story, different article --------
# The url check above only catches the identical link. The case the reader
# actually cares about is a follow-up: yesterday 「OpenAI 失控 Agent 呼叫 DeepSeek
# 評估漏洞」, today 「OpenAI 取消 Astra 6.1 發布，欺騙性行為測試不達標」 — two
# different articles on one developing thread. Deleting the second would hide the
# outcome; running it cold makes the reader reconstruct the context themselves.
#
# So we MATCH ON HEADLINES (seen-stories.json) and require the newer card to say
# what moved. That sentence goes in `followup` and renders as 「昨日續篇」 above
# the summary — the one thing a daily brief can offer that a search cannot.
_stories_path = ROOT / "seen-stories.json"
_stories = {}
if _stories_path.is_file():
    try:
        _stories = json.loads(_stories_path.read_text(encoding="utf-8"))
        if not isinstance(_stories, dict):
            _stories = {}
    except Exception:
        print("WARN seen-stories.json 讀唔到／格式唔對 → 當空，跨日續篇偵測今日跳過",
              file=sys.stderr)
        _stories = {}

# Past headlines within 7 days, newest first, excluding today's own entry.
_past = []
if ISO:
    try:
        _t0 = datetime.strptime(ISO, "%Y-%m-%d")
        for _d in sorted(_stories, reverse=True):
            if _d == ISO or not re.match(r"^\d{4}-\d{2}-\d{2}$", _d):
                continue
            try:
                _ag = (_t0 - datetime.strptime(_d, "%Y-%m-%d")).days
            except Exception:
                continue
            if 1 <= _ag <= 7:
                for _e in (_stories[_d] or []):
                    _ttl = (_e.get("t") if isinstance(_e, dict) else str(_e)) or ""
                    if _ttl.strip():
                        _past.append((_d, _ttl.strip(), (_e.get("u") if isinstance(_e, dict) else "") or ""))
    except Exception:
        pass

if _past:
    # Rarity is judged across the WHOLE window, not just today: a term in many
    # past headlines (google, openai on a busy week) identifies nothing.
    _pdf = {}
    for _d, _ttl, _u in _past:
        for _x in _terms(_ttl):
            _pdf[_x] = _pdf.get(_x, 0) + 1
    _PAST_RARE = [(_d, _ttl, _u, {x for x in _terms(_ttl) if _pdf.get(x, 0) <= 3})
                  for _d, _ttl, _u in _past]

    for _i, _it in enumerate(data["items"]):
        _k = _norm_url(_it.get("url", ""))
        if _recent.get(_k):
            continue          # already flagged as the identical link above
        _mine = _rare(_TERMS[_i])
        if not _mine:
            continue
        _best, _bsh, _bscore = None, set(), 0
        for _d, _ttl, _u, _prare in _PAST_RARE:
            if _u and _u == _k:
                continue
            # Merge overlapping trigrams FIRST, then drop category words. What is
            # left is the count of distinct, story-specific things the two headlines
            # share — the only number the 2+ threshold can honestly be applied to.
            _sh = _merge_phrases(_mine & _prare)
            _ev = {x for x in _sh if x not in _GENERIC and len(x) >= 3}
            _sim = _similar(_it.get("title", ""), _ttl)
            # 2+ specific phrases in common, or a near-identical headline.
            if len(_ev) >= 2 or _sim >= 0.5:
                _score = len(_ev) * 10 + int(_sim * 10)
                if _score > _bscore or _best is None:
                    _best, _bsh, _bscore = (_d, _ttl), _ev or _sh, _score
        if not _best:
            continue
        _fu = str(_it.get("followup", "") or _it.get("followup_en", "")).strip()
        if _fu:
            print(f"NOTE 續篇已註明：「{_it.get('title','')}」"
                  f"\n     接住 {_best[0]}「{_best[1]}」", file=sys.stderr)
        else:
            print(f"WARN 呢則係 {_best[0]} 嘅續篇，但冇寫明新進展："
                  f"\n     今日：{_it.get('title','')}"
                  f"\n     {_best[0]}：{_best[1]}"
                  + (f"\n     共同關鍵詞：{'、'.join(sorted(_bsh))}" if _bsh else "")
                  + f"\n     → 唔好剔走呢則。加 `followup`（＋`followup_en`）一句，"
                  f"講明昨日講到邊、今日有咩唔同、最新發展係乜。讀者最需要嘅就係呢句。",
                  file=sys.stderr)
            _warn += 1

# =============================================================================
# 繁體中文正規化 — the audience is Taiwan AND Hong Kong, plus clients who forward
# this into decks. Spoken-Cantonese particles (嘅/係/唔/冇/啲) read as broken
# Chinese to a Taiwanese reader and as too casual in a client-facing document,
# so the published copy is standard written Traditional Chinese.
#
# Only unambiguous function words are auto-corrected. Words whose replacement
# depends on meaning (同 = 與/和/一樣, 話 = 說/話) are flagged for the editor
# instead of guessed at — a wrong auto-fix is worse than a warning.
# =============================================================================
_ZH_FIX = {
    # multi-char entries first in intent; the loop sorts by length so
    # 唔係→不是 wins over 唔→不 regardless of dict order.
    "唔係": "不是", "唔使": "不必", "唔好": "不要", "唔止": "不只",
    "而家": "現在", "即刻": "立即", "點做": "如何做", "咁樣": "這樣",
    "嗰個": "那個", "湊數": "充數", "毋須": "無須", "慳返": "節省",
    "慳": "節省", "睇": "查看", "搵": "尋找", "攞": "取得", "諗": "思考",
    "嘅": "的", "係": "是", "唔": "不", "冇": "沒有", "啲": "些",
    "喺": "在", "咁": "這麼", "咩": "什麼", "嗰": "那", "嚟": "來",
    "俾": "給", "畀": "給", "喇": "了", "嘢": "東西", "哋": "們",
    "乜": "什麼", "咪": "就",
}
# Ambiguous — warn, never rewrite. A wrong auto-fix is worse than a warning.
# Each entry masks its own standard-Chinese compounds first, otherwise the editor
# gets a warning on every 值得/話語/返回 and stops reading the warnings at all.
_ZH_FLAG = {
    "話": (r"話語|話題|說話|電話|對話|神話|笑話|話術|童話|會話|通話|佳話|話筒",
           "若作「說」用要改成「說」"),
    "得": (r"值得|獲得|取得|得到|得以|使得|懂得|覺得|記得|贏得|難得|心得|得力|所得|得獎|不得不|得失",
           "若作「可以」用（如「試得」）要改寫"),
    "返": (r"返回|返還|往返|回返|返修|遣返|返程|返鄉|返利",
           "若作「回」用（如「攞返」）要改寫"),
}
# 「同」 is 與/和 when it joins two things, but 相同/同步/共同/同質 are standard
# Chinese and must not be touched — so match the conjunction, not the character.
# 同比/同項/同級 are the ones that bite in this beat: a price table writes
# 「Astra 同項為 10／1／50 美元」and a market report writes 「同比增長超過 100%」,
# both of which a blind conjunction swap turns into 與項/與比 — reads as a typo.
_TONG_OK = re.compile(r"(相同|同步|共同|同質|同時|同業|同一|同事|認同|同意|不同|同期|同類|同儕|同盟|同行|同名|贊同|雷同"
                      r"|同比|同項|同級|同款|同價|同等|同組|同區|同日|同月|同年|同源|同檔|同城|同齡|同儕|同僚|同窗|同好)")
# the space is optional because Latin brand names get one ("整合同 AI 原生對手")
_TONG_CONJ = re.compile(r"([一-鿿A-Za-z0-9]{2,10})( ?)同( ?)([一-鿿A-Za-z0-9]{2,10})")

def _fix_tong(t):
    """Replace the conjunction 同 with 與, leaving compound words alone."""
    if not t or "同" not in t:
        return t, False
    holes, kept = [], t
    # mask the standard compounds so the conjunction regex cannot see them
    def _mask(m):
        holes.append(m.group(0))
        return f"\x00{len(holes)-1}\x00"
    kept = _TONG_OK.sub(_mask, kept)
    new = _TONG_CONJ.sub(lambda m: f"{m.group(1)}{m.group(2)}與{m.group(3)}{m.group(4)}", kept)
    changed = new != kept
    for _i, _h in enumerate(holes):
        new = new.replace(f"\x00{_i}\x00", _h)
    return new, changed
# --- HK vs TW term divergence ------------------------------------------------
# One page serves both markets, so the copy uses the term a reader in EITHER
# market parses without friction. Where the two diverge, prefer the form that is
# also understood in HK (數據/影片/介面) over the HK-only one (質素/服務器/數碼).
# Registered names are exempt: 電通數碼 is Dentsu Digital's actual company name,
# so a blind 數碼→數位 swap would corrupt it. Hence _TERM_KEEP is checked first.
# 中國互聯網絡信息中心 (CNNIC) is a registered body name — 網絡 is part of the name,
# so the generic 網絡→網路 swap would rename the institution it cites.
_TERM_KEEP = re.compile(r"(電通數碼|數碼通|數碼港|香港數碼|數碼營銷署"
                        r"|中國互聯網絡信息中心|互聯網絡信息中心)")
_TERM_FIX = {
    "服務器": "伺服器", "軟件": "軟體", "硬件": "硬體", "網絡": "網路",
    "質素": "品質", "視頻": "影片", "激活": "啟用", "缺省": "預設",
    "界面": "介面", "分辨率": "解析度", "帶寬": "頻寬", "打印": "列印",
    "博客": "部落格", "郵箱": "信箱", "屏幕": "螢幕", "鼠標": "滑鼠",
    "智能手機": "智慧型手機", "數碼": "數位",
}

def _fix_terms(t):
    """Normalize HK-only tech terms, protecting registered proper nouns."""
    if not t:
        return t, []
    holes, out, applied = [], str(t), []
    def _mask(m):
        holes.append(m.group(0))
        return f"\x01{len(holes)-1}\x01"
    out = _TERM_KEEP.sub(_mask, out)
    for _k in sorted(_TERM_FIX, key=len, reverse=True):
        if _k in out:
            out = out.replace(_k, _TERM_FIX[_k])
            applied.append((_k, _TERM_FIX[_k]))
    for _i, _h in enumerate(holes):
        out = out.replace(f"\x01{_i}\x01", _h)
    return out, applied

_ZH_FIELDS = ("title", "summary", "why", "pattern")

# 係 is 是 on its own, and it is also the second character of standard-Chinese
# compounds (關係/體系/聯係is not a word, 關係 is). A blind 係→是 turns 關係 into
# 關是 — a silent corruption that reads as a typo in a client-facing page, so the
# compounds are masked before the particle pass runs.
_ZH_KEEP = re.compile(r"(關係|聯繫|體系|系統|世系|派系|語系|直系|母系|父系"
                      r"|同場|在場|臨場|現場|場次|入場|離場|全場|開場|收場)")


def _to_written_zh(t):
    """Return (fixed_text, [(from, to), ...]) — longest keys first so 唔係→不是
    wins over 唔→不."""
    if not t:
        return t, []
    out, applied = str(t), []
    # mask standard-Chinese compounds that contain a particle character, so the
    # particle pass and the 同-conjunction pass cannot break them apart
    _keep = []

    def _mask_keep(m):
        _keep.append(m.group(0))
        return f"\x02{len(_keep) - 1}\x02"

    out = _ZH_KEEP.sub(_mask_keep, out)
    for _k in sorted(_ZH_FIX, key=len, reverse=True):
        if _k in out:
            out = out.replace(_k, _ZH_FIX[_k])
            applied.append((_k, _ZH_FIX[_k]))
    out, _tong = _fix_tong(out)
    if _tong:
        applied.append(("A同B", "A與B"))
    out, _terms = _fix_terms(out)
    applied.extend(_terms)
    for _i, _h in enumerate(_keep):
        out = out.replace(f"\x02{_i}\x02", _h)
    return out, applied

_zh_fixed_n = 0
for _i, _it in enumerate(data["items"], 1):
    for _f in _ZH_FIELDS:
        _v = _it.get(_f)
        if isinstance(_v, str) and _v:
            _new, _app = _to_written_zh(_v)
            if _app:
                _it[_f] = _new
                _zh_fixed_n += 1
                print(f"ZH item {_i} {_f}：已改為書面繁中（"
                      + "、".join(f"{a}→{b}" for a, b in _app) + f"）\n     {_new}",
                      file=sys.stderr)
    # highlights are a list of strings
    for _f in ("highlights",):
        _v = _it.get(_f)
        if isinstance(_v, list):
            _fixed = []
            for _x in _v:
                _new, _app = _to_written_zh(_x) if isinstance(_x, str) else (_x, [])
                if _app:
                    _zh_fixed_n += 1
                _fixed.append(_new)
            _it[_f] = _fixed
    # ambiguous words: flag only
    for _f in _ZH_FIELDS:
        _v = _it.get(_f) or ""
        for _w, (_ok, _note) in _ZH_FLAG.items():
            if isinstance(_v, str) and _w in _v:
                # strip the standard compounds; only a bare survivor is suspect
                if _w in re.sub(_ok, "", _v):
                    print(f"ZH? item {_i} {_f} 含「{_w}」：{_note}\n     {_v}", file=sys.stderr)
                    _warn += 1
                    break

# --- Highlights must be whole sentences, not clause fragments -----------------
# A highlight written by splitting the summary on commas gives the reader half a
# thought per bullet ("百事可樂不經比稿直接委任 Publicis，終止宏盟" — terminated
# mid-clause), which is worse than showing the summary paragraph whole. So each
# bullet has to stand alone: end in real punctuation and carry a subject.
# When a card's bullets fail that test we fall back to the full summary rather
# than publish fragments — the reader always gets a complete sentence.
_END_OK = ("。", "！", "？", "%", "）", ")", ".", "!", "?", "」", "”")

def _is_fragment(t):
    """True when a bullet reads as a cut-off clause rather than a sentence."""
    s = str(t or "").strip()
    if not s:
        return True
    if s.endswith(("…", "...", "，", ",", "、", "；", ";", "：", ":")):
        return True
    return not s.endswith(_END_OK)

_frag_cards = 0
for _i, _it in enumerate(data["items"], 1):
    for _f, _lab in (("highlights", "中文"), ("highlights_en", "英文")):
        _v = _it.get(_f)
        if not isinstance(_v, list) or not _v:
            continue
        _bad = [x for x in _v if _is_fragment(x)]
        if _bad:
            _frag_cards += 1
            print(f"FRAG item {_i} {_f}（{_lab}）有 {len(_bad)}/{len(_v)} 點是半句，"
                  f"已改用完整 summary 顯示。重點要能獨立成句，不要把 summary 按逗號切開：\n"
                  f"     ✗ {str(_bad[0])[:60]}", file=sys.stderr)
            _warn += 1
            _it[_f] = []          # force the whole-summary fallback in the card
if _frag_cards:
    print(f"FRAG 共 {_frag_cards} 個欄位的重點是半句 → 已 fallback 顯示完整 summary。"
          f"根源要喺 routine 寫稿階段每點獨立成句。", file=sys.stderr)

if _zh_fixed_n:
    print(f"ZH 共修正 {_zh_fixed_n} 個欄位為書面繁體中文（台港通用）。"
          f"根源要喺 routine 寫稿階段就用書面語，唔好靠呢層兜底。", file=sys.stderr)

# --- Write the cleaned data back so the EDM and archive match the site --------
# build_email.py and build_archive.py read data.json directly. Without this the
# site would show 18 deduped, written-Chinese stories while the EDM still sent 22
# in spoken Cantonese. The untouched original is kept as data.raw.json.
if _drop or _zh_fixed_n or _frag_cards:
    (ROOT / "data.raw.json").write_text(_raw, encoding="utf-8")
    _data_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"NOTE 已回寫 data.json（剔走 {len(_drop)} 條重複、修正 {_zh_fixed_n} 個中文欄位、"
          f"{_frag_cards} 個半句重點改用完整 summary），"
          f"原檔備份為 data.raw.json。EDM 同存檔會用同一份數據 —— "
          f"所以要先跑 build.py，再跑 build_email.py 同 build_archive.py。", file=sys.stderr)

# --- Validate items: warn (don't crash) --------------------------------------
def _cjk(s):
    return len(re.findall(r"[一-鿿]", s or ""))

_sections = set(data["sections"])
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
        print(f"WARN item {_i} 「{_t}」: section '{_sec}' 唔喺版塊之列 → 呢張卡會被丟走！", file=sys.stderr); _warn += 1
    if _it.get("action") and _it["action"] not in ACT:
        print(f"WARN item {_i} 「{_t}」: action '{_it['action']}' 唔啱（要 可即用/要留意/影響生意）→ 用預設色", file=sys.stderr); _warn += 1
    if _it.get("region") and _it["region"] not in REG:
        print(f"WARN item {_i} 「{_t}」: region '{_it['region']}' 唔啱（要 國際/中國/香港）→ 中性色", file=sys.stderr); _warn += 1
    if _cjk(_it.get("summary")) > 60:
        print(f"WARN item {_i} 「{_t}」: summary {_cjk(_it['summary'])} 中文字 >60，建議收短", file=sys.stderr); _warn += 1
    if _cjk(_it.get("why")) > 45:
        print(f"WARN item {_i} 「{_t}」: why {_cjk(_it['why'])} 中文字 >45，建議收短", file=sys.stderr); _warn += 1
    _hl = _it.get("highlights") or []
    if _hl and not isinstance(_hl, list):
        print(f"WARN item {_i} 「{_t}」: highlights 要係 list（每點一句）→ 今次當冇", file=sys.stderr); _warn += 1
    elif isinstance(_hl, list) and len(_hl) > 4:
        print(f"WARN item {_i} 「{_t}」: highlights 有 {len(_hl)} 點，建議 2–3 點", file=sys.stderr); _warn += 1
    _u = _it.get("url", "")
    if _u and not _u.startswith(("http://", "https://")):
        print(f"WARN item {_i} 「{_t}」: url 唔係 http/https：{_u}", file=sys.stderr); _warn += 1

if len(_sections_en) and len(_sections_en) != len(data["sections"]):
    print(f"WARN sections_en 有 {len(_sections_en)} 個，同 sections 嘅 {len(data['sections'])} 個唔一致 → 部分版塊 EN 會 fallback 中文", file=sys.stderr); _warn += 1

groups = {s: [] for s in data["sections"]}
for it in data["items"]:
    groups.setdefault(it.get("section", ""), []).append(it)

# An empty section is fine — better an honest gap than a padded duplicate.
for _s in data["sections"]:
    if not groups.get(_s):
        print(f"NOTE 版塊「{_s}」今日冇內容 → 會照顯示「今日暫無」，唔使硬塞", file=sys.stderr)

# --- Render cards -------------------------------------------------------------
def _list_items(zh_list, en_list):
    """Bilingual <li> rows; pads the shorter language with its counterpart."""
    zh_list = [x for x in (zh_list or []) if str(x).strip()]
    en_list = [x for x in (en_list or []) if str(x).strip()]
    out = []
    for _i in range(max(len(zh_list), len(en_list))):
        _z = zh_list[_i] if _i < len(zh_list) else (en_list[_i] if _i < len(en_list) else "")
        _e = en_list[_i] if _i < len(en_list) else _z
        out.append(f"<li>{bi(_z, _e)}</li>")
    return "".join(out)

def _split_paras(t):
    """Free text -> paragraphs. Accepts a list, or a string with blank-line or
    single-newline breaks (editors write it both ways)."""
    if isinstance(t, list):
        return [str(x).strip() for x in t if str(x).strip()]
    t = str(t or "").strip()
    if not t:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n|\n", t) if p.strip()]

def _para_rows(zh, en):
    """Bilingual <p> rows; pads the shorter language with its counterpart."""
    z, e = _split_paras(zh), _split_paras(en)
    rows = []
    for _i in range(max(len(z), len(e))):
        _z = z[_i] if _i < len(z) else (e[_i] if _i < len(e) else "")
        _e = e[_i] if _i < len(e) else _z
        rows.append(f"<p>{bi(_z, _e)}</p>")
    return "".join(rows)

cards, n = {}, 0
tldr_rows = []   # one-liners for the 三分鐘看完 digest at the top of the page
_paywall_n = 0
# A write-up shorter than this adds nothing the card did not already say — the
# card itself runs ~300 字 (highlights + summary + insight), so the expander has
# to clear that bar to be worth a click.
_DETAIL_MIN_CHARS = 420
_detail_gap = []    # (no, source, paywalled) — no detail at all
_detail_thin = []   # (no, source, chars)     — detail present but too short
_slug_seen = {}     # slug -> card no, to catch a same-URL collision loudly
_slug_of = {}       # card no -> slug, used by 三分鐘看完 and the s{n} alias map
for s in data["sections"]:
    out = []
    for it in groups[s]:
        n += 1
        sid = story_slug(it)
        # Two cards from the same URL would share a slug and break in-page anchors.
        # The dedupe upstream should make this impossible; if it ever happens, say
        # so and disambiguate rather than emitting a duplicate id silently.
        if sid in _slug_seen:
            print(f"WARN #{n:02d} slug 撞 #{_slug_seen[sid]:02d}（{sid}）→ 加尾號區分，"
                  "查下係唔係同一條 URL 出咗兩張卡", file=sys.stderr)
            _warn += 1
            sid = f"{sid}-{n}"
        _slug_seen[sid] = n
        _slug_of[n] = sid
        url = html.escape(str(it.get("url", "")))
        act = it.get("action", "要留意")
        act_cls = ACT.get(act, "watch")
        reg = it.get("region", "")
        reg_cls = REG.get(reg, "r-other")
        src = html.escape(str(it.get("source", "")))
        tm = str(it.get("time", ""))
        sec_cls = SEC_CLS[s]

        # 昨日續篇 — when this story already ran on an earlier day, this line says what
        # MOVED since then. It sits above 重點摘要 on purpose: a reader who saw the
        # earlier card needs the delta first, and a reader who did not still gets the
        # thread in one sentence. This is the alternative to deleting the story as a
        # duplicate — deleting it would hide the outcome of a developing line.
        fu = ""
        if str(it.get("followup", "") or it.get("followup_en", "")).strip():
            fu = (f'<div class="followup"><b class="k">{bi("昨日續篇", "Since Yesterday")}</b>'
                  f'<p>{bi(it.get("followup",""), it.get("followup_en"))}</p></div>')

        # 重點摘要 — bullets when provided, otherwise the one-paragraph summary
        hl_zh, hl_en = it.get("highlights") or [], it.get("highlights_en") or []
        if isinstance(hl_zh, list) and (hl_zh or hl_en):
            body = (f'<div class="block"><b class="k">{bi("重點摘要", "Key Highlights")}</b>'
                    f'<ul class="kh">{_list_items(hl_zh, hl_en)}</ul></div>')
        else:
            body = (f'<div class="block"><b class="k">{bi("重點摘要", "Key Highlights")}</b>'
                    f'<p>{bi(it.get("summary",""), it.get("summary_en"))}</p></div>')

        # 行業洞察 — the marketer's angle
        take = (f'<div class="take"><b class="k">{bi("行業洞察", "Industry Insight")}</b>'
                f'<p>{bi(it.get("why",""), it.get("why_en"))}</p></div>')

        # 趨勢觀察 — follow-up on an already-published story (replaces duplicate cards)
        pat = ""
        if str(it.get("pattern", "") or it.get("pattern_en", "")).strip():
            pat = (f'<div class="predict"><b class="k">{bi("趨勢觀察", "Pattern Watch")}</b>'
                   f'<p>{bi(it.get("pattern",""), it.get("pattern_en"))}</p></div>')

        # 詳細內容 — our own longer write-up, collapsed. This is the paywall
        # answer: when the source is metered the reader still gets the substance
        # here.
        #
        # There is deliberately NO fallback. The first version assembled the
        # expander out of the highlights + summary + insight already printed on
        # the card, which meant opening it showed the reader nothing new — the
        # button promised 詳細 and delivered a rerun. An absent expander is
        # honest; a padded one costs a click and trust. So: no `detail` in the
        # data, no button, and a loud stderr warning when a paywalled story is
        # the one missing it (that is the case where the reader has no other way
        # in). _detail_gap collects those for the build report.
        paywalled = _is_paywalled(it)
        if paywalled:
            _paywall_n += 1
        det_rows = _para_rows(it.get("detail"), it.get("detail_en"))
        # Count 漢字, not len(): the text carries Latin brand names and figures, so
        # len() reads ~50% high and the "約 N 字" on the button would overpromise.
        _det_n = len(re.findall(r"[一-鿿]", " ".join(_split_paras(it.get("detail")))))
        if det_rows and _det_n < _DETAIL_MIN_CHARS:
            _detail_thin.append((n, it.get("source", ""), _det_n))
        if not det_rows:
            _detail_gap.append((n, it.get("source", ""), paywalled))
        detail = ""
        if det_rows:
            _label = (bi(f"看詳細內容（本站整理，約 {_det_n} 字）", "Read our full write-up")
                      if paywalled else bi(f"看詳細內容（約 {_det_n} 字）", "Read our full write-up"))
            _note = (f'<p class="why-src">{bi("原文需訂閱，以上為本站整理；來源：" + str(it.get("source","")), "Source is subscriber-only; the above is our own write-up. Source: " + str(it.get("source","")))}</p>'
                     if paywalled else
                     f'<p class="why-src">{bi("整理自：" + str(it.get("source","")), "Compiled from: " + str(it.get("source","")))}</p>')
            detail = (f'<details class="detail"><summary>{_label}</summary>'
                      f'<div class="detail-body">{det_rows}{_note}</div></details>')

        pw_badge = ('<span class="paywall" title="原文需要訂閱才可閱讀 / Source requires a subscription">'
                    f'🔒{bi("需訂閱", "Paywalled")}</span>') if paywalled else ""

        # 三分鐘看完 only lists what a reader must not miss — 可即用 and 影響生意.
        if act_cls in ("act", "impact"):
            tldr_rows.append(
                f'<li><a href="#{sid}"><span class="t-tag {act_cls}">{bi(act, ACT_EN.get(act, act))}</span>'
                f'{bi(it.get("title",""), it.get("title_en"))}</a></li>')

        # id = the stable slug. The old positional s{n} survives as an empty anchor
        # so links already shared against THIS issue keep landing in the right
        # place; from tomorrow the slug is the one that travels.
        #
        # The anchor sits INSIDE the <article>, not before it. A sibling span is a
        # direct child of .stories, and a grid item's display is blockified — so
        # the first version turned every alias into a full grid cell and the
        # measured layout went from 2 cards per row to 1 (cols '552px 552px',
        # 首行 1 張, alias area 2,030,127px² at 1400px). That is exactly the
        # 「格仔唔整齊」 Carrie asked me to fix, so the anchor goes inside where it
        # is ordinary inline content and holds no grid track.
        out.append(f'''<article class="story {sec_cls}" id="{sid}" data-no="{n}"><span class="idalias" id="s{n}" aria-hidden="true"></span>
<div class="story-meta"><span class="src">{src}</span><span class="date">{bi(tm, _time_en(tm))}</span>{pw_badge}<span class="no">{n:02d}</span></div>
<h3><a href="{url}" target="_blank" rel="noopener noreferrer">{bi(it.get("title",""), it.get("title_en"))}</a></h3>
{fu}{body}
{take}
{pat}{detail}<div class="story-foot"><span class="foot-tags"><span class="signal {act_cls}">{bi(act, ACT_EN.get(act, act))}</span><span class="chip region {reg_cls}">{bi(reg, REG_EN.get(reg, reg))}</span></span><a class="readsrc" href="{url}" target="_blank" rel="noopener noreferrer">{bi("閱讀原文 →", "Read original →")}</a></div>
</article>''')
    cards[s] = "\n".join(out)

total = n
READ_MIN = data.get("read_minutes") or max(3, round(total * 0.5))

if _paywall_n:
    print(f"NOTE {_paywall_n}/{total} 則來源需訂閱 → 已加「需訂閱」標記", file=sys.stderr)

# The expander is the only route into a paywalled story, so a missing `detail`
# there is a real gap, not a style preference. Loud for those, quiet for the rest.
_gap_pw = [g for g in _detail_gap if g[2]]
if _gap_pw:
    print(f"WARN {len(_gap_pw)}/{_paywall_n} 則需訂閱來源冇 detail，讀者完全睇唔到內容："
          + ", ".join(f"#{g[0]:02d} {g[1]}" for g in _gap_pw), file=sys.stderr)
if _detail_gap:
    print(f"NOTE {len(_detail_gap)}/{total} 則冇 detail → 唔會出「看詳細內容」按鈕（寧可冇，唔好重複卡片內容）",
          file=sys.stderr)
if _detail_thin:
    print(f"WARN {len(_detail_thin)} 則 detail 短過 {_DETAIL_MIN_CHARS} 字，展開後同卡片重複度高："
          + ", ".join(f"#{t[0]:02d} {t[1]}({t[2]}字)" for t in _detail_thin), file=sys.stderr)
if total and not _detail_gap and not _detail_thin:
    print(f"OK   {total}/{total} 則都有足夠長度嘅 detail", file=sys.stderr)

# ---- 三分鐘看完 -------------------------------------------------------------
# Cap at 6: past that it stops being a three-minute read and becomes a second
# table of contents. The cap is announced in the header line, not hidden.
_TLDR_MAX = 6
tldr_html = ""
if tldr_rows:
    _shown = tldr_rows[:_TLDR_MAX]
    _sub = (bi(f"{len(_shown)} 個今天真正要知的重點", f"the {len(_shown)} things that actually matter today")
            if len(tldr_rows) <= _TLDR_MAX else
            bi(f"今天 {len(tldr_rows)} 則屬可即用或影響生意，先看這 {len(_shown)} 個",
               f"{len(tldr_rows)} stories are actionable or business-critical — here are the top {len(_shown)}"))
    tldr_html = f'''<section class="tldr" aria-labelledby="tldr-h">
  <div class="tldr-head"><b id="tldr-h">{bi("三分鐘看完", "The 3-minute version")}</b><span>{_sub}</span></div>
  <ol>{"".join(_shown)}</ol>
</section>'''

stats = "".join(
    f'<a class="stat" href="#{SEC_ID[s]}"><b>{len(groups[s])}</b><span>{bi(s, SEC_EN.get(s, s))}</span></a>'
    for s in data["sections"])
nav = "".join(
    f'<a href="#{SEC_ID[s]}">{bi(s, SEC_EN.get(s, s))}<i>{len(groups[s])}</i></a>'
    for s in data["sections"])

# Reader-facing: just state the fact. The editorial reasoning behind leaving a
# section blank (better a gap than a padded duplicate) is Carrie's own rationale
# and belongs in the stderr NOTE for the editor, not on the page.
_empty_note = (f'<p class="empty">{bi("今天這個分類沒有新消息。", "No updates in this section today.")}</p>')
sections_html = "\n".join(
    f'''<section id="{SEC_ID[s]}">
<div class="cat-head {SEC_CLS[s]}"><span class="cat-emoji">{SEC_EMOJI[s]}</span><div class="cat-txt"><h2>{bi(s, SEC_EN.get(s, s))}</h2><p class="cat-desc">{bi(SEC_DESC[s], SEC_DESC_EN[s])}</p></div><em>{bi(str(len(groups[s]))+" 則", str(len(groups[s]))+" items")}</em></div>
<div class="stories">{cards[s] or _empty_note}</div>
</section>'''
    for s in data["sections"])

date_disp, date_disp_en = _canon_dates(ISO, data.get("date_display", ""), data.get("date_display_en", ""))
sources_note = data.get("sources_note", "")
sources_note_en = data.get("sources_note_en", sources_note)

HEADLINE    = data.get("headline", "少一點 AI 噪音。\n多一點行銷訊號。")
HEADLINE_EN = data.get("headline_en", "Less AI noise.\nMore marketing signal.")
STANDFIRST  = data.get("standfirst",
    "每天一份。每則只講三件事：發生什麼、對行銷人有何影響、今天是否要行動。")
STANDFIRST_EN = data.get("standfirst_en",
    "Every morning. Each story answers three things: what happened, why it matters to marketers, and whether to act today.")
BYLINE      = data.get("byline", "Carrie Hui")
BYLINE_ROLE    = data.get("byline_role", "AI 行銷策略 · 旅遊零售與大中華區")
BYLINE_ROLE_EN = data.get("byline_role_en", "AI Marketing Strategist · Travel Retail & Greater China")

def _h1(text_zh, text_en):
    """Honour a literal \\n in the headline as a <br>."""
    def _fmt(t):
        return "<br>".join(html.escape(p) for p in str(t).split("\n"))
    return (f'<span class="l-zh">{_fmt(text_zh)}</span>'
            f'<span class="l-en">{_fmt(text_en)}</span>')

thesis_html = ""
if str(data.get("thesis", "") or data.get("thesis_en", "")).strip():
    _note = ""
    if str(data.get("thesis_note", "") or data.get("thesis_note_en", "")).strip():
        _note = f'<p>{bi(data.get("thesis_note",""), data.get("thesis_note_en"))}</p>'
    thesis_html = f'''<section class="section">
<div class="thesis">
  <div class="eyebrow">{bi("今日核心訊號", "Today's signal")}</div>
  <blockquote>{bi(data.get("thesis",""), data.get("thesis_en"))}</blockquote>
  {_note}
</div>
</section>'''

_weekly_link = ""
if WEEKLY_URL:
    _weekly_link = (f'<a class="byline-link" href="{html.escape(WEEKLY_URL)}" target="_blank" rel="noopener noreferrer">'
                    f'{bi("每週深度版 →", "Weekly brief →")}</a>')

# The LinkedIn link carries an inline SVG mark, not the text "LinkedIn": the byline
# is already three text fragments long and a fourth word would read as more credit
# copy. `aria-label` is on the <a>, so a screen reader still announces the
# destination — the glyph is `aria-hidden` and would otherwise announce nothing.
_li_link = ""
if LINKEDIN_URL:
    _li_link = (
        f'<a class="byline-link li" href="{html.escape(LINKEDIN_URL)}" target="_blank"'
        f' rel="noopener noreferrer me"'
        f' aria-label="{html.escape(bi_attr(BYLINE + " 的 LinkedIn（新視窗開啟）", BYLINE + " on LinkedIn (opens in a new tab)"))}">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="currentColor">'
        '<path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.55V9h3.57v11.45z"/>'
        '</svg>'
        f'<span>{bi("LinkedIn", "LinkedIn")}</span></a>')

# --- Share preview -----------------------------------------------------------
# The brief travels by being forwarded (Lark, email, WhatsApp), so the link
# preview IS the front page for most readers. Without these tags a forward shows
# a bare url. Description = the leading headlines, so the card says what's inside.
_lead = [i.get("title_en") or i.get("title", "") for i in data["items"][:3]]
_lead_zh = [i.get("title", "") for i in data["items"][:3]]
_desc_en = f"{total} stories · {date_disp_en} — " + "；".join(x for x in _lead if x)
_desc_zh = f"今天 {total} 則 · {date_disp} — " + "；".join(x for x in _lead_zh if x)
_desc_en = (_desc_en[:197] + "…") if len(_desc_en) > 198 else _desc_en
_desc_zh = (_desc_zh[:197] + "…") if len(_desc_zh) > 198 else _desc_zh
_og_image = data.get("og_image", "")
_og = f'''<meta name="description" content="{html.escape(_desc_en)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(SITE_TITLE_EN)}">
<meta property="og:title" content="{html.escape(SITE_TITLE_EN)} · {html.escape(date_disp_en)}">
<meta property="og:description" content="{html.escape(_desc_en)}">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="zh_HK">
<meta property="og:locale:alternate" content="zh_TW">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(SITE_TITLE_EN)} · {html.escape(date_disp_en)}">
<meta name="twitter:description" content="{html.escape(_desc_en)}">'''
if SITE_URL:
    _og += f'\n<meta property="og:url" content="{html.escape(SITE_URL)}">\n<link rel="canonical" href="{html.escape(SITE_URL)}">'

# Icon/manifest hrefs must carry the project path prefix. This is a GitHub Pages
# PROJECT site (/ai-marketing-daily/), so a root-relative "/icon-192.png" would
# resolve to carriehw.github.io/icon-192.png and 404. A relative "icon-192.png"
# breaks the other way — archive/2026-09-29.html would look inside archive/.
# Deriving the prefix from site_url is correct for both.
_base = "/"
if SITE_URL:
    try:
        from urllib.parse import urlsplit
        _p = urlsplit(SITE_URL).path or "/"
        _base = _p if _p.endswith("/") else _p.rsplit("/", 1)[0] + "/"
    except Exception:
        _base = "/"

# Webfonts. Same path trap as the icons above, so reuse _base: a relative
# "fonts/…" would make archive/2026-09-29.html look in archive/fonts/, and a
# root-relative "/fonts/…" 404s on a project site.
#
# The block is generated by build_fonts.py (single source of truth for the family
# names, weights and unicode-range) rather than pasted here, so the CSS can never
# drift from the woff2 files that were actually subset. If the fonts have not been
# built, emit NOTHING and leave the system stack — a half-wired @font-face
# pointing at missing files is worse than no webfont, because the page would then
# claim a font it cannot load and the failure is silent.
#
# Every path that ends without a @font-face block MUST say so on stderr. The first
# version only warned when fonts/ existed but was incomplete, and said nothing at
# all when the directory was absent — which is exactly the case the scheduled run
# hits (fresh session, fonts/ never fetched). Measured 2026-10-02: moving fonts/
# away and rebuilding printed no warning and produced a page with 0 woff2
# references. Silence on the most likely failure is the bug class this project
# keeps paying for, so the quiet branch is now the loud one.
_fontcss = ""
_fontdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
try:
    import importlib.util as _ilu
    _fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_fonts.py")
    if not os.path.isdir(_fontdir):
        print("  字體未齊，略過 @font-face（冇 fonts/ 資料夾 —— 排程要先 GET repo 嘅 "
              "fonts/*.woff2 落本機）", file=sys.stderr)
    elif not os.path.exists(_fp):
        print("  字體未齊，略過 @font-face（冇 build_fonts.py）", file=sys.stderr)
    else:
        _spec = _ilu.spec_from_file_location("_bf", _fp)
        _bf = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_bf)
        _missing = [f for f, *_ in _bf.FACES
                    if not os.path.exists(os.path.join(
                        _fontdir, f.rsplit(".", 1)[0] + ".woff2"))]
        if _missing:
            print("  字體未齊，略過 @font-face（缺 %s）" % ", ".join(_missing[:3]),
                  file=sys.stderr)
        else:
            _fontcss = _bf.css(_base)
except Exception as _e:  # noqa: BLE001 — never let font wiring break the build
    print("  @font-face 生成失敗，維持系統字體：%s" % _e, file=sys.stderr)

# preload only the two faces above the fold (body regular + the mono used by the
# story numbers). Preloading all five would compete with the hero text for the
# first connections and make the swap later, not earlier.
_fontpre = ""
if _fontcss:
    _fontpre = (f'\n<link rel="preload" href="{_base}fonts/Inter-Regular.woff2" as="font" type="font/woff2" crossorigin>'
                f'\n<link rel="preload" href="{_base}fonts/IBMPlexMono-Regular.woff2" as="font" type="font/woff2" crossorigin>')

# Share card. Absent an explicit og_image in data.json, use this issue's own card
# built by build_ogimage.py at og/<ISO>.jpg.
#
# Three things here are load-bearing, all of them measured rather than assumed:
#  1. It must be an ABSOLUTE url. Slack, WhatsApp, LinkedIn and Gmail fetch the
#     image from their own servers with no page context, so a relative path is
#     never resolved and the card renders blank — which is what the site did for
#     its whole life: `twitter:card=summary_large_image` was declared while
#     `og:image` appeared 0 times, i.e. a slot sized for a large image with no
#     image in it.
#  2. It must be DATED, not a rolling og.jpg. build_archive.py snapshots this page
#     verbatim, so a rolling name would make the 9/20 archive page advertise
#     9/30's headlines.
#  3. og:image:width/height let the platform lay the card out before the image
#     finishes downloading; without them some clients fall back to a small square.
if not _og_image and SITE_URL:
    _og_image = SITE_URL.rstrip("/") + f"/og/{ISO}.jpg"
if _og_image:
    _og += (f'\n<meta property="og:image" content="{html.escape(_og_image)}">'
            f'\n<meta property="og:image:width" content="1200">'
            f'\n<meta property="og:image:height" content="630">'
            f'\n<meta property="og:image:type" content="image/jpeg">'
            f'\n<meta property="og:image:alt" content="{html.escape(SITE_TITLE_EN)} · {html.escape(date_disp_en)} — {total} stories">'
            f'\n<meta name="twitter:image" content="{html.escape(_og_image)}">'
            f'\n<meta name="twitter:image:alt" content="{html.escape(SITE_TITLE_EN)} · {html.escape(date_disp_en)}">')

# Structured data: lets the archive surface as a dated collection in search.
_ld = json.dumps({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": f"{SITE_TITLE_EN} · {date_disp_en}",
    "inLanguage": ["en", "zh-Hant"],
    "datePublished": ISO,
    "description": _desc_en,
    **({"url": SITE_URL} if SITE_URL else {}),
    # sameAs is what actually ties this page to her profile for search engines and
    # link previews; the visible byline link alone is not read as an identity claim.
    "author": {"@type": "Person", "name": BYLINE,
               **({"sameAs": LINKEDIN_URL} if LINKEDIN_URL else {})},
    "hasPart": [{
        "@type": "NewsArticle",
        "headline": (i.get("title_en") or i.get("title", ""))[:110],
        "url": i.get("url", ""),
        **({"publisher": {"@type": "Organization", "name": i["source"]}} if i.get("source") else {}),
    } for i in data["items"][:25]],
}, ensure_ascii=False, separators=(",", ":"))

page = f'''<!doctype html>
<html lang="en" data-lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(SITE_TITLE_EN)} · {html.escape(ISO)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
{_og}
<!-- Status-bar tint, matched to the icon's base navy so the chrome above the page is the
     same colour as the tile the reader tapped. The splash stays paper (manifest
     background_color) so launching does not flash a dark screen. -->
<meta name="theme-color" content="#141852">
<link rel="icon" href="{_base}favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="192x192" href="{_base}icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="{_base}icon-180.png">
<link rel="manifest" href="{_base}manifest.webmanifest">{_fontpre}
<!-- Standalone iOS: without this the status bar sits on paper-coloured page background
     and the time/battery go invisible. `black-translucent` would push content under the
     notch, so `default` is correct for a page with its own sticky topbar. -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="AI・行銷情報">
<meta name="application-name" content="AI・行銷情報">
<script type="application/ld+json">{_ld}</script>
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
/* ---- webfonts (generated by build_fonts.py; Latin + numerals only) ------------
   Before this block the page named `Inter` and declared tabular numerals while
   loading 0 font files, so on Windows/Android it silently fell through to a
   system sans and the 等寬數字 claim was simply not true. CJK deliberately stays
   on the system face — a subset Hant webfont is 4–9 MB, a worse trade on a
   27-story mobile page than the substitution it would fix. ---------------------*/
{_fontcss}
/* ---- palette v1.0 — every value derived from icon-512.png ---------------------
   See brand/AI情報站-品牌規範-v1.0.md and brand/palette_check.py.
   The icon is a FOUR-corner gradient spanning 100° of hue:
     violet #6249D7 251° · blue #39689F 212° · plum #7D266B 312° · navy #11154A 236°
   The old --c3 green (158°), --c4 red (4°) and --c5 orange (33°) sat completely
   outside that arc, which is the measurable reason the page read as unrelated to
   the mark. The five category hues below are spread ACROSS the arc instead, so
   hue order == section order and colour carries information.
   Every pairing below is checked by palette_check.py at >=4.8:1, not 4.5 — a
   published page should not sit one rounding error from failing AA. --------------*/
:root{{
  --paper:#f7f5ef;--card:#fff;--ink:#101114;--muted:#656a73;--body:#3c3f45;
  --accent:#5a42f4;--accent-d:#4632d4;--accent-soft:#ebe8ff;
  --line:#dedbd2;--shadow:0 16px 45px rgba(16,17,20,.08);
  /* icon anchors, used by the dark identity zone */
  --i-violet:#553fba;--i-blue:#2f5582;--i-navy:#11154a;--i-plum:#7d266b;
  --lime:#d3fe66;
  /* on-dark text layers (checked against the LIGHTEST stop, #553fba) */
  --on-dark:#f7f5ef;--on-dark-2:#d6d4e8;--on-dark-3:#cfcde4;--on-dark-chip:#edebf6;
  /* category colours: solid = cat-head bg + card border; s = pill bg; t = pill text */
  --c1:#39689f;--c1s:#d9e6f6;--c1t:#2c619e;
  --c2:#3f5bc8;--c2s:#d9dff6;--c2t:#2f4ec7;
  --c3:#6249d7;--c3s:#ded9f6;--c3t:#5438d6;
  --c4:#9a3a9e;--c4s:#f5d9f6;--c4t:#972d9c;
  --c5:#7d266b;--c5s:#f6d9f0;--c5t:#7d266b;
  /* Signal badges stay green / amber / violet. They are OUTSIDE the icon's hue arc
     on purpose, same exemption as Lime: 可即用 / 要留意 / 影響生意 is a traffic-light
     encoding the reader already knows, and recolouring it into the arc would make
     three different meanings look like three shades of the same thing. V nudged
     down from #1e7c5a / #a45a00 — both measured 4.47 and 4.73 on their own tints,
     under the 4.8 target. Hue unchanged at 158° and 33°. */
  --green:#1d7656;--amber:#a25900;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
/* The old radial-gradient sat at 85% 0% — the top-right of the page, which the
   dark topbar and hero now cover completely. It was painting a violet glow
   underneath an opaque gradient: invisible, and still a paint cost on every
   scroll. Removed rather than relocated; the reading zone is meant to be flat
   paper (rule R4), and a second gradient down there would compete with the one
   piece of gradient that carries meaning. */
/* InterLat first and CJK after it, in that order on purpose: the Latin subset has
   no CJK glyphs, so Chinese falls through to the next family per-character — the
   normal CSS cascade, not a bug. Reversing them would give Latin the CJK font's
   proportional Latin, which is the mismatched look this change removes. */
body{{margin:0;background:var(--paper);color:var(--ink);font-family:InterLat,Inter,"Noto Sans TC","Noto Sans HK",ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","PingFang HK","Microsoft JhengHei",sans-serif;line-height:1.65}}
a{{color:inherit}}
/* --- language toggle: show the active language, hide the other ---
   The bare `.l-en{{display:none}}` is specificity 0,1,0, so ANY later rule like
   `.stat span{{display:block}}` (0,1,1) silently beat it and the card showed both
   languages stacked. The `html:not(...)` form is 0,2,0 and outranks any such
   single-class descendant rule, which keeps the toggle from breaking again when
   a component styles its inner spans. */
.l-en{{display:none}}
html:not([data-lang="en"]) .l-en{{display:none}}
html[data-lang="en"] .l-en{{display:inline}}
html[data-lang="en"] .l-zh{{display:none}}
.wrap{{width:min(1120px,calc(100% - 32px));margin:0 auto}}

/* ---- masthead nav ---- */
/* Dark identity zone. The top 4px line is the icon's Lime — the one place a 4px
   strip of it is unambiguously a brand mark rather than decoration. The bar itself
   is the icon's navy anchor, so the masthead and the app icon on the reader's home
   screen are the same colour. Kept slightly translucent so the blur still reads
   as a layer when content scrolls under it. */
.topbar{{border-top:4px solid rgba(211,254,102,.26);background:rgba(17,21,74,.96);backdrop-filter:blur(8px);position:sticky;top:0;z-index:20;border-bottom:1px solid rgba(247,245,239,.14)}}
.mast{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 0;flex-wrap:wrap}}
.brand{{font-weight:800;letter-spacing:-.02em;font-size:19px;line-height:1.25;color:var(--on-dark)}}
.brand span{{color:var(--lime)}}
.brand small{{display:block;font-weight:500;font-size:11.5px;color:var(--on-dark-3);letter-spacing:.16em;text-transform:uppercase}}
/* min-width:0 on BOTH, and it is load-bearing. .navlinks was written with
   `overflow-x:auto;max-width:100%` intending to scroll, and it never did: a flex
   item defaults to min-width:auto, so .mast-r refused to shrink below its
   content and .navlinks sized to a flat 1006px at EVERY viewport. Measured on
   the live site: at 900/820/768px the document scrollWidth was 1022 against a
   768 viewport — the whole page scrolled sideways on a tablet, and had been
   doing so before this change. Adding the Share pill took .navlinks to 1074px,
   which also wrapped the EN/中文 toggle onto a second row and grew the sticky
   topbar from 121px to 164px on every desktop width — 43px of a daily-read
   page's first screen. min-width:0 lets the flex item actually shrink, at which
   point the overflow-x:auto that was already there starts working as intended.
   Verified by measurement at 15 widths from 1600 to 390: no horizontal document
   overflow at any of them, topbar back to one row. */
/* .mast keeps its original flex-wrap:wrap — on a phone the brand and the controls
   genuinely need two rows, and forcing nowrap there pushed the document to 585px
   against a 500px viewport (measured at 500/430/390/360). What was wrong was never
   the wrapping; it was that .mast-r could not shrink, so wrapping was the only
   relief available and it took it on desktop too. min-width:0 fixes the cause, and
   the wrap then only happens where it is actually wanted. */
.mast-r{{display:flex;align-items:center;gap:10px;flex-wrap:nowrap;min-width:0}}
.navlinks{{display:flex;gap:6px;align-items:center;overflow-x:auto;min-width:0;flex:1 1 auto;
  scrollbar-width:none;-ms-overflow-style:none}}
.navlinks::-webkit-scrollbar{{display:none}}
.brand{{flex:0 0 auto}}
/* Every rule below covers BOTH the pills inside the scrolling strip and the two
   lifted out of it (`.mast-r>a.pill`). The base look was scoped to `.navlinks a`,
   so moving the Archive pill out of that container silently dropped its border,
   background, padding and radius — it rendered as bare underlined text on the dark
   bar. Extending the selector rather than copying the declarations keeps one source
   of truth; a copy would drift the moment either is touched. */
.navlinks a,.mast-r>a.pill{{white-space:nowrap;font-size:13px;color:var(--on-dark-chip);text-decoration:none;border:1px solid rgba(247,245,239,.26);background:rgba(247,245,239,.07);padding:6px 12px;border-radius:99px}}
.navlinks a i{{font-style:normal;color:var(--lime);margin-left:5px;font-family:PlexMonoLat,ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}}
.navlinks a:hover,.mast-r>a.pill:hover{{border-color:var(--lime);color:var(--on-dark)}}
.navlinks a.pill,.mast-r>a.pill{{background:var(--on-dark);color:var(--i-navy);border-color:var(--on-dark);font-weight:700}}
.navlinks a.pill:hover,.mast-r>a.pill:hover{{background:var(--lime);border-color:var(--lime);color:var(--i-navy)}}
.langtog{{display:inline-flex;border:1px solid rgba(247,245,239,.26);border-radius:99px;overflow:hidden;background:rgba(247,245,239,.07);flex:none}}
.langtog button{{font:inherit;font-size:12px;letter-spacing:.04em;padding:6px 14px;border:0;background:transparent;color:var(--on-dark-3);cursor:pointer}}
.langtog button+button{{border-left:1px solid rgba(247,245,239,.26)}}
.langtog button.on{{background:var(--lime);color:var(--i-navy);font-weight:700}}
.langtog button:focus-visible{{outline:2px solid var(--lime);outline-offset:2px}}

/* ---- hero: the dark identity zone -------------------------------------------
   The four stops are the icon's own four corners, in the icon's own spatial order
   (violet top-left → blue top-right → navy bottom-left → plum bottom-right), so
   the first screen and the app icon on the reader's home screen are the same
   object. V is pushed down on violet (84→73) and blue (62→51) because at the
   icon's own brightness the on-dark text layers only reached 3.91–4.18:1. Hue is
   untouched — 251° and 213° after the shift.
   Dark stops HERE only. The reading zone below stays warm paper: this page runs
   ~27 long stories a day, and CJK hairlines halate on a dark ground. --------------*/
.hero{{padding:52px 0 34px;margin-bottom:8px;color:var(--on-dark);
  background:linear-gradient(135deg,var(--i-violet) 0%,var(--i-blue) 30%,var(--i-navy) 64%,var(--i-plum) 100%)}}
.eyebrow{{color:var(--lime);font-weight:800;text-transform:uppercase;font-size:12.5px;letter-spacing:.14em}}
h1{{font-size:clamp(38px,6.4vw,74px);line-height:1.0;letter-spacing:-.05em;margin:14px 0 18px;font-weight:800;color:var(--on-dark)}}
/* text-wrap:balance — ONLY on short display text (this standfirst and the
   .thesis headline), never on body copy. Measured, zh mode, 9 widths:
   without it the standfirst broke 33 + 「動。」 at every width from 1000px up
   (a 2-character orphan line, 6% of the widest line). With it: 18 + 17, 94%.
   Scope matters — the same property on .story .sum shrank paragraphs by up to
   276px to even the lines out, which re-creates the earlier complaint that the
   content sits narrower than its own headline. balance evens SHORT text; on a
   5-line paragraph it just makes the whole block narrow. Body copy is left alone.
   text-wrap:pretty was measured too and moved nothing here (25 orphans before,
   25 after) — chromium's pretty does not rebalance CJK. */
.hero-sub{{font-size:clamp(16.5px,1.9vw,20px);color:var(--on-dark-2);max-width:660px;margin:0 0 20px;
  text-wrap:balance}}
.issue-meta{{display:flex;flex-wrap:wrap;gap:9px;margin-bottom:18px}}
/* Direct child only. `span` as a descendant selector also caught the inner
   <span class="l-zh">/<span class="l-en"> that bi() emits, so each pill grew a
   second pill inside itself — the 「20 則 · 5 個分類」chip rendered as three
   nested capsules. `>` keeps the pill on the outer wrapper alone. */
.issue-meta>span{{border:1px solid rgba(247,245,239,.28);background:rgba(247,245,239,.08);padding:7px 13px;border-radius:999px;font-size:13px;color:var(--on-dark-chip)}}
.issue-meta>span b{{color:var(--on-dark);font-weight:700}}
/* slim byline (personal credit, no full profile card) */
.byline{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0 4px;border-top:1px solid rgba(247,245,239,.2);font-size:13.5px;color:var(--on-dark-3)}}
.byline .who{{color:var(--on-dark);font-weight:750}}
.byline .dot{{color:rgba(247,245,239,.4)}}
.byline-link{{text-decoration:none;color:var(--lime);font-weight:700}}
.byline-link:hover{{text-decoration:underline;text-underline-offset:3px}}
/* LinkedIn: glyph + word on one baseline. inline-flex (not inline) because an
   inline SVG sits on the text baseline and hangs ~2px low next to CJK, which
   reads as a misaligned icon rather than a link. */
.byline-link.li{{display:inline-flex;align-items:center;gap:5px}}
.byline-link.li svg{{width:14px;height:14px;flex:none}}
.byline-link:focus-visible{{outline:2px solid var(--lime);outline-offset:3px;border-radius:3px}}
/* Share now lives in the sticky topbar, so it must match the .navlinks pills it
   sits beside, not the old hero buttons. Sized to the same 13px / 6px 12px as
   .navlinks a so the row does not grow taller, and kept as an OUTLINE pill: the
   Archive pill next to it is the solid one, and two solid pills side by side read
   as two equally-primary actions. .heroacts and .archlink were deleted with the
   hero button row — leaving them would be dead CSS that looks live. */
#share{{white-space:nowrap;font:inherit;font-size:13px;font-weight:600;color:var(--on-dark-chip);border:1px solid rgba(247,245,239,.26);background:rgba(247,245,239,.07);padding:6px 12px;border-radius:99px;cursor:pointer;flex:none}}
#share:hover{{border-color:var(--lime);color:var(--on-dark)}}
#share:focus-visible{{outline:2px solid var(--lime);outline-offset:2px}}
/* .pill.fix is the Archive pill lifted out of the scrolling strip. flex:none so it
   keeps its size when .navlinks shrinks — without it the flex layout takes the
   space back from the pill rather than from the strip it is meant to come from. */
.navlinks a.pill.fix,.mast-r>a.pill{{flex:none}}
#sharebox{{display:none;gap:8px;align-items:center;padding:12px 0 0}}
#sharebox.on{{display:flex}}
#sharebox input{{flex:1;font:inherit;font-size:13px;padding:8px 11px;border:1px solid var(--lime);border-radius:6px;color:var(--ink);background:#fff;min-width:0}}
#sharebox span{{font-size:12px;color:var(--on-dark-3);white-space:nowrap}}

/* ---- add-to-home-screen hint -------------------------------------------------
   Sits below the hero buttons, above the legend. Deliberately quiet: a dashed
   outline rather than a filled card, so it reads as a tip and not as a story.
   Hidden by default (`hidden` attribute) and only revealed by script on a touch
   device that is not already standalone — a desktop reader would be told to do
   something impossible, and a reader who already installed it would be nagged
   about a thing they have done. */
#a2hs{{display:flex;align-items:flex-start;gap:10px;margin:14px 0 0;padding:11px 13px;
  border:1px dashed var(--lime);border-radius:12px;background:rgba(247,245,239,.1);color:var(--on-dark-2)}}
#a2hs[hidden]{{display:none}}
.a2hs-ic{{font-size:16px;line-height:1.35;flex:none}}
.a2hs-txt{{margin:0;font-size:13px;line-height:1.55;color:var(--on-dark-2);flex:1}}
.a2hs-txt b{{color:var(--lime)}}
/* Both platforms' instructions are in the DOM; script adds is-ios / is-and to reveal
   exactly one. Default hidden, so if script never runs nothing contradictory shows. */
.a2hs-ios,.a2hs-and{{display:none}}
#a2hs.is-ios .a2hs-ios,#a2hs.is-and .a2hs-and{{display:inline}}
#a2hs-x{{flex:none;border:0;background:transparent;color:var(--on-dark-3);font-size:14px;
  line-height:1;padding:3px 2px;cursor:pointer;border-radius:6px}}
#a2hs-x:hover{{color:var(--i-navy);background:var(--lime)}}
#a2hs-x:focus-visible{{outline:2px solid var(--lime);outline-offset:2px}}

/* ---- signal legend + section counters ---- */
/* Each badge and its gloss are ONE flex item (.lg), not two. Flat flex items let
   the wrap fall between 要留意 and 平台或趨勢變動 at phone widths, so the badge
   ended one line and its own explanation started the next — the legend read as
   three unrelated fragments. Wrapping each pair makes it unbreakable. */
/* Both blocks sit INSIDE <header class="hero">, so they follow the dark zone.
   The old --muted / --card / --line values were a light-page inheritance: on the
   gradient the legend gloss measured 3.70:1 and the five .stat cards rendered as
   solid white slabs over the identity artwork. Every value below is checked
   against the LIGHTEST hero stop (#553FBA) — the worst case — not against navy,
   which would flatter the numbers by 2x. */
.legend{{display:flex;flex-wrap:wrap;align-items:center;gap:8px 18px;padding:16px 0 0;font-size:12.5px;color:var(--on-dark-2)}}
.legend .lg{{display:inline-flex;align-items:center;gap:7px}}
/* The .stat grid becomes a translucent layer instead of an opaque card: 9% paper
   over the gradient keeps the artwork readable through it while still reading as
   a distinct panel. Label 5.64:1, Lime figure 5.32:1 at the worst stop. */
.stats{{display:grid;grid-template-columns:repeat({max(1, len(data["sections"]))},1fr);gap:1px;background:rgba(247,245,239,.18);border:1px solid rgba(247,245,239,.22);border-radius:14px;overflow:hidden;margin:20px 0 8px}}
.stat{{background:rgba(247,245,239,.09);text-align:center;padding:15px 6px;text-decoration:none;color:var(--on-dark)}}
.stat b{{display:block;font-size:27px;color:var(--lime);font-family:PlexMonoLat,ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums;letter-spacing:-.03em}}
.stat span{{font-size:11.5px;color:var(--on-dark);line-height:1.35;display:block}}
/* Hover stops at 16%: at 20% the label fell to 4.6:1. */
.stat:hover{{background:rgba(247,245,239,.16)}}

/* ---- today's signal ---- */
.section{{padding:34px 0 6px}}
.thesis{{background:var(--accent);color:#fff;border-radius:26px;padding:clamp(24px,4.4vw,46px);box-shadow:var(--shadow)}}
/* Was rgba(255,255,255,.75) = 4.06:1 on --accent. 12.5px bold is not "large text"
   under AA (that needs 18.5px, or 14pt bold), so it needed 4.5 and did not have it.
   .90 gives 5.13:1 and still reads as a quieter layer than the quote. */
.thesis .eyebrow{{color:rgba(255,255,255,.9)}}
/* The headline and the body MUST share one measure, or they read as mis-aligned.
   Measured at 1280px with only the body capped: the headline ran to x=1117 while
   the body stopped at x=937 — 181px short — and because the headline's own three
   line-ends sat within 33px of each other it implied a hard right edge the body
   then failed to reach. The fix is NOT to widen the body: at the headline's 1028px
   the body would run 62 full-width CJK chars per line, past the ~40-45 where CJK
   reading starts needing a scan back to find the next line. So the HEADLINE comes
   in to the body's measure instead. One shared var, so the two cannot drift apart.
   At 820px both end within 5px of each other; headline stays 4 lines / 19 chars.
   Note this only misread at >=1200px: at 1024px the headline already wrapped to 4
   ragged lines (its own line-ends spread over 744px), which implies no right edge
   at all, so the same 64px shortfall was invisible. A width-specific defect. */
.thesis{{--measure:820px}}
/* balance here too — display text, same reasoning as .hero-sub above. Measured:
   orphan last line at 5 of 9 widths (worst 9% of the widest line at 640-900px);
   with balance, 81-87% at every width. The .thesis <p> below is body copy and
   stays untouched. */
.thesis blockquote{{max-width:var(--measure);font-size:clamp(23px,3.9vw,42px);line-height:1.1;letter-spacing:-.035em;margin:10px 0 16px;font-weight:750;
  text-wrap:balance}}
.thesis p{{max-width:var(--measure);margin:0;color:rgba(255,255,255,.85);font-size:16.5px}}

/* ---- category headers ---- */
section[id]{{scroll-margin-top:86px;margin:34px 0 0}}
.cat-head{{display:flex;align-items:center;gap:14px;padding:15px 20px;border-radius:16px;color:#fff;margin:0 0 4px}}
.cat-head h2{{font-size:clamp(20px,2.7vw,28px);letter-spacing:-.03em;margin:0;line-height:1.15}}
.cat-head .cat-desc{{margin:2px 0 0;font-size:13.5px;opacity:.88}}
.cat-head .cat-txt{{flex:1;min-width:0}}
/* The count chip was rgba(255,255,255,.18) — a LIGHT wash on the category colour,
   which lifted the background toward the white text sitting on it. White-on-chip
   measured 3.93 / 4.05 / 4.20 / 4.25 / 5.73:1 across the five sections: four of
   five under AA, and the chip was LESS readable than the same text with no chip
   at all (5.75:1 worst). A pre-existing failure, found by re-measuring every
   pairing rather than only the ones I changed. Inverted to a dark wash, which
   darkens the ground instead of lifting it: 7.66:1 worst case. */
.cat-head em{{font-style:normal;font-size:13px;font-weight:700;background:rgba(0,0,0,.18);border-radius:99px;padding:5px 12px;white-space:nowrap}}
.cat-emoji{{font-size:29px;line-height:1}}
.cat-head.c1{{background:var(--c1)}}
.cat-head.c2{{background:var(--c2)}}
.cat-head.c3{{background:var(--c3)}}
.cat-head.c4{{background:var(--c4)}}
.cat-head.c5{{background:var(--c5)}}

/* ---- story cards ----
   NOTE: no align-items:start here, on purpose. With it, every card shrank to its
   own content height, so two cards in the same row ended at different heights and
   the grid read as "misaligned" — the complaint readers actually raised. Letting
   the row stretch (grid's default) makes cards in a row equal height, and
   .story-foot{{margin-top:auto}} then pins every 閱讀原文 button to the same
   baseline. Card heights still differ BETWEEN rows, which is fine and expected. */
.stories{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px;margin-top:16px}}
.story{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px 24px;box-shadow:0 8px 30px rgba(16,17,20,.035);border-top:5px solid var(--line);display:flex;flex-direction:column}}
.story.c1{{border-top-color:var(--c1)}}
.story.c2{{border-top-color:var(--c2)}}
.story.c3{{border-top-color:var(--c3)}}
.story.c4{{border-top-color:var(--c4)}}
.story.c5{{border-top-color:var(--c5)}}
/* Tightened hierarchy: exactly three type sizes inside a card — source line
   (12px), body (15px), title (~21px) — and one label style for every block
   heading. Before, 重點摘要/行業洞察/趨勢觀察 each had its own size, colour and
   box treatment, so a card had five competing levels and the eye had nowhere
   obvious to land. Now the title dominates, 行業洞察 is the single tinted block,
   and everything else is plain body text on an 8px spacing rhythm. */
.story-meta{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px;font-size:12px}}
.src{{font-weight:750;padding:4px 10px;border-radius:999px;letter-spacing:.02em;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
/* Pill text uses --cNt, NOT --cN. The solid category colour on its own tint only
   reaches 4.34–4.56:1 for the three blue-violet hues — under AA for 12px text.
   --cNt is the same hue pushed darker until >=4.8:1, so the pill stays on-hue and
   stays readable. Measured: c1 5.01 · c2 5.22 · c3 5.27 · c4 5.09 · c5 6.82. */
.story.c1 .src{{background:var(--c1s);color:var(--c1t)}}
.story.c2 .src{{background:var(--c2s);color:var(--c2t)}}
.story.c3 .src{{background:var(--c3s);color:var(--c3t)}}
.story.c4 .src{{background:var(--c4s);color:var(--c4t)}}
.story.c5 .src{{background:var(--c5s);color:var(--c5t)}}
.date{{color:var(--muted)}}
/* Subscription flag: readers were clicking through and hitting a paywall with no
   warning. Flagging it on the card itself sets the expectation before the click. */
.paywall{{display:inline-flex;align-items:center;gap:4px;font-weight:750;font-size:11.5px;padding:4px 9px;border-radius:999px;background:#fdf3e2;color:var(--amber);border:1px solid #edd9ab;white-space:nowrap}}
.story .no{{margin-left:auto;color:var(--line);font-weight:800;font-size:14px;font-family:PlexMonoLat,ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.story h3{{font-size:clamp(18px,2.05vw,21.5px);line-height:1.28;letter-spacing:-.022em;margin:2px 0 10px;text-wrap:balance}}
.story h3 a{{text-decoration:none}}
.story h3 a:hover{{text-decoration:underline;text-underline-offset:4px;color:var(--accent-d)}}
.story h3 a:focus-visible{{outline:2px solid var(--accent);outline-offset:3px}}
.block{{margin:0 0 10px}}
.block b.k,.take b.k,.predict b.k,.detail b.k,.followup b.k{{display:block;font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.11em;margin-bottom:5px;color:var(--muted)}}
.block p{{margin:0;color:var(--body);font-size:15px;line-height:1.62}}
.kh{{margin:0;padding-left:19px;color:var(--body);font-size:15px;line-height:1.62}}
.kh li{{margin-bottom:5px}}
.kh li:last-child{{margin-bottom:0}}
.take{{border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 12px 12px 0;padding:12px 16px;margin:10px 0}}
.take b.k{{color:var(--accent)}}
.take p{{margin:0;font-size:15px;line-height:1.62;color:var(--ink)}}
.predict{{border-left:3px solid #e3c76c;background:#fff8e8;border-radius:0 12px 12px 0;padding:12px 16px;margin:0 0 10px}}
.predict b.k{{color:var(--amber)}}
.predict p{{margin:0;font-size:15px;line-height:1.62;color:var(--body)}}
/* 昨日續篇 — the delta against an earlier day's card. Sits directly under the
   headline, before 重點摘要, because it is the context the reader needs first.
   Cool blue so it reads as "orientation", distinct from 行業洞察 (purple, our
   opinion) and 趨勢觀察 (amber, forward-looking). */
.followup{{border-left:3px solid #60bdf1;background:#eef7fd;border-radius:0 12px 12px 0;padding:11px 16px;margin:0 0 11px}}
.followup b.k{{color:#1d6f9e}}
.followup p{{margin:0;font-size:14.5px;line-height:1.6;color:var(--body)}}
/* Expandable full write-up — the paywall workaround. Our own Chinese/English
   account of the story lives here, so a reader who cannot open the source still
   gets the substance without leaving the page. Collapsed by default so the
   20-card grid stays scannable; <details> means it works with JS disabled. */
.detail{{border:1px solid var(--line);border-radius:14px;background:rgba(247,245,239,.6);margin:0 0 10px;overflow:hidden}}
.detail>summary{{cursor:pointer;list-style:none;padding:10px 15px;font-weight:750;font-size:13px;color:var(--ink);display:flex;align-items:center;gap:7px}}
.detail>summary::-webkit-details-marker{{display:none}}
.detail>summary::after{{content:"＋";margin-left:auto;color:var(--accent);font-weight:800;font-size:14px}}
.detail[open]>summary::after{{content:"－"}}
.detail>summary:hover{{color:var(--accent-d)}}
.detail>summary:focus-visible{{outline:2px solid var(--accent);outline-offset:-2px}}
.detail-body{{padding:2px 15px 14px;border-top:1px solid var(--line)}}
.detail-body p{{margin:9px 0 0;color:var(--body);font-size:14.5px;line-height:1.68}}
.detail-body p:first-child{{margin-top:10px}}
.detail-body .why-src{{margin-top:11px;font-size:12px;color:var(--muted)}}
.story-foot{{display:flex;flex-wrap:wrap;gap:9px;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding-top:12px;margin-top:auto}}
.foot-tags{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.signal{{font-weight:800;font-size:12.5px;padding:6px 12px;border-radius:999px;white-space:nowrap}}
.signal.act{{background:#e2f3ec;color:var(--green)}}
.signal.watch{{background:#fdf3e2;color:var(--amber)}}
.signal.impact{{background:var(--accent-soft);color:var(--accent)}}
.chip{{font-size:11.5px;padding:5px 10px;border-radius:99px;white-space:nowrap}}
.chip.region{{border:1px solid var(--line);color:var(--muted)}}
.readsrc{{text-decoration:none;font-weight:800;font-size:13px;background:var(--ink);color:#fff;padding:8px 14px;border-radius:999px;white-space:nowrap}}
.readsrc:hover{{background:var(--accent)}}
.empty{{margin:0;padding:22px 24px;border:1px dashed var(--line);border-radius:18px;color:var(--muted);font-size:14.5px;background:rgba(255,255,255,.5)}}

/* ---- 三分鐘看完 (top-of-page digest) ----
   A 20-card page is a lot to face cold. This lists only the 可即用 / 影響生意
   items as one-liners that jump straight to the card, so a reader with three
   minutes still leaves knowing what mattered. */
.tldr{{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:16px;padding:18px 22px;margin:22px 0 4px;box-shadow:0 8px 30px rgba(16,17,20,.035)}}
.tldr-head{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px}}
.tldr-head b{{font-size:15.5px;letter-spacing:-.01em}}
.tldr-head span{{font-size:12px;color:var(--muted)}}
.tldr ol{{margin:0;padding-left:0;list-style:none;counter-reset:t}}
.tldr li{{counter-increment:t;display:flex;gap:10px;align-items:baseline;padding:7px 0;border-top:1px solid rgba(222,219,210,.65)}}
.tldr li:first-child{{border-top:0;padding-top:0}}
.tldr li::before{{content:counter(t);flex:none;width:20px;font-size:11.5px;font-weight:800;color:var(--accent);font-family:PlexMonoLat,ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums;padding-top:3px}}
.tldr a{{text-decoration:none;color:var(--ink);font-size:14.5px;line-height:1.55}}
.tldr a:hover{{color:var(--accent-d);text-decoration:underline;text-underline-offset:3px}}
.tldr .t-tag{{font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:99px;margin-right:7px;white-space:nowrap;vertical-align:1px}}
.tldr .t-tag.act{{background:#e2f3ec;color:var(--green)}}
.tldr .t-tag.impact{{background:var(--accent-soft);color:var(--accent)}}

/* ---- reading progress + active section ----
   Long single-page scroll with no sense of position. The top bar shows how far
   in you are; the nav pill for the section you are reading lights up. */
/* The progress bar and the topbar's Lime line were both pinned to the top of the
   viewport — #prog (fixed, 3px, z40) drew straight over the topbar's 4px Lime
   border (z20), so a violet bar crept across the brand line as you scrolled.
   Resolved by making them ONE element: the top strip is a dim Lime track that
   fills with full Lime as you read. Reading position is a real status, which is
   the only thing Lime is allowed to express. Fill on track = 7.6:1. */
#prog{{position:fixed;left:0;top:0;height:4px;width:100%;transform-origin:0 50%;transform:scaleX(0);background:var(--lime);z-index:40;pointer-events:none;transition:transform .08s linear}}
.navlinks a.cur{{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-d);font-weight:700}}
/* a card jumped to from 三分鐘看完 flashes once so the eye finds it */
.story:target{{box-shadow:0 0 0 3px var(--accent)}}
/* Jump offset = the sticky topbar's real height, measured rather than guessed.
   It was a flat 96px against a topbar that measures 121px at desktop widths and
   at ≤560px (where .mast wraps to two rows), and 71px in the 561–760px band. So
   every jump from 三分鐘看完 or a shared link parked the headline ~25px UNDER the
   bar at the two widths most people read on. --jump follows the same breakpoints
   as the topbar itself and carries 8px of breathing room. */
:root{{--jump:129px}}
.story{{scroll-margin-top:var(--jump)}}
/* Legacy s{{n}} anchor, kept so links shared against an earlier issue still land.
   It lives inside the card (a sibling would become a grid item and blow up the
   two-column layout), takes no space, and carries the same scroll offset as the
   card so the sticky header does not cover the headline it jumped to. The
   :target ring is drawn on the card, not the 0×0 anchor, which has nothing to
   outline. */
.idalias{{display:inline;width:0;height:0;overflow:hidden;scroll-margin-top:var(--jump)}}
.idalias:target + *,
.story:has(> .idalias:target){{box-shadow:0 0 0 3px var(--accent)}}

footer{{border-top:1px solid var(--line);margin-top:48px;padding:26px 0 44px;font-size:13px;color:var(--muted);line-height:1.85}}
footer b{{color:var(--ink)}}
/* ---- back to top --------------------------------------------------------------
   Bottom RIGHT, deliberately: #toast is fixed bottom-CENTRE at z-index 50, and a
   bottom-centre button would be covered by the copy-link toast at the exact moment
   a reader might use both. Sits at z-index 45 — under the toast, over the cards.
   `visibility` (not just opacity) so the hidden state is also untabbable; opacity
   alone leaves an invisible button that a keyboard user can focus and press. */
#totop{{position:fixed;right:20px;bottom:22px;z-index:45;display:inline-flex;align-items:center;gap:6px;
  font:inherit;font-size:13px;font-weight:700;color:var(--i-navy);background:var(--lime);
  border:1px solid rgba(12,16,45,.22);border-radius:999px;padding:9px 15px;cursor:pointer;
  box-shadow:0 6px 18px rgba(12,16,45,.22);
  opacity:0;visibility:hidden;transform:translateY(10px);transition:opacity .2s,transform .2s,visibility .2s}}
#totop.on{{opacity:1;visibility:visible;transform:translateY(0)}}
#totop svg{{width:15px;height:15px;flex:none}}
#totop:hover{{background:#e2ff86}}
#totop:focus-visible{{outline:2px solid var(--i-navy);outline-offset:2px}}
/* Phones: the label is redundant next to the arrow and the button is closest to a
   thumb, where a wide pill covers the most text. Arrow only, round. */
@media (max-width:560px){{
  #totop{{right:14px;bottom:16px;padding:10px;border-radius:50%}}
  #totop span{{position:absolute;left:-9999px}}
  #totop svg{{width:17px;height:17px}}
}}
#toast{{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;z-index:50}}
#toast.on{{opacity:1;transform:translateX(-50%) translateY(0)}}

@media (max-width:1000px){{
  .stories{{grid-template-columns:1fr}}
}}
/* Jump offset for the one band where the sticky topbar is short. Measured
   .topbar height: 121px at 1400px, 71px at 760px, 121px again at 560px — the
   category pills drop out at 760px so the bar collapses to one row, then .mast
   itself wraps to two rows below 561px and it is tall again. Hence an explicit
   range rather than a plain max-width: a `max-width:760px` override would also
   catch the ≤560px case, which needs the tall value. Written as its own block so
   it does not depend on where it sits among the other media queries. */
@media (min-width:561px) and (max-width:760px){{
  :root{{--jump:79px}}
}}
@media (max-width:760px){{
  .hero{{padding-top:36px}}
  /* 2 columns; an odd section count would leave a dangling empty cell, so the
     last stat spans the full row instead of showing a blank box. */
  .stats{{grid-template-columns:repeat(2,1fr)}}
  .stats>.stat:last-child:nth-child(odd){{grid-column:1/-1}}
  .story{{padding:20px 18px}}
  .cat-head{{padding:13px 15px;gap:11px}}
  /* Category pills go; Archive and Share stay (they live outside .navlinks now).
     The strip is then empty, so it must not keep claiming flex space — without
     `flex:none` an empty `flex:1 1 auto` item still pushes the remaining controls
     around. */
  .navlinks a:not(.pill){{display:none}}
  .navlinks{{flex:none}}
  .tldr{{padding:16px 17px;border-radius:14px}}
  .tldr a{{font-size:14px}}
}}
/* ---- phone fold ----------------------------------------------------------
   At 390px the masthead, headline, lede, four meta pills, byline, two buttons
   and the legend filled the entire first screen, so a reader had to scroll
   past a full viewport of furniture before the first story. These trims are
   spacing and type-scale only — nothing is hidden, and the desktop layout is
   untouched. Measured on a 390x844 viewport: first card moves ~210px up. */
@media (max-width:460px){{
  .hero{{padding:24px 0 6px}}
  h1{{font-size:clamp(31px,8.6vw,40px);margin:10px 0 12px;letter-spacing:-.045em}}
  .hero-sub{{font-size:15.5px;line-height:1.5;margin:0 0 15px}}
  /* The four pills were one per row at this width. Smaller type and tighter
     padding fits them two-up, which is 2 rows instead of 4. */
  .issue-meta{{gap:7px;margin-bottom:13px}}
  .issue-meta>span{{padding:6px 11px;font-size:12px}}
  .byline{{padding:10px 0 2px;font-size:12.5px;gap:7px}}
  /* was `.heroacts{{margin-top:11px;gap:8px}}` — that row no longer exists.
     At this width the topbar carries Archive + Share, so trim those instead. */
  .navlinks{{gap:6px}}
  .navlinks a.pill,.mast-r>a.pill,#share{{padding:6px 10px;font-size:12.5px}}
  .legend{{padding:13px 0 0;gap:7px 14px;font-size:12px}}
  .stats{{margin:15px 0 6px}}
  .stat{{padding:12px 5px}}
  .stat b{{font-size:23px}}
  .section{{padding:24px 0 6px}}
}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}html{{scroll-behavior:auto}}}}
/* skip link: 20+ cards is a long tab-through for keyboard/screen-reader users */
.skip{{position:absolute;left:-9999px;top:0;z-index:60;background:var(--ink);color:#fff;padding:11px 18px;border-radius:0 0 8px 0;text-decoration:none;font-weight:700;font-size:14px}}
.skip:focus{{left:0}}
/* print / PDF: many readers forward this as a PDF to clients */
@media print{{
  body{{background:#fff}}
  /* .heroacts dropped from this list with the markup. #totop added: a printed page
     has no "top" to scroll to, so it would print as a stray green pill on page 1. */
  .topbar,.langtog,#share,#sharebox,#toast,#totop,.navlinks,#prog,#a2hs{{display:none!important}}
  .story{{break-inside:avoid;page-break-inside:avoid;box-shadow:none;border:1px solid #ccc}}
  .cat-head{{break-after:avoid;page-break-after:avoid;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .thesis,.take,.src,.signal,.paywall,.tldr{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .tldr{{break-inside:avoid;page-break-inside:avoid;box-shadow:none}}
  /* A PDF cannot be expanded, and for a paywalled story the write-up IS the
     content — so it prints open (forced via the beforeprint handler, since a
     collapsed <details> cannot be un-hidden by CSS alone). */
  .detail>summary{{display:none}}
  .detail-body{{border-top:0;padding-top:0}}
  .detail{{background:#fff;border-color:#ccc;break-inside:avoid;page-break-inside:avoid}}
  .stories{{grid-template-columns:1fr}}
  a[href^="http"]::after{{content:" (" attr(href) ")";font-size:9.5px;color:#666;word-break:break-all}}
  .readsrc::after{{content:none}}
}}
</style>
</head>
<body>
<a class="skip" href="#main">{bi("跳至內容", "Skip to content")}</a>
<div id="prog" role="presentation"></div>
<div class="topbar"><div class="wrap"><div class="mast">
  <div class="brand">{bi(SITE_TITLE, SITE_TITLE_EN)}<small>{html.escape(SITE_TAGLINE)}</small></div>
  <div class="mast-r">
    <div class="navlinks">{nav}</div>
    <!-- Archive and Share sit OUTSIDE .navlinks. .navlinks is the horizontally
         scrolling category strip, and a control placed inside it scrolls away with
         the categories: measured at 1280px, Share's right edge landed at x=1455 on
         a 1280 viewport — reachable only by dragging the nav sideways, which is the
         same as not being there. These two are pinned next to the language toggle
         with flex:none instead. -->
    <a class="pill fix" href="archive/">{bi("歷史存檔", "Archive")}</a>
    <button id="share" type="button">{bi("分享", "Share")}</button>
    <div class="langtog" role="group" aria-label="Language / 語言">
      <button type="button" data-set="en" class="on" aria-pressed="true" aria-label="English">EN</button>
      <button type="button" data-set="zh" aria-pressed="false" aria-label="繁體中文（台灣・香港）">中文</button>
    </div>
  </div>
</div></div></div>

<header class="hero"><div class="wrap">
  <div class="eyebrow">{bi("每日情報", "Daily Brief")}　·　{bi(date_disp, date_disp_en)}</div>
  <h1>{_h1(HEADLINE, HEADLINE_EN)}</h1>
  <p class="hero-sub">{bi(STANDFIRST, STANDFIRST_EN)}</p>
  <div class="issue-meta">
    <span><b>{total}</b>{bi(" 則 · ", " stories · ")}<b>{len(data["sections"])}</b>{bi(" 個分類", " categories")}</span>
    <span>{bi("每則附一手來源", "Every story sourced")}</span>
    <span>{bi(f"約 {READ_MIN} 分鐘讀完", f"{READ_MIN}-minute read")}</span>
    <span>{bi("🟢 即用　·　🟡 留意　·　🟣 影響生意", "🟢 Act · 🟡 Watch · 🟣 Business impact")}</span>
  </div>
  <div class="byline">
    <span class="who">{bi("主編：" + BYLINE, "Curated by " + BYLINE)}</span><span class="dot">·</span>
    <span>{bi(BYLINE_ROLE, BYLINE_ROLE_EN)}</span>{('<span class="dot">·</span>' + _weekly_link) if _weekly_link else ''}{('<span class="dot">·</span>' + _li_link) if _li_link else ''}
  </div>
  <!-- The .heroacts row is gone. It held "分享給同事" and "📚 歷史存檔" — and the
       sticky topbar already carries an Archive pill, so BOTH buttons were duplicates
       of controls one scroll-line above them, costing first-screen space on every
       visit to a page people read daily. Share moved into the topbar (where it is
       reachable from any scroll position, not only the top); Archive was already
       there. #sharebox stays: it is the last-resort fallback when both the Web Share
       API and the clipboard are unavailable, and the script still targets it. -->
  <div id="sharebox"><span>{bi("長按或全選以複製：", "Long-press / select all to copy:")}</span><input type="text" readonly value="{html.escape(SITE_URL)}"></div>
  <!-- Add-to-home-screen hint. Shown ONLY on a phone/tablet that is NOT already
       running standalone, and dismissable for 90 days. A banner that reappears every
       morning on a daily-read site would be worse than no banner: it costs first-screen
       space every single visit to deliver a one-time instruction. The iOS and Android
       wording differ because the menu item does — telling an iPhone user to look for
       「安裝應用程式」 sends them hunting for something that is not there. -->
  <div id="a2hs" hidden>
    <span class="a2hs-ic" aria-hidden="true">📲</span>
    <!-- Both platforms' wording is rendered into the DOM and one is revealed with a
         class. Writing it in via innerHTML/textContent would either inject markup or
         print the bilingual <span> tags as literal text, and it would also break the
         EN/中文 toggle, which works by CSS on those same spans. -->
    <p class="a2hs-txt"><b>{bi("想每朝一撳就睇？", "Read it like an app?")}</b>
      <span class="a2hs-ios">{bi("在 Safari 按下方「分享」→「加入主畫面」，就可以像 App 一樣全螢幕開啟，沒有網址列。", "In Safari, tap Share below → “Add to Home Screen” to open it full-screen like an app.")}</span><span class="a2hs-and">{bi("按瀏覽器右上角的選單鍵（三點）→「安裝應用程式／加到主畫面」，就可以像 App 一樣全螢幕開啟。", "Tap the three-dot menu at the top right of your browser → “Install app / Add to Home screen” to open it full-screen like an app.")}</span>
    </p>
    <button id="a2hs-x" type="button" aria-label="{html.escape(bi_attr('關閉這個提示', 'Dismiss this tip'))}">✕</button>
  </div>
  <div class="legend"><span class="lg"><span class="signal act">{bi("可即用", "Ready to use")}</span>{bi("今天可用／節省工時", "try today / save time")}</span><span class="lg"><span class="signal watch">{bi("要留意", "Worth watching")}</span>{bi("平台或趨勢變動", "platform / trend shift")}</span><span class="lg"><span class="signal impact">{bi("影響生意", "Business impact")}</span>{bi("代理商生態／客戶／法規", "agency / client / compliance")}</span></div>
  <div class="stats">{stats}</div>
  {tldr_html}
</div></header>

<div class="wrap">{thesis_html}</div>

<main class="wrap" id="main">
{sections_html}
</main>

<footer><div class="wrap">
<p><span class="l-zh">今天共 <b>{total}</b> 則精選　·　每日更新　·　為 AI 驅動的行銷團隊而設</span><span class="l-en"><b>{total}</b> stories today　·　updated every morning　·　built for AI-driven agencies</span></p>
<p>{bi("資料來源：", "Sources: ")}{bi(sources_note, sources_note_en)}</p>
<p>{bi("內容僅供資訊參考。", "For informational reference only.")}</p>
</div></footer>
<!-- Back to top. Hidden until 1.5 viewports down (see the scroll handler) so it is
     not furniture on the first screen. `aria-hidden` is NOT used: the button is
     genuinely actionable whenever it is visible, and it is removed from the tab
     order by `visibility` while hidden, which is the accessible equivalent. -->
<button id="totop" type="button" aria-label="{html.escape(bi_attr('回到頁首', 'Back to top'))}">
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5l-7 7h4.2v7h5.6v-7H19z" fill="currentColor"/></svg>
  <span>{bi("頁首", "Top")}</span>
</button>
<div id="toast"></div>
<script>
const SHARE_URL={json.dumps(SITE_URL) if SITE_URL else "location.href"};
const MSG={{zh:'連結已複製，可直接分享給同事', en:'Link copied — share it with your team'}};
function curLang(){{return document.documentElement.getAttribute('data-lang')==='en'?'en':'zh'}}
function setLang(l){{
  document.documentElement.setAttribute('data-lang',l);
  document.documentElement.lang=(l==='en'?'en':'zh-Hant');
  try{{localStorage.setItem('amd-lang',l)}}catch(e){{}}
  document.querySelectorAll('.langtog button').forEach(b=>{{const on=b.dataset.set===l;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false')}});
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

/* ---- add-to-home-screen hint ----
   Three gates, all of which must pass before the tip appears:
     1. a touch device — `(hover:none) and (pointer:coarse)` is true on phones and
        tablets and false on desktops (including Windows touch laptops, whose
        primary pointer is still a mouse). A desktop reader has no "add to home
        screen", so showing the tip there would simply be wrong. Deliberately NOT
        gated on screen.width as well: that value is unreliable in embedded and
        headless browsers, and it would exclude a landscape tablet where the tip
        is perfectly valid. The pointer query is the honest signal.
     2. not already running standalone — someone who installed it must never be
        told to install it (display-mode:standalone on Android/Chrome,
        navigator.standalone on iOS Safari);
     3. not dismissed in the last 90 days — this is a site people open every
        morning, so a permanent banner would tax every visit to deliver a
        one-time instruction. Dismiss is remembered, and the whole thing is
        wrapped in try/catch because Safari private mode throws on localStorage.
   The instructions differ per platform because the menu item genuinely differs. */
(function(){{
  var box=document.getElementById('a2hs'); if(!box) return;
  var x=document.getElementById('a2hs-x');
  var KEY='amd-a2hs-off', DAYS=90;
  function off(){{
    try{{
      var v=localStorage.getItem(KEY);
      return !!v && (Date.now()-parseInt(v,10)) < DAYS*864e5;
    }}catch(e){{return false}}
  }}
  var standalone = (window.matchMedia && matchMedia('(display-mode:standalone)').matches)
                   || navigator.standalone===true;
  var touch = matchMedia('(hover:none) and (pointer:coarse)').matches;
  if(standalone || !touch || off()) return;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent)
            || (navigator.platform==='MacIntel' && navigator.maxTouchPoints>1);
  box.classList.add(ios ? 'is-ios' : 'is-and');
  box.hidden = false;
  x.addEventListener('click', function(){{
    box.hidden = true;
    try{{localStorage.setItem(KEY, String(Date.now()))}}catch(e){{}}
  }});
}})();

/* ---- reading progress + which section am I in ----
   scaleX on a fixed bar (compositor-only, no layout work per scroll event) and
   an IntersectionObserver for the nav highlight. rAF-throttled so a fast scroll
   on a 20-card page does not queue up work. */
(function(){{
  var bar=document.getElementById('prog'), pending=false;
  /* Back-to-top piggybacks on THIS handler instead of registering its own scroll
     listener: two listeners on a 20-card page means two callbacks per frame doing
     the same scrollY read. Threshold is one and a half viewports — below that the
     topbar is still a short flick away and the button would only cover content. */
  var top=document.getElementById('totop');
  function draw(){{
    pending=false;
    var h=document.documentElement.scrollHeight-window.innerHeight;
    bar.style.transform='scaleX('+(h>0?Math.min(1,Math.max(0,window.scrollY/h)):0)+')';
    if(top)top.classList.toggle('on',window.scrollY>window.innerHeight*1.5);
  }}
  if(top)top.addEventListener('click',function(){{
    /* Move focus to the skip link's target as well as scrolling. A keyboard or
       screen-reader user who only got a scroll would still be tabbing from the
       footer on the next Tab press, i.e. the button would do nothing for them. */
    var rm=matchMedia('(prefers-reduced-motion:reduce)').matches;
    window.scrollTo({{top:0,behavior:rm?'auto':'smooth'}});
    var b=document.querySelector('.brand');
    if(b){{b.setAttribute('tabindex','-1');b.focus({{preventScroll:true}})}}
  }});
  addEventListener('scroll',function(){{if(!pending){{pending=true;requestAnimationFrame(draw)}}}},{{passive:true}});
  addEventListener('resize',draw,{{passive:true}});
  draw();

  var links={{}};
  document.querySelectorAll('.navlinks a[href^="#"]').forEach(function(a){{links[a.getAttribute('href').slice(1)]=a}});
  /* Printing / saving as PDF: open every write-up first (a collapsed <details>
     is hidden by the UA, not by our CSS, so only the open attribute works),
     then restore whatever the reader had open. */
  var wasOpen=null;
  addEventListener('beforeprint',function(){{
    var d=document.querySelectorAll('details.detail');
    wasOpen=[].map.call(d,function(x){{return x.open}});
    [].forEach.call(d,function(x){{x.open=true}});
  }});
  addEventListener('afterprint',function(){{
    if(!wasOpen)return;
    [].forEach.call(document.querySelectorAll('details.detail'),function(x,i){{x.open=!!wasOpen[i]}});
    wasOpen=null;
  }});

  var secs=[].slice.call(document.querySelectorAll('main section[id]')).filter(function(s){{return links[s.id]}});
  if(!secs.length||!('IntersectionObserver' in window))return;
  /* Track every visible section and light the topmost one: with tall sections a
     "last one crossed" rule leaves the wrong pill lit when scrolling back up. */
  var vis={{}};
  var io=new IntersectionObserver(function(es){{
    es.forEach(function(e){{vis[e.target.id]=e.isIntersecting}});
    var cur=null;
    for(var i=0;i<secs.length;i++){{if(vis[secs[i].id]){{cur=secs[i].id;break}}}}
    Object.keys(links).forEach(function(k){{links[k].classList.toggle('cur',k===cur)}});
  }},{{rootMargin:'-88px 0px -55% 0px'}});
  secs.forEach(function(s){{io.observe(s)}});
}})();
</script>{_analytics}
</body>
</html>
'''

(ROOT / "index.html").write_text(page, encoding="utf-8")

# --- Remember today's urls so tomorrow's run can spot a repeat ---------------
# Keyed by date and pruned to 14 days. Re-running today just overwrites today's
# entry, so the file never poisons its own dedup check.
if ISO:
    _seen[ISO] = sorted({_norm_url(i.get("url", "")) for i in data["items"] if i.get("url")})
    try:
        _cut = datetime.strptime(ISO, "%Y-%m-%d") - timedelta(days=14)
        _seen = {d: u for d, u in _seen.items()
                 if (lambda x: x is None or x >= _cut)(
                     (lambda: (datetime.strptime(d, "%Y-%m-%d") if re.match(r"^\d{4}-\d{2}-\d{2}$", d) else None))())}
    except Exception:
        pass
    _seen_path.write_text(json.dumps(_seen, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")

# --- Remember today's HEADLINES too -----------------------------------------
# seen-urls.json can only catch the same link twice. A genuine follow-up is a
# DIFFERENT article about the same developing story, so the url check is blind
# to exactly the case that matters most to the reader: "this ran yesterday —
# what changed?". Storing headlines lets tomorrow's run recognise the thread.
if ISO:
    _stories[ISO] = [{"t": (i.get("title", "") or "").strip(),
                      "u": _norm_url(i.get("url", ""))}
                     for i in data["items"] if (i.get("title", "") or "").strip()]
    try:
        _cut2 = datetime.strptime(ISO, "%Y-%m-%d") - timedelta(days=14)
        _stories = {d: v for d, v in _stories.items()
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", d)
                    and datetime.strptime(d, "%Y-%m-%d") >= _cut2}
    except Exception:
        pass
    _stories_path.write_text(json.dumps(_stories, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                             encoding="utf-8")

print(f"OK index.html total={total} sections=" + ",".join(f"{s}:{len(groups[s])}" for s in data["sections"])
      + (f"  ⚠ {_warn} warning(s) — 見上面 stderr" if _warn else "  (0 warnings)"))
