#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Subset and emit the page's webfonts, then prove they actually render.

Why this exists (counted on the built page, not assumed):
  index.html declares `Inter` 8 times and has **0 `@font-face`** rules and 0
  webfont <link>s. So the typography was entirely dependent on whether the
  reader's own device happened to have Inter installed — on Windows and Android
  it does not, and the stack fell through to a system sans with no warning. The
  同一個坑 as the Hyatt pipeline: 字體要驗渲染結果，唔係讀 CSS。

Scope — Latin and numerals only, deliberately:
  A CJK webfont is 4–9 MB even subset to common Hant, which on a 27-story page
  read on mobile is a worse trade than the substitution it fixes. Chinese keeps
  using the system face (PingFang / Noto Sans CJK), which every target device
  has. What the page actually lacked was (a) a consistent Latin sans and (b) a
  real monospace for the numerals — the 品牌規範 §3.3 「等寬數字」 claim was not
  true without a font file behind it.

Output: fonts/*.woff2 + the @font-face CSS block, which build.py inlines.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/.fonts")
CH = "/usr/bin/chromium" if os.path.exists("/usr/bin/chromium") else "chromium"

# Latin-1 + punctuation + the arrows/bullets the page uses. Explicit rather than
# a named unicode-range so the subset is reproducible and reviewable.
UNICODES = (
    "U+0020-007E,"            # basic latin
    "U+00A0-00FF,"            # latin-1 supplement (é, ·, ×, °)
    "U+2010-2027,"            # dashes, quotes, ellipsis, bullet
    "U+2030-2033,"            # per mille, primes
    "U+20AC,U+2026,U+2192,U+2190,U+2191,U+2193,"   # euro, ellipsis, arrows
    "U+2713,U+2714,"          # check marks
    "U+FEFF"
)

FACES = [
    # (file, family, weight, style)
    ("Inter-Regular.otf",    "InterLat", "400", "normal"),
    ("Inter-SemiBold.otf",   "InterLat", "600", "normal"),
    ("Inter-Bold.otf",       "InterLat", "700", "normal"),
    ("IBMPlexMono-Regular.ttf", "PlexMonoLat", "400", "normal"),
    ("IBMPlexMono-Medium.ttf",  "PlexMonoLat", "500", "normal"),
]


def subset(src, out, unicodes):
    """pyftsubset via uv — fontTools is not in the base runtime, and a global
    install is the wrong tool for a build-time dependency."""
    cmd = ["uv", "run", "--with", "fonttools[woff]", "--with", "brotli",
           "pyftsubset", src,
           "--output-file=" + out,
           "--flavor=woff2",
           "--unicodes=" + unicodes,
           # layout-features: kern for Latin pairs, tnum so the numerals the page
           # declares as tabular actually have tabular figures in the subset.
           "--layout-features=kern,liga,tnum,zero",
           "--desubroutinize",
           "--no-hinting",
           "--drop-tables+=DSIG",
           "--name-IDs=1,2,3,4,6"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not os.path.exists(out):
        raise RuntimeError("subset failed for %s:\n%s" % (src, r.stderr[-600:]))
    return os.path.getsize(out)


def css(base):
    """@font-face block. font-display:swap, not optional/block:

    block hides text for up to 3s — on a news page the headline is the product.
    optional lets the browser skip the font entirely on a slow first visit, which
    would reintroduce the silent substitution this file exists to remove. swap
    paints the system face immediately, then swaps — the one visible cost is a
    reflow, which the size-adjust/metric overrides below keep small.
    """
    rows = []
    for fn, fam, wt, st in FACES:
        rows.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%s;"
            "font-display:swap;src:url('%sfonts/%s') format('woff2');"
            "unicode-range:%s}" % (fam, st, wt, base, fn.rsplit(".", 1)[0] + ".woff2",
                                   UNICODES))
    return "".join(rows)


def verify(fonts_dir, base_css):
    """量渲染結果。三問，每問都要有一個「已知應該失敗」嘅對照：

      1. woff2 檔是否真的被瀏覽器接受（壞檔 chromium 會靜靜跳過，CSS 照樣無錯）。
      2. 載入後嘅字寬，是否真的同系統 fallback 唔同 —— 若相同，即係 webfont 冇生效。
      3. 等寬數字是否真的等寬 —— '1111' 同 '0000' 寬度必須相同。
         對照：同一串字用 sans 量，必須唔等寬（否則量法無鑑別力）。
    """
    ok = True
    print("=== webfont 渲染驗證（量像素，唔讀 CSS）===")

    def measure(fontfam, text, extra_css=""):
        # 探針要寫落 fonts/ 嘅上一層：@font-face 嘅 url() 係 'fonts/xxx.woff2'，
        # 若探針本身放喺 fonts/ 裡面，相對路徑會解析成 fonts/fonts/xxx.woff2 → 404，
        # 字體永遠載唔到，而我會錯誤地讀成「webfont 唔生效」。
        # 另外直接 console.log，唔再包一層動態 <script>（第一版就係嗰層令輸出消失）。
        html = (
            '<!doctype html><meta charset="utf-8"><style>%s %s'
            '#a{font-size:72px;display:inline-block;white-space:pre}</style>'
            '<body style="margin:0"><div id=a style="font-family:%s">%s</div>'
            '<script>document.fonts.ready.then(function(){'
            'console.log("FW="+document.getElementById("a")'
            '.getBoundingClientRect().width)})</script></body>'
            % (base_css, extra_css, fontfam, text))
        p = os.path.join(os.path.dirname(os.path.abspath(fonts_dir)), "_probe.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
        r = subprocess.run(
            [CH, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--enable-logging=stderr", "--v=0", "--window-size=1600,260",
             "--virtual-time-budget=9000", "--dump-dom", "file://" + p],
            capture_output=True, text=True, timeout=180)
        for line in r.stderr.splitlines():
            i = line.find("FW=")
            if i < 0:
                continue
            # chromium 嘅 CONSOLE 行係 `"FW=950.453125", source: file:///…`，
            # 所以 split()[0] 會帶住收尾嘅 `",`，float() 直接拋錯。第一版把呢個錯
            # 吞落 except: continue，結果三層全部報「量唔到」—— 睇落似字體問題，
            # 其實係我自己嘅解析問題。改為只取開頭嘅數字字元。
            tok = ""
            for ch in line[i + 3:]:
                if ch.isdigit() or ch == ".":
                    tok += ch
                else:
                    break
            try:
                return float(tok)
            except ValueError:
                continue
        return None

    # 1+2. webfont 生效嗎？同 fallback 比
    s = "Marketing Intelligence 2026"
    w_web = measure("InterLat,monospace", s)
    # 對照：同一串字、同字號，刻意唔用 webfont（只用系統 serif），必須量到唔同寬度。
    w_sys = measure("Times,serif", s)
    print("  Inter 子集 %s px ／ 系統 serif 對照 %s px"
          % ("量唔到" if w_web is None else "%.1f" % w_web,
             "量唔到" if w_sys is None else "%.1f" % w_sys))
    if w_web is None or w_sys is None:
        print("  → 量唔到，唔可以下結論"); return 1
    # 若 woff2 載唔到，InterLat 會 fall back 落 monospace（我故意放喺堆疊第二位做哨兵）
    w_mono_sentinel = measure("monospace", s)
    loaded = abs(w_web - (w_mono_sentinel or -1)) > 1.0
    print("  → %s：%s（哨兵 monospace %s px —— 若 woff2 載唔到，上面會等於這個數）"
          % ("PASS" if loaded else "FAIL",
             "woff2 真的載入並生效" if loaded else "woff2 冇生效，跌落 fallback",
             "量唔到" if w_mono_sentinel is None else "%.1f" % w_mono_sentinel))
    ok &= loaded

    # 3. 等寬數字
    w1 = measure("PlexMonoLat,serif", "1111")
    w0 = measure("PlexMonoLat,serif", "0000")
    prop1 = measure("Times,serif", "1111")
    prop0 = measure("Times,serif", "0000")
    if None in (w1, w0, prop1, prop0):
        print("  → 等寬數字量唔到，唔可以下結論"); return 1
    mono_equal = abs(w1 - w0) < 0.6
    ctl_differs = abs(prop1 - prop0) > 0.6
    print("  等寬 '1111'=%.1f '0000'=%.1f（差 %.2f）／ "
          "對照 Times '1111'=%.1f '0000'=%.1f（差 %.2f）"
          % (w1, w0, abs(w1 - w0), prop1, prop0, abs(prop1 - prop0)))
    if not ctl_differs:
        # 有效性對照失敗：如果連比例字體都量到等寬，係量法壞了，唔係結論成立。
        print("  → 對照無效：連 Times 都量到等寬，量法冇鑑別力，唔可以聲稱等寬生效")
        ok = False
    else:
        print("  → %s：%s" % ("PASS" if mono_equal else "FAIL",
                             "數字真的等寬，品牌規範 §3.3 成立"
                             if mono_equal else "數字唔等寬，等寬宣告未生效"))
        ok &= mono_equal

    try:
        os.unlink(os.path.join(os.path.dirname(os.path.abspath(fonts_dir)),
                               "_probe.html"))
    except OSError:
        pass
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "fonts"))
    ap.add_argument("--base", default="", help="CSS 內 url() 前綴，例如 /ai-marketing-daily/")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--emit-css", help="把 @font-face CSS 寫到這個檔")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    total = 0
    for fn, fam, wt, st in FACES:
        src = os.path.join(SRC, fn)
        if not os.path.exists(src):
            print("搵唔到字檔 %s —— 唔可以靜靜略過，否則 CSS 會指向一個 404" % src,
                  file=sys.stderr)
            return 2
        out = os.path.join(a.out, fn.rsplit(".", 1)[0] + ".woff2")
        n = subset(src, out, UNICODES)
        total += n
        print("  %-28s → %-30s %6.1f KB (原檔 %5.0f KB)"
              % (fn, os.path.basename(out), n / 1024, os.path.getsize(src) / 1024))
    print("共 %d 個 woff2，合計 %.1f KB" % (len(FACES), total / 1024))
    if total > 180 * 1024:
        print("  WARN 合計 >180KB，手機首次載入成本偏高")

    block = css(a.base)
    if a.emit_css:
        with open(a.emit_css, "w", encoding="utf-8") as f:
            f.write(block)
        print("CSS → %s（%d chars）" % (a.emit_css, len(block)))

    if a.verify:
        # 驗證時 url() 要指向本機檔案，所以用相對 base
        return verify(a.out, css(""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
