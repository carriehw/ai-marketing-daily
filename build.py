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
  重點摘要 Key Highlights   ← items[].highlights[] (2–3 bullets); falls back to summary
  行業洞察 Industry Insight ← items[].why
  趨勢觀察 Pattern Watch    ← items[].pattern (OPTIONAL — see "follow-ups" below)
  signal tag · region tag · 閱讀原文 →

FOLLOW-UPS, NOT DUPLICATE CARDS
  When today's news advances a story already published, do NOT cut a second card
  for it. Put the new angle in `pattern` on the ORIGINAL card. The dedup pass
  below drops same-URL repeats outright, so a duplicate card cannot reach the page.

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
                    highlights[], highlights_en[], pattern, pattern_en}

Any missing *_en field falls back to its Chinese value, so the site never breaks
on a day the translations are incomplete — it just shows Chinese in the EN view.

Run:  PYTHONIOENCODING=utf-8 python3 build.py
"""
import json, html, re, sys
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
ISO           = str(data.get("date", "")).strip()

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
for _i, _s in enumerate(data["sections"]):
    _d = _SEC_DEFAULTS.get(_s, ("📌", "", ""))
    SEC_EMOJI[_s]   = _emoji_in[_i]   if _i < len(_emoji_in)   and _emoji_in[_i]   else _d[0]
    SEC_DESC[_s]    = _desc_in[_i]    if _i < len(_desc_in)    and _desc_in[_i]    else _d[1]
    SEC_DESC_EN[_s] = _desc_en_in[_i] if _i < len(_desc_en_in) and _desc_en_in[_i] else (_d[2] or SEC_DESC[_s])

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
    """Rare terms two headlines have in common. Empirically: 0–1 shared term =
    unrelated stories about the same vendor; 2+ = the same story re-angled."""
    return _rare(_TERMS[i]) & _rare(_TERMS[j])

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
_TONG_OK = re.compile(r"(相同|同步|共同|同質|同時|同業|同一|同事|認同|同意|不同|同期|同類|同儕|同盟|同行|同名|贊同|雷同)")
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
_TERM_KEEP = re.compile(r"(電通數碼|數碼通|數碼港|香港數碼|數碼營銷署)")
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

def _to_written_zh(t):
    """Return (fixed_text, [(from, to), ...]) — longest keys first so 唔係→不是
    wins over 唔→不."""
    if not t:
        return t, []
    out, applied = str(t), []
    for _k in sorted(_ZH_FIX, key=len, reverse=True):
        if _k in out:
            out = out.replace(_k, _ZH_FIX[_k])
            applied.append((_k, _ZH_FIX[_k]))
    out, _tong = _fix_tong(out)
    if _tong:
        applied.append(("A同B", "A與B"))
    out, _terms = _fix_terms(out)
    applied.extend(_terms)
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

cards, n = {}, 0
for s in data["sections"]:
    out = []
    for it in groups[s]:
        n += 1
        url = html.escape(str(it.get("url", "")))
        act = it.get("action", "要留意")
        act_cls = ACT.get(act, "watch")
        reg = it.get("region", "")
        reg_cls = REG.get(reg, "r-other")
        src = html.escape(str(it.get("source", "")))
        tm = str(it.get("time", ""))
        sec_cls = SEC_CLS[s]

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

        out.append(f'''<article class="story {sec_cls}">
<div class="story-meta"><span class="src">{src}</span><span class="date">{bi(tm, _time_en(tm))}</span><span class="no">{n:02d}</span></div>
<h3><a href="{url}" target="_blank" rel="noopener noreferrer">{bi(it.get("title",""), it.get("title_en"))}</a></h3>
{body}
{take}
{pat}<div class="story-foot"><span class="foot-tags"><span class="signal {act_cls}">{bi(act, ACT_EN.get(act, act))}</span><span class="chip region {reg_cls}">{bi(reg, REG_EN.get(reg, reg))}</span></span><a class="readsrc" href="{url}" target="_blank" rel="noopener noreferrer">{bi("閱讀原文 →", "Read original →")}</a></div>
</article>''')
    cards[s] = "\n".join(out)

total = n
READ_MIN = data.get("read_minutes") or max(3, round(total * 0.5))

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
if _og_image:
    _og += (f'\n<meta property="og:image" content="{html.escape(_og_image)}">'
            f'\n<meta name="twitter:image" content="{html.escape(_og_image)}">')

# Structured data: lets the archive surface as a dated collection in search.
_ld = json.dumps({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": f"{SITE_TITLE_EN} · {date_disp_en}",
    "inLanguage": ["en", "zh-Hant"],
    "datePublished": ISO,
    "description": _desc_en,
    **({"url": SITE_URL} if SITE_URL else {}),
    "author": {"@type": "Person", "name": BYLINE},
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
<meta name="theme-color" content="#5a42f4">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%235a42f4'/><text x='16' y='23' font-size='19' font-weight='bold' text-anchor='middle' fill='white' font-family='sans-serif'>A</text></svg>">
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
:root{{
  --paper:#f7f5ef;--card:#fff;--ink:#101114;--muted:#656a73;--body:#3c3f45;
  --accent:#5a42f4;--accent-d:#4632d4;--accent-soft:#ebe8ff;
  --line:#dedbd2;--shadow:0 16px 45px rgba(16,17,20,.08);
  --c1:#1763d8;--c1s:#e8f0fd;
  --c2:#7a2fd0;--c2s:#f2e9fd;
  --c3:#1e7c5a;--c3s:#e2f3ec;
  --c4:#d63b2f;--c4s:#fdeceb;
  --c5:#a45a00;--c5s:#fdf3e2;
  --green:#1e7c5a;--amber:#a45a00;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:radial-gradient(circle at 85% 0%,rgba(90,66,244,.11),transparent 30%),var(--paper);color:var(--ink);font-family:Inter,"Noto Sans TC","Noto Sans HK",ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","PingFang HK","Microsoft JhengHei",sans-serif;line-height:1.65}}
a{{color:inherit}}
/* --- language toggle: show the active language, hide the other --- */
.l-en{{display:none}}
html[data-lang="en"] .l-en{{display:inline}}
html[data-lang="en"] .l-zh{{display:none}}
.wrap{{width:min(1120px,calc(100% - 32px));margin:0 auto}}

/* ---- masthead nav ---- */
.topbar{{border-top:4px solid var(--accent);background:rgba(247,245,239,.94);backdrop-filter:blur(6px);position:sticky;top:0;z-index:20;border-bottom:1px solid rgba(222,219,210,.8)}}
.mast{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 0;flex-wrap:wrap}}
.brand{{font-weight:800;letter-spacing:-.02em;font-size:19px;line-height:1.25}}
.brand span{{color:var(--accent)}}
.brand small{{display:block;font-weight:500;font-size:11.5px;color:var(--muted);letter-spacing:.16em;text-transform:uppercase}}
.mast-r{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.navlinks{{display:flex;gap:6px;align-items:center;overflow-x:auto;max-width:100%}}
.navlinks a{{white-space:nowrap;font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);background:var(--card);padding:6px 12px;border-radius:99px}}
.navlinks a i{{font-style:normal;color:var(--accent);margin-left:5px;font-variant-numeric:tabular-nums}}
.navlinks a:hover{{border-color:var(--accent);color:var(--accent-d)}}
.navlinks a.pill{{background:var(--ink);color:#fff;border-color:var(--ink)}}
.navlinks a.pill:hover{{background:var(--accent);border-color:var(--accent);color:#fff}}
.langtog{{display:inline-flex;border:1px solid var(--line);border-radius:99px;overflow:hidden;background:var(--card);flex:none}}
.langtog button{{font:inherit;font-size:12px;letter-spacing:.04em;padding:6px 14px;border:0;background:transparent;color:var(--muted);cursor:pointer}}
.langtog button+button{{border-left:1px solid var(--line)}}
.langtog button.on{{background:var(--accent);color:#fff}}
.langtog button:focus-visible{{outline:2px solid var(--ink);outline-offset:2px}}

/* ---- hero ---- */
.hero{{padding:52px 0 8px}}
.eyebrow{{color:var(--accent);font-weight:800;text-transform:uppercase;font-size:12.5px;letter-spacing:.14em}}
h1{{font-size:clamp(38px,6.4vw,74px);line-height:1.0;letter-spacing:-.05em;margin:14px 0 18px;font-weight:800}}
.hero-sub{{font-size:clamp(16.5px,1.9vw,20px);color:var(--muted);max-width:660px;margin:0 0 20px}}
.issue-meta{{display:flex;flex-wrap:wrap;gap:9px;margin-bottom:18px}}
.issue-meta span{{border:1px solid var(--line);background:var(--card);padding:7px 13px;border-radius:999px;font-size:13px;color:var(--muted)}}
.issue-meta span b{{color:var(--ink);font-weight:700}}
/* slim byline (personal credit, no full profile card) */
.byline{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0 4px;border-top:1px solid var(--line);font-size:13.5px;color:var(--muted)}}
.byline .who{{color:var(--ink);font-weight:750}}
.byline .dot{{color:var(--line)}}
.byline-link{{text-decoration:none;color:var(--accent);font-weight:700}}
.byline-link:hover{{text-decoration:underline;text-underline-offset:3px}}
.heroacts{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px}}
#share{{border:1px solid var(--ink);background:var(--ink);color:#fff;font:inherit;font-size:13.5px;font-weight:700;padding:9px 18px;border-radius:999px;cursor:pointer}}
#share:hover{{background:var(--accent);border-color:var(--accent)}}
#share:focus-visible{{outline:2px solid var(--ink);outline-offset:2px}}
.archlink{{font-size:13.5px;color:var(--ink);text-decoration:none;border:1px solid var(--line);background:var(--card);padding:9px 16px;border-radius:999px;white-space:nowrap;font-weight:600}}
.archlink:hover{{border-color:var(--accent);color:var(--accent)}}
#sharebox{{display:none;gap:8px;align-items:center;padding:12px 0 0}}
#sharebox.on{{display:flex}}
#sharebox input{{flex:1;font:inherit;font-size:13px;padding:8px 11px;border:1px solid var(--accent);border-radius:6px;color:var(--ink);background:#fff;min-width:0}}
#sharebox span{{font-size:12px;color:var(--muted);white-space:nowrap}}

/* ---- signal legend + section counters ---- */
.legend{{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:16px 0 0;font-size:12.5px;color:var(--muted)}}
.stats{{display:grid;grid-template-columns:repeat({max(1, len(data["sections"]))},1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:20px 0 8px}}
.stat{{background:var(--card);text-align:center;padding:15px 6px;text-decoration:none;color:var(--ink)}}
.stat b{{display:block;font-size:27px;color:var(--accent);font-variant-numeric:tabular-nums;letter-spacing:-.03em}}
.stat span{{font-size:11.5px;color:var(--muted);line-height:1.35;display:block}}
.stat:hover{{background:var(--accent-soft)}}

/* ---- today's signal ---- */
.section{{padding:34px 0 6px}}
.thesis{{background:var(--accent);color:#fff;border-radius:26px;padding:clamp(24px,4.4vw,46px);box-shadow:var(--shadow)}}
.thesis .eyebrow{{color:rgba(255,255,255,.75)}}
.thesis blockquote{{font-size:clamp(23px,3.9vw,42px);line-height:1.1;letter-spacing:-.035em;margin:10px 0 16px;font-weight:750}}
.thesis p{{max-width:820px;margin:0;color:rgba(255,255,255,.85);font-size:16.5px}}

/* ---- category headers ---- */
section[id]{{scroll-margin-top:86px;margin:34px 0 0}}
.cat-head{{display:flex;align-items:center;gap:14px;padding:15px 20px;border-radius:16px;color:#fff;margin:0 0 4px}}
.cat-head h2{{font-size:clamp(20px,2.7vw,28px);letter-spacing:-.03em;margin:0;line-height:1.15}}
.cat-head .cat-desc{{margin:2px 0 0;font-size:13.5px;opacity:.88}}
.cat-head .cat-txt{{flex:1;min-width:0}}
.cat-head em{{font-style:normal;font-size:13px;font-weight:700;background:rgba(255,255,255,.18);border-radius:99px;padding:5px 12px;white-space:nowrap}}
.cat-emoji{{font-size:29px;line-height:1}}
.cat-head.c1{{background:var(--c1)}}
.cat-head.c2{{background:var(--c2)}}
.cat-head.c3{{background:var(--c3)}}
.cat-head.c4{{background:var(--c4)}}
.cat-head.c5{{background:var(--c5)}}

/* ---- story cards ---- */
.stories{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px;margin-top:16px;align-items:start}}
.story{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:24px 26px;box-shadow:0 8px 30px rgba(16,17,20,.035);border-top:5px solid var(--line);display:flex;flex-direction:column}}
.story.c1{{border-top-color:var(--c1)}}
.story.c2{{border-top-color:var(--c2)}}
.story.c3{{border-top-color:var(--c3)}}
.story.c4{{border-top-color:var(--c4)}}
.story.c5{{border-top-color:var(--c5)}}
.story-meta{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;font-size:12.5px}}
.src{{font-weight:800;padding:5px 11px;border-radius:999px;letter-spacing:.02em;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.story.c1 .src{{background:var(--c1s);color:var(--c1)}}
.story.c2 .src{{background:var(--c2s);color:var(--c2)}}
.story.c3 .src{{background:var(--c3s);color:var(--c3)}}
.story.c4 .src{{background:var(--c4s);color:var(--c4)}}
.story.c5 .src{{background:var(--c5s);color:var(--c5)}}
.date{{color:var(--muted)}}
.story .no{{margin-left:auto;color:var(--line);font-weight:800;font-size:15px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.story h3{{font-size:clamp(18.5px,2.2vw,23px);line-height:1.25;letter-spacing:-.02em;margin:4px 0 12px;text-wrap:balance}}
.story h3 a{{text-decoration:none}}
.story h3 a:hover{{text-decoration:underline;text-underline-offset:4px;color:var(--accent-d)}}
.story h3 a:focus-visible{{outline:2px solid var(--accent);outline-offset:3px}}
.block{{margin:0 0 12px}}
.block b.k,.take b.k,.predict b.k{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px}}
.block b.k{{color:var(--muted)}}
.block p{{margin:0;color:var(--body);font-size:15.5px}}
.kh{{margin:0;padding-left:20px;color:var(--body);font-size:15.5px}}
.kh li{{margin-bottom:6px}}
.kh li:last-child{{margin-bottom:0}}
.take{{border-left:4px solid var(--accent);background:var(--accent-soft);border-radius:0 14px 14px 0;padding:13px 17px;margin:12px 0}}
.take b.k{{color:var(--accent)}}
.take p{{margin:0;font-size:15.5px}}
.predict{{background:#fff8e8;border:1px dashed #e3c76c;border-radius:14px;padding:12px 16px;margin:0 0 12px}}
.predict b.k{{color:var(--amber)}}
.predict p{{margin:0;font-size:14.5px;color:var(--body)}}
.story-foot{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding-top:14px;margin-top:auto}}
.foot-tags{{display:flex;gap:7px;align-items:center;flex-wrap:wrap}}
.signal{{font-weight:800;font-size:13px;padding:7px 13px;border-radius:999px;white-space:nowrap}}
.signal.act{{background:#e2f3ec;color:var(--green)}}
.signal.watch{{background:#fdf3e2;color:var(--amber)}}
.signal.impact{{background:var(--accent-soft);color:var(--accent)}}
.chip{{font-size:12px;padding:5px 11px;border-radius:99px;white-space:nowrap}}
.chip.region{{border:1px solid var(--line);color:var(--muted)}}
.readsrc{{text-decoration:none;font-weight:800;font-size:13.5px;background:var(--ink);color:#fff;padding:8px 15px;border-radius:999px;white-space:nowrap}}
.readsrc:hover{{background:var(--accent)}}
.empty{{margin:0;padding:22px 24px;border:1px dashed var(--line);border-radius:18px;color:var(--muted);font-size:14.5px;background:rgba(255,255,255,.5)}}

footer{{border-top:1px solid var(--line);margin-top:48px;padding:26px 0 44px;font-size:13px;color:var(--muted);line-height:1.85}}
footer b{{color:var(--ink)}}
#toast{{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;z-index:50}}
#toast.on{{opacity:1;transform:translateX(-50%) translateY(0)}}

@media (max-width:1000px){{
  .stories{{grid-template-columns:1fr}}
}}
@media (max-width:760px){{
  .hero{{padding-top:36px}}
  /* 2 columns; an odd section count would leave a dangling empty cell, so the
     last stat spans the full row instead of showing a blank box. */
  .stats{{grid-template-columns:repeat(2,1fr)}}
  .stats>.stat:last-child:nth-child(odd){{grid-column:1/-1}}
  .story{{padding:20px 18px}}
  .cat-head{{padding:13px 15px;gap:11px}}
  .navlinks a:not(.pill){{display:none}}
}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}html{{scroll-behavior:auto}}}}
/* skip link: 20+ cards is a long tab-through for keyboard/screen-reader users */
.skip{{position:absolute;left:-9999px;top:0;z-index:60;background:var(--ink);color:#fff;padding:11px 18px;border-radius:0 0 8px 0;text-decoration:none;font-weight:700;font-size:14px}}
.skip:focus{{left:0}}
/* print / PDF: many readers forward this as a PDF to clients */
@media print{{
  body{{background:#fff}}
  .topbar,.langtog,#share,.heroacts,#sharebox,#toast,.navlinks{{display:none!important}}
  .story{{break-inside:avoid;page-break-inside:avoid;box-shadow:none;border:1px solid #ccc}}
  .cat-head{{break-after:avoid;page-break-after:avoid;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .thesis,.take,.src,.signal{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .stories{{grid-template-columns:1fr}}
  a[href^="http"]::after{{content:" (" attr(href) ")";font-size:9.5px;color:#666;word-break:break-all}}
  .readsrc::after{{content:none}}
}}
</style>
</head>
<body>
<a class="skip" href="#main">{bi("跳至內容", "Skip to content")}</a>
<div class="topbar"><div class="wrap"><div class="mast">
  <div class="brand">{bi(SITE_TITLE, SITE_TITLE_EN)}<small>{html.escape(SITE_TAGLINE)}</small></div>
  <div class="mast-r">
    <div class="navlinks">{nav}<a class="pill" href="archive/">{bi("歷史存檔", "Archive")}</a></div>
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
    <span>{bi(BYLINE_ROLE, BYLINE_ROLE_EN)}</span>{('<span class="dot">·</span>' + _weekly_link) if _weekly_link else ''}
  </div>
  <div class="heroacts">
    <button id="share">{bi("分享給同事", "Share")}</button>
    <a class="archlink" href="archive/">{bi("📚 歷史存檔", "📚 Archive")}</a>
  </div>
  <div id="sharebox"><span>{bi("長按或全選以複製：", "Long-press / select all to copy:")}</span><input type="text" readonly value="{html.escape(SITE_URL)}"></div>
  <div class="legend"><span class="signal act">{bi("可即用", "Ready to use")}</span>{bi("今天可用／節省工時", "try today / save time")}　<span class="signal watch">{bi("要留意", "Worth watching")}</span>{bi("平台或趨勢變動", "platform / trend shift")}　<span class="signal impact">{bi("影響生意", "Business impact")}</span>{bi("代理商生態／客戶／法規", "agency / client / compliance")}</div>
  <div class="stats">{stats}</div>
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
</script>
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

print(f"OK index.html total={total} sections=" + ",".join(f"{s}:{len(groups[s])}" for s in data["sections"])
      + (f"  ⚠ {_warn} warning(s) — 見上面 stderr" if _warn else "  (0 warnings)"))
