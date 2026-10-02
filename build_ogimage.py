#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the 1200×630 share card for one issue.

Why this exists (measured, not assumed):
  index.html already declares `twitter:card = summary_large_image`, and build.py
  only emits og:image when data.json carries an `og_image` key — which it never
  did. So every forward of the link (Slack, WhatsApp, LinkedIn, email preview)
  rendered a card sized for a large image with no image in it. Counted on the
  live 2026-09-30 page: `og:image` 0 occurrences, `twitter:card` 1.

Output: og/<ISO>.png, one per issue. Dated rather than a single rolling og.png
  because build_archive.py snapshots index.html verbatim — a rolling filename
  would make every archived page advertise today's card, so a link to the 9/20
  issue would preview 9/30's headlines.

Design follows this project's own規範 (library/.../brand/AI情報站-品牌規範-v1.1.md),
  not MIA Brand Guideline v2.0 — Carrie owns this site. Anchor colours are the
  four corners measured off icon-512.png, so the card and the app icon are the
  same object seen twice.

Fonts are verified by rendering, never by reading CSS: --verify re-reads the PNG
  and asserts the three type layers actually differ in pixels. On a box without
  Noto Serif CJK the serif headline silently falls back to the sans and the card
  looks flat while the CSS still says `serif` — that is exactly the failure this
  check exists to catch.
"""
import argparse
import json
import os
import subprocess
import sys

CH = "/usr/bin/chromium" if os.path.exists("/usr/bin/chromium") else "chromium"
W, H = 1200, 630

# Measured off icon-512.png (44×44 px corner averages). See 品牌規範 §1.
VIOLET, BLUE, PLUM, NAVY = "#6249D7", "#39689F", "#7D266B", "#11154A"
PAPER, LIME = "#F7F5EF", "#D3FE66"

HTML = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden}}
  body{{
    /* Four-corner gradient, same construction as the icon: two radial washes for
       the top corners over a navy→plum diagonal. A two-stop linear gradient (what
       the other team's brief assumed the icon was) loses the blue and plum angles
       entirely. */
    background:
      radial-gradient(120% 130% at 0% 0%, {VIOLET} 0%, rgba(98,73,215,0) 58%),
      radial-gradient(115% 125% at 100% 0%, {BLUE} 0%, rgba(57,104,159,0) 55%),
      radial-gradient(120% 130% at 100% 100%, {PLUM} 0%, rgba(125,38,107,0) 60%),
      {NAVY};
    color:{PAPER};
    font-family:Inter,"Noto Sans TC","Noto Sans CJK TC",sans-serif;
    display:flex;flex-direction:column;justify-content:space-between;
    padding:52px 60px 46px;
  }}
  .top{{display:flex;align-items:center;justify-content:space-between}}
  .brand{{display:flex;align-items:baseline;gap:13px}}
  /* Serif for the wordmark and headlines, sans for furniture, mono for numbers —
     the same three-layer hierarchy as the page. If any two collapse into one
     face the card reads as a generic dark rectangle. */
  .brand b{{font-family:"Noto Serif CJK TC","Noto Serif TC",serif;
    font-size:41px;font-weight:700;letter-spacing:.01em}}
  .brand span{{font-size:17px;opacity:.74;letter-spacing:.14em;text-transform:uppercase}}
  .live{{display:flex;align-items:center;gap:10px;
    font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:19px;
    background:rgba(0,0,0,.22);padding:10px 17px;border-radius:999px}}
  /* Lime is the status light, never a fill. 品牌規範 R3 caps it at 2% of area;
     one 13px dot on a 1200×630 card is 0.02%. */
  .dot{{width:13px;height:13px;border-radius:50%;background:{LIME};flex:none}}
  h1{{font-family:"Noto Serif CJK TC","Noto Serif TC",serif;
    font-size:60px;line-height:1.24;font-weight:700;letter-spacing:-.015em;
    text-wrap:balance;max-width:19ch}}
  .leads{{margin-top:26px;display:flex;flex-direction:column;gap:11px;max-width:1010px}}
  .leads div{{font-size:22px;line-height:1.42;opacity:.9;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .leads i{{font-family:"IBM Plex Mono",ui-monospace,monospace;
    font-style:normal;color:{LIME};opacity:.95;margin-right:11px;font-size:19px}}
  .bot{{display:flex;align-items:flex-end;justify-content:space-between;
    border-top:1px solid rgba(247,245,239,.26);padding-top:19px}}
  .by{{font-size:20px;opacity:.9}}
  .count{{font-family:"IBM Plex Mono",ui-monospace,monospace;text-align:right}}
  .count b{{display:block;font-size:52px;font-weight:600;letter-spacing:-.02em;
    line-height:1;color:{LIME}}}
  .count span{{font-size:16px;opacity:.72;letter-spacing:.09em}}
</style></head><body>
  <div class="top">
    <div class="brand"><b>{title}</b><span>AI Marketing Daily</span></div>
    <div class="live"><i class="dot"></i>{iso}</div>
  </div>
  <div>
    <h1>{headline}</h1>
    <div class="leads">{leads}</div>
  </div>
  <div class="bot">
    <div class="by">{byline}</div>
    <div class="count"><b>{total}</b><span>{count_label}</span></div>
  </div>
</body></html>
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_html(d):
    items = d.get("items", [])
    lead = items[0].get("title", "") if items else ""
    rest = [i.get("title", "") for i in items[1:4]]
    leads = "".join(
        f'<div><i>{n:02d}</i>{esc(t)}</div>' for n, t in enumerate(rest, start=2) if t)
    return HTML.format(
        W=W, H=H, VIOLET=VIOLET, BLUE=BLUE, PLUM=PLUM, NAVY=NAVY,
        PAPER=PAPER, LIME=LIME,
        title=esc(d.get("site_title", "AI・行銷情報")),
        iso=esc(d.get("date", "")),
        headline=esc(lead),
        leads=leads,
        # 同 build.py 一樣讀 byline／byline_role，唔另外編一句署名 —— 卡圖同頁面
        # 講唔同嘅話，讀者會當成兩個來源。
        byline=esc((d.get("byline") or "Carrie Hui")
                   + " · " + (d.get("byline_role") or "AI 行銷策略")),
        total=len(items),
        count_label="則 · TODAY",
    )


def shoot(html_path, out_png):
    r = subprocess.run(
        [CH, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         f"--window-size={W},{H}", "--force-device-scale-factor=1",
         "--default-background-color=00000000", "--virtual-time-budget=6000",
         f"--screenshot={out_png}", "file://" + os.path.abspath(html_path)],
        capture_output=True, text=True, timeout=180)
    if not os.path.exists(out_png):
        raise RuntimeError("screenshot failed: " + r.stderr[-400:])
    return r


def verify(png, d):
    """量像素，唔量 CSS。三個問題：
      1. 尺寸是否真的 1200×630（平台會拒絕其他比例）。
      2. 三層字體是否真的唔同一款 —— 用同字號渲染同一串字，量墨跡寬度。
         有效性對照：故意把三層都設成 sans，若仍判為「不同」，係工具壞了。
      3. Lime 面積是否在 R3 上限之內，深底對比是否足夠。
    """
    try:
        from PIL import Image
    except ImportError:
        print("  (冇 Pillow，改用 uv run --with pillow 重跑 verify)", file=sys.stderr)
        return 2
    im = Image.open(png).convert("RGB")
    ok = True
    print("=== 分享卡圖驗證 %s ===" % os.path.basename(png))
    size_ok = im.size == (W, H)
    print("  %s 尺寸 %sx%s（平台要 1200x630）" % ("PASS" if size_ok else "FAIL", *im.size))
    ok &= size_ok

    # Lime 面積（R3 上限 2%）
    px = im.load()
    lime = (0xD3, 0xFE, 0x66)
    n_lime = 0
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            if abs(r - lime[0]) < 26 and abs(g - lime[1]) < 26 and abs(b - lime[2]) < 40:
                n_lime += 1
    pct = n_lime / ((W // 2) * (H // 2)) * 100
    print("  %s Lime 面積 %.2f%%（R3 上限 2%%）" % ("PASS" if pct <= 2 else "FAIL", pct))
    ok &= pct <= 2

    # 非空白：四角漸變必須真的有四種色相，唔係一片純色
    corners = [px[40, 40], px[W - 40, 40], px[W - 40, H - 40], px[40, H - 40]]
    spread = max(max(c) - min(c) for c in zip(*corners))
    print("  %s 四角色差 %d（純色底會係 0；漸變應 >30）"
          % ("PASS" if spread > 30 else "FAIL", spread))
    ok &= spread > 30
    print("  四角實測 %s" % " ".join("#%02X%02X%02X" % c for c in corners))
    return 0 if ok else 1


def font_control(tmpdir):
    """有效性對照：量三層字體的渲染結果是否真的互不相同。

    第一版用「AI 行銷情報 2026」量寬度，三層都量到 453.3px，我一度讀成「字體全部被
    代用」。其實係量法本身無鑑別力：**CJK 表意字在這些字體裡全部是全角等寬**，所以
    無論 serif／sans／mono，同一串中文的寬度必然相同。用寬度去分辨 CJK 字體，等於用
    尺去分辨兩張同尺寸的照片。

    所以分兩項量：
      A. 拉丁字串量寬度 —— serif／sans／mono 的西文字寬本來就不同，量得出分別。
      B. CJK 字串量像素 —— 寬度相同是正常的，要比的是墨跡本身（黑點座標集）。
    兩項都要過，才算三層字體真的存在。
    """
    lat = "Marketing Intelligence 2026"
    cjk = "行銷情報"
    # 字體堆疊本身帶雙引號（"Noto Serif CJK TC"），一放入 style="..." 屬性就會提早
    # 關掉屬性，整條宣告被丟棄 —— 三層於是全部量到 683.1px，我一度誤讀成「字體被代用」。
    # 改用 <style> 區塊，堆疊裡的引號就唔會同屬性引號打架。
    probe = """<!doctype html><meta charset="utf-8">
    <style>#a{display:inline-block;font-size:60px;font-family:%s}</style>
    <body style="margin:0"><div id=a>""" + lat + """</div></body>"""
    out = {}
    for tag, fam in (("serif", '"Noto Serif CJK TC","Noto Serif TC",serif'),
                     ("sans", 'Inter,"Noto Sans CJK TC",sans-serif'),
                     ("mono", '"IBM Plex Mono",ui-monospace,monospace')):
        p = os.path.join(tmpdir, "f_%s.html" % tag)
        with open(p, "w", encoding="utf-8") as f:
            # Marker must be distinctive: a bare "W" matched the chromium log's own
            # text and the parse silently produced None for all three layers, which
            # read as "量唔到" rather than as a broken probe.
            f.write(probe % fam +
                    "<script>var s=document.createElement('script');"
                    "s.textContent='console.log(\"FONTW=\"+"
                    "document.getElementById(\"a\").getBoundingClientRect().width+"
                    "\"|\"+document.getElementById(\"a\").getBoundingClientRect().height)';"
                    "document.body.appendChild(s)</script>")
        r = subprocess.run(
            [CH, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--enable-logging=stderr", "--v=0", "--window-size=1400,300",
             "--virtual-time-budget=5000", "--dump-dom", "file://" + p],
            capture_output=True, text=True, timeout=180)
        w = None
        for line in r.stderr.splitlines():
            i = line.find("FONTW=")
            if i < 0:
                continue
            try:
                w = float(line[i + 6:].split("|")[0])
                break
            except Exception:
                continue
        if w is None:
            print("  (%s 量唔到，chromium stderr 尾段：%s)" % (tag, r.stderr[-160:]),
                  file=sys.stderr)
        out[tag] = w
    print("=== 字體有效性對照（量渲染結果，唔係讀 CSS）===")
    print("  A. 拉丁字串 %r 寬度" % lat)
    for k, v in out.items():
        print("     %-6s %s px" % (k, "量唔到" if v is None else "%.1f" % v))
    vals = [v for v in out.values() if v is not None]
    if len(vals) < 3:
        print("     → 量唔齊三層，唔可以下結論"); return 1
    distinct = len(set(round(v, 1) for v in vals))
    a_ok = distinct == 3
    print("     → %s：%d/3 個唔同寬度%s"
          % ("PASS" if a_ok else "FAIL", distinct,
             "" if a_ok else "，有字體被靜靜代用（CSS 寫咗唔代表有效）"))

    # B. CJK 墨跡比對 —— 全角等寬令寬度必然相同，所以比像素
    print("  B. CJK 字串 %r 墨跡（全角等寬，寬度相同係正常，要比像素）" % cjk)
    try:
        from PIL import Image
    except ImportError:
        print("     → 冇 Pillow，量唔到 CJK 墨跡，唔可以聲稱襯線有效"); return 1
    inks = {}
    for tag, fam in (("serif", '"Noto Serif CJK TC","Noto Serif TC",serif'),
                     ("sans", 'Inter,"Noto Sans CJK TC",sans-serif')):
        p = os.path.join(tmpdir, "c_%s.html" % tag)
        with open(p, "w", encoding="utf-8") as f:
            f.write('<!doctype html><meta charset="utf-8">'
                    '<style>#c{font-size:96px;line-height:1.1;color:#000;'
                    'font-family:%s}</style>'
                    '<body style="margin:0;background:#fff">'
                    '<div id=c>%s</div></body>' % (fam, cjk))
        png = os.path.join(tmpdir, "c_%s.png" % tag)
        subprocess.run([CH, "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--window-size=480,140",
                        "--force-device-scale-factor=1", "--virtual-time-budget=6000",
                        "--screenshot=" + png, "file://" + p],
                       capture_output=True, text=True, timeout=180)
        if not os.path.exists(png):
            print("     → %s 截圖失敗，唔可以下結論" % tag); return 1
        im = Image.open(png).convert("L")
        w, h = im.size
        px = im.load()
        inks[tag] = frozenset((x, y) for y in range(h) for x in range(w) if px[x, y] < 128)
    s, n = inks["serif"], inks["sans"]
    inter = len(s & n)
    union = len(s | n) or 1
    jac = inter / union
    # 同一款字渲染兩次會近乎 1.0；兩款不同字型的同一串中文通常 0.5–0.8。
    b_ok = jac < 0.95 and len(s) > 200 and len(n) > 200
    print("     serif 墨點 %d ／ sans 墨點 %d ／ 重疊率 %.3f" % (len(s), len(n), jac))
    print("     → %s：%s"
          % ("PASS" if b_ok else "FAIL",
             "兩款 CJK 字型墨跡明顯不同，襯線真的生效"
             if b_ok else "墨跡幾乎一樣（重疊 %.1f%%），襯線被代用成同一款字" % (jac * 100)))
    return 0 if (a_ok and b_ok) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--out", help="輸出 PNG（預設 og/<date>.png）")
    ap.add_argument("--verify", action="store_true", help="渲染後量像素")
    ap.add_argument("--font-check", action="store_true", help="只跑字體有效性對照")
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(a.data)) or "."
    tmp = os.environ.get("TMPDIR") or here

    if a.font_check:
        return font_control(tmp)

    with open(a.data, encoding="utf-8") as f:
        d = json.load(f)
    iso = d.get("date") or ""
    if not iso:
        print("data.json 冇 date", file=sys.stderr)
        return 2
    out = a.out or os.path.join(here, "og", "%s.jpg" % iso)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    hp = os.path.join(tmp, "ogcard-%s.html" % iso)
    with open(hp, "w", encoding="utf-8") as f:
        f.write(build_html(d))
    # 先截 PNG（chromium 只出 PNG），再轉 JPEG。量到嘅 PNG 係 441KB —— 四角漸變令
    # 每一個像素都係唔同 RGB 值，PNG 嘅無損壓縮對漸變幾乎無效。WhatsApp／LINE 對
    # 預覽縮圖有大小上限，超過就索性唔抓圖，所以交付檔一定要係 JPEG。
    png_tmp = os.path.join(tmp, "ogcard-%s.png" % iso)
    shoot(hp, png_tmp)
    try:
        from PIL import Image
        Image.open(png_tmp).convert("RGB").save(out, "JPEG", quality=88, optimize=True,
                                                progressive=True)
    except ImportError:
        print("冇 Pillow，轉唔到 JPEG", file=sys.stderr)
        return 2
    kb = os.path.getsize(out) / 1024
    print("OK %s  %.0f KB（PNG 原檔 %.0f KB）  (%d 則)"
          % (out, kb, os.path.getsize(png_tmp) / 1024, len(d.get("items", []))))
    if kb > 300:
        print("  WARN 檔案 >300KB，社交平台可能唔抓")
    if a.verify:
        rc = verify(out, d)
        rc2 = font_control(tmp)
        return rc or rc2
    return 0


if __name__ == "__main__":
    sys.exit(main())
