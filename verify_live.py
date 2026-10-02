#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""發佈後驗證關卡 —— routine 第 6 步呼叫呢個 script，唔好再靠文字自律。

背景（為何要有呢個檔）：
  2026-08-18、08-24、08-25、08-26、09-06 五次 run 嘅 status 係 success，
  但 resultSummary 內文自己寫「未能完成」，線上亦真係冇出版（archive/2026-08-18.html
  至今 404）。原因係舊第 6 步嘅驗證條件係「首頁 HTTP 200」——而昨日版本仍然掛住，
  停更當日照樣 200。恆真條件冇鑑別力，於是 run 用「成功發出一個 Slack 道歉」
  當成功收尾，網站靜靜停更而冇人知。

設計原則：
  每一項檢查都必須「今日冇出版時會 fail」。純 200、純「檔案存在」一律不算。
  跑 --self-test 會用故意造壞嘅輸入證明每項檢查真的會 fail（有效性對照）。

退出碼：
  0 = 全部通過，可以行第 7 步發快訊
  1 = 有檢查不通過 → routine 必須以失敗結束並發失敗通知，唔准當 success
  2 = 腳本自身出錯（參數錯／網絡完全不通），同樣唔准當 success
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://carriehw.github.io/ai-marketing-daily"
UA = "mia-aidaily-verify/1.0"


def fetch(url, tries=3, delay=4):
    """拎線上檔案。一定要 cache-buster + no-cache，否則會驗到 CDN 舊版快取。"""
    last = None
    for n in range(tries):
        bust = "%scb=%d" % ("&" if "?" in url else "?", int(time.time()) + n)
        req = urllib.request.Request(
            url + bust,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.getcode(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception as e:  # 網絡抖動先重試，唔好一次就當停更
            last = e
            if n < tries - 1:
                time.sleep(delay)
    raise RuntimeError("fetch failed: %s (%s)" % (url, last))


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, ok, name, detail):
        self.rows.append((bool(ok), name, detail))
        return bool(ok)

    @property
    def failed(self):
        return [r for r in self.rows if not r[0]]

    def report(self):
        for ok, name, detail in self.rows:
            print("  %s %-34s %s" % ("PASS" if ok else "FAIL", name, detail))


def verify(today, local_dir, checks, fetcher=fetch):
    """today = 'YYYY-MM-DD'（當日期號）。local_dir = 剛 build 出嘅檔案所在。"""
    lp = lambda n: os.path.join(local_dir, n)

    # --- 1. 首頁位元組必須同本機剛 build 出嘅一模一樣 -------------------
    # 停更當日線上係昨日版本，md5 唔會等於今日本機版本 → 呢項會 fail。
    code, remote = fetcher(BASE + "/index.html")
    with open(lp("index.html"), "rb") as f:
        local = f.read()
    rmd5, lmd5 = hashlib.md5(remote).hexdigest(), hashlib.md5(local).hexdigest()
    checks.add(
        code == 200 and rmd5 == lmd5,
        "首頁位元組相同",
        "HTTP %s 線上 %d bytes md5 %s / 本機 %d bytes md5 %s"
        % (code, len(remote), rmd5[:8], len(local), lmd5[:8]),
    )

    # --- 2. 線上首頁必須帶今日日期 ---------------------------------------
    # 獨立於第 1 項：即使有人手動傳錯檔，日期對唔上一樣攔得住。
    txt = remote.decode("utf-8", "replace")
    n_iso = txt.count(today)
    m_title = re.search(r"<title>([^<]*)</title>", txt)
    title = m_title.group(1) if m_title else ""
    checks.add(
        n_iso > 0 and today in title,
        "首頁日期係今日",
        "ISO 日期出現 %d 次；title=%r" % (n_iso, title[:60]),
    )

    # --- 3. 今日存檔頁必須真的上線（HTTP 200 且帶今日日期）--------------
    # 9/26、9/27 停更 → archive/2026-09-26.html 至今 404，呢項會攔住。
    acode, apage = fetcher("%s/archive/%s.html" % (BASE, today))
    atxt = apage.decode("utf-8", "replace")
    checks.add(
        acode == 200 and today in atxt,
        "今日存檔頁已上線",
        "archive/%s.html HTTP %s，%d bytes，帶日期=%s"
        % (today, acode, len(apage), today in atxt),
    )

    # --- 4. manifest 必須包含今日，而且期數唔准少過線上舊版 --------------
    # build_archive.py 係 append；本機缺 snapshot 會靜靜抹走歷史。
    mcode, mraw = fetcher(BASE + "/archive/manifest.json")
    try:
        rem_list = json.loads(mraw.decode("utf-8"))
    except Exception:
        rem_list = []
    with open(lp("archive/manifest.json"), "rb") as f:
        loc_list = json.loads(f.read().decode("utf-8"))
    rdates = {e.get("date") for e in rem_list if isinstance(e, dict)}
    ldates = {e.get("date") for e in loc_list if isinstance(e, dict)}
    lost = sorted(d for d in ldates - rdates if d)  # 本機有、線上冇 = 未傳上去
    checks.add(
        mcode == 200 and today in rdates and len(rdates) >= len(ldates) and not lost,
        "存檔目錄含今日且冇少期",
        "線上 %d 期 / 本機 %d 期；含今日=%s；未上傳=%s"
        % (len(rdates), len(ldates), today in rdates, lost or "無"),
    )

    # --- 5. 存檔目錄頁列出今日 -------------------------------------------
    icode, ipage = fetcher(BASE + "/archive/")
    itxt = ipage.decode("utf-8", "replace")
    checks.add(
        icode == 200 and today in itxt,
        "存檔目錄頁列出今日",
        "archive/ HTTP %s，帶今日日期=%s" % (icode, today in itxt),
    )

    # --- 6. 內容量健康度：卡片數要合理 -----------------------------------
    # 防「出到一個空殼頁但位元組對得上」嘅情況。
    n_story = len(re.findall(r'class="story\b', txt))
    checks.add(n_story >= 8, "首頁卡片數合理", "story 卡片 %d 張（下限 8）" % n_story)

    # --- 7. 頁面引用嘅每一個 woff2 都必須線上真的取得到 -------------------
    # 要攔嘅唔係「有冇寫 @font-face」——寫咗一樣可以指向 404。字體 404 嘅失敗係
    # 完全靜默嘅：頁面照樣出，只係默默跌落系統字體，而我哋會以為字體已經生效。
    # 所以逐個 url() 真去 fetch，並且驗內容真係 woff2（magic bytes 'wOF2'），
    # 唔係 GitHub Pages 嘅 404 HTML 頁（佢都係 200 嗎？唔係，但驗 magic 更穩）。
    refs = sorted(set(re.findall(r"url\('([^']*\.woff2)'\)", txt)))
    if refs:
        bad = []
        for u in refs:
            fu = u if u.startswith("http") else (
                BASE.rsplit("/", 1)[0] + u if u.startswith("/") else BASE + "/" + u)
            fc, fb = fetcher(fu)
            if fc != 200 or not fb.startswith(b"wOF2"):
                bad.append("%s(HTTP %s,%d bytes)" % (u.rsplit("/", 1)[-1], fc, len(fb)))
        checks.add(not bad, "引用嘅字體檔都取得到",
                   "共 %d 個 woff2，失敗：%s" % (len(refs), ", ".join(bad) or "無"))
    else:
        # 冇引用 = FAIL，唔係「用系統字體都可以」。
        #
        # 由 2026-10-02 起網站已經內嵌字體，所以 0 個引用唔再係一個選擇，而係退化。
        # 呢個分支正係排程最易中嘅坑：build.py 嘅字體區塊設計成「fonts/ 唔齊就靜默
        # 略過」（好過指向 404），而排程每朝喺 fresh session 入面要自己 GET 返
        # build_fonts.py 同 fonts/*.woff2。若漏咗攞，頁面照樣出、照樣部署成功、
        # 位元組亦對得上，只係字體默默消失 —— 若呢度判 PASS，就冇任何一道關卡會
        # 發現，直到有人用 Windows 打開覺得「today 個版面有啲唔同」。
        checks.add(False, "引用嘅字體檔都取得到",
                   "頁面 0 個 woff2 引用 —— 字體已退化成系統字；"
                   "排程要先 GET build_fonts.py 同 fonts/*.woff2 才跑 build.py")

    # --- 8. og:image 必須線上真的取得到，而且係圖 -------------------------
    # 分享卡最容易「本機有、冇傳上去」：本機 og/ 存在，Contents API 漏傳一個目錄，
    # 線上就空白卡。而空白卡係睇唔出嘅 —— 要等有人分享到 Slack 才發現。
    m_og = re.search(r'property="og:image" content="([^"]+)"', txt)
    if m_og:
        ou = m_og.group(1)
        oc, ob = fetcher(ou)
        is_img = ob[:3] == b"\xff\xd8\xff" or ob[:8] == b"\x89PNG\r\n\x1a\n"
        checks.add(oc == 200 and is_img and len(ob) > 4096,
                   "分享卡圖線上取得到",
                   "%s HTTP %s，%d bytes，係圖=%s"
                   % (ou.rsplit("/", 1)[-1], oc, len(ob), is_img))
    else:
        checks.add(False, "分享卡圖線上取得到", "頁面冇 og:image —— 分享到 Slack 會冇卡圖")

    # --- 9. 統計器：首頁同存檔目錄頁都要有，而回報端點要真係收 ------------
    # 呢項同第 7 項同一個病理：失敗完全靜默。漏咗 analytics 鍵、或者端點打錯字,
    # 頁面照出、部署照成功、位元組照對，只係由嗰日起數字變成零 —— 而零會被讀成
    # 「冇人睇」，唔係「冇接通」。所以唔只檢查「有冇 script 字樣」，要同時：
    #   a. 兩個頁面都有 data-goatcounter（存檔目錄頁係另一個 generator 出，
    #      兩次都試過獨立漏咗佢）；
    #   b. 兩個頁面指住同一個端點（若 build.py 同 build_archive.py 嘅預設帳號
    #      分叉，存檔會默默報去另一個帳號，總數永遠加唔埋）；
    #   c. 真去 fetch 嗰個端點嘅 ?test=1，證明帳號存在 —— test=1 唔會記一筆，
    #      所以驗證本身唔會刷花數字。有效性對照：唔存在嘅帳號回 400（實測
    #      2026-10-02），所以 200 真係認得出帳號，唔係恆真。
    # 但唔可以變成「關唔得」。若有人日後刻意寫 "analytics": {"provider": ""} 關掉統計，
    # 呢項就唔應該攔住整日嘅出版 —— 咁樣就係對照 B 要防嘅假警報，日日阻住正常發佈。
    # 所以先睇本機 data.json 係唔係明確關掉；只有「明確關掉」才略過。鍵缺失唔算關掉
    # （generator 有預設值會照計），所以排程漏咗鍵依然會被下面攔住。
    _an_off = False
    try:
        with open(lp("data.json"), "rb") as f:
            _an_cfg = json.loads(f.read().decode("utf-8")).get("analytics")
        _an_off = (isinstance(_an_cfg, dict) and _an_cfg
                   and not str(_an_cfg.get("provider", "")).strip())
    except Exception:
        _an_off = False      # 讀唔到就照驗，唔好因為讀唔到配置而放行

    def _eps(page_txt):
        return sorted(set(re.findall(r"data-goatcounter','([^']+)'", page_txt)))

    if _an_off:
        checks.add(True, "統計器已接通且收得到",
                   "data.json 明確關掉統計（analytics.provider 空）—— 略過，唔算失敗")
    else:
        ep_home, ep_arch = _eps(txt), _eps(itxt)
        probs = []
        if not ep_home:
            probs.append("首頁冇統計器（data.json 嘅 analytics 鍵漏咗？）")
        if not ep_arch:
            probs.append("存檔目錄頁冇統計器")
        if ep_home and ep_arch and ep_home != ep_arch:
            probs.append("兩頁端點唔同：%s vs %s" % (ep_home, ep_arch))
        # 探測端點嘅網絡錯誤唔等於今日冇出版。fetch() 三次都連唔上會 raise,
        # 冇呢個 try 就會變成 exit 2 ——整日報 failed、而且另外八項根本唔會印出嚟,
        # 得個完全啞嘅失敗。但「連唔上」同「帳號唔存在」要分開講：帳號有問題
        # GoatCounter 係回 HTTP（400／404），唔係連線失敗；連線失敗係我哋這邊
        # 嘅 DNS／TLS／timeout，唔應該攔住 Carrie 嘅出版。所以 HTTP 碼唔對 = 真失敗，
        # 連唔上 = 照過但寫明「未能確認」，等人睇得到係未驗而唔係已驗過。
        _ep_note = ""
        if ep_home:
            try:
                pc, _ = fetcher(ep_home[0] + "?test=1&p=/_verify")
                if pc != 200:
                    probs.append("端點 %s 回 HTTP %s（帳號唔存在就係 400）"
                                 % (ep_home[0], pc))
            except Exception as e:
                _ep_note = "；端點一時連唔上（%s），未能確認帳號，唔當今日失敗" % e
        checks.add(not probs, "統計器已接通且收得到",
                   "端點 %s；問題：%s%s" % (ep_home[0] if ep_home else "無",
                                           "；".join(probs) or "無", _ep_note))

    return checks


def self_test(fetcher=fetch):
    """有效性對照：故意餵壞嘅輸入，證明每項檢查真的會 fail。

    Carrie 的規則：檢核方法本身要先有有效性對照。若明知應該不同的兩者被判為相同，
    係工具壞了，唔係結論成立。
    """
    print("=== 有效性對照 self-test ===")

    def fake(mapping):
        def f(url, **kw):
            for k, v in mapping.items():
                if k in url:
                    return v
            return 200, b""
        return f

    ok_all = True

    # 對照 A：線上仍然係昨日版本（正是 9/26、9/27 停更的樣子）→ 必須 fail
    import tempfile
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "archive"), exist_ok=True)
    today, yday = "2026-09-30", "2026-09-29"
    # 本機頁面要帶住字體引用同 og:image，否則第 7、8 項冇嘢可驗，
    # 等於加咗兩個永遠 pass 嘅恆真檢查 —— 正是這個檔案開頭要防嘅毛病。
    FONT_REF = "@font-face{src:url('/ai-marketing-daily/fonts/Inter-Regular.woff2')}"
    OG_REF = ('<meta property="og:image" content="%s/og/%s.jpg">' % (BASE, today))
    # 同理，fixture 要帶住統計器，否則第 9 項喺每個對照都 fail，對照 B
    # （一切正常）亦會變成永遠唔過，令整個 self-test 失去鑑別力。
    EP = "https://carriehuiww.goatcounter.com/count"
    AN_REF = "s.setAttribute('data-goatcounter','%s');" % EP
    ARCH_LIST = ("列表 " + today + AN_REF).encode()
    local_html = ("<title>AI Marketing Daily · %s</title>" % today
                  + FONT_REF + OG_REF + AN_REF
                  + '<div class="story">x</div>' * 10).encode()
    WOFF_OK = b"wOF2" + b"\0" * 9000          # 夠大、magic 正確
    JPG_OK = b"\xff\xd8\xff" + b"\0" * 9000   # JPEG magic
    with open(os.path.join(d, "index.html"), "wb") as f:
        f.write(local_html)
    with open(os.path.join(d, "archive/manifest.json"), "w") as f:
        json.dump([{"date": today}, {"date": yday}], f)

    stale = ("<title>AI Marketing Daily · %s</title>" % yday
             + FONT_REF + OG_REF + AN_REF
             + '<div class="story">x</div>' * 10).encode()
    c = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, stale),
        "/archive/%s.html" % today: (404, b""),
        "manifest.json": (200, json.dumps([{"date": yday}]).encode()),
        "/archive/": (200, ("列表 " + yday + AN_REF).encode()),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (200, b""),
    }))
    bad = [n for ok, n, _ in c.rows if not ok]
    print("  對照 A（線上仍是昨日版本，應該被攔住）")
    c.report()
    if len(bad) >= 4:
        print("  → 正確：%d 項 fail\n" % len(bad))
    else:
        print("  → 工具壞了：只有 %d 項 fail，停更竟然過關\n" % len(bad))
        ok_all = False

    # 對照 B：全部正常 → 必須全 pass（否則係假警報，會日日阻住正常發佈）
    good_manifest = json.dumps([{"date": today}, {"date": yday}]).encode()
    c2 = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, local_html),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (200, b""),
    }))
    print("  對照 B（一切正常，應該全部通過）")
    c2.report()
    if not c2.failed:
        print("  → 正確：全部 pass\n")
    else:
        print("  → 工具壞了：正常情況都 fail %d 項（假警報）\n" % len(c2.failed))
        ok_all = False

    # 對照 C：一切正常，但字體檔線上 404（最靜默嘅失敗）→ 第 7 項必須單獨 fail。
    # 若呢個對照全 pass，即係第 7 項係恆真，加嚟冇用。
    c3 = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, local_html),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (404, b""),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (200, b""),
    }))
    f3 = [n for ok, n, _ in c3.rows if not ok]
    print("  對照 C（字體檔 404，應該只有字體那項被攔住）")
    c3.report()
    if f3 == ["引用嘅字體檔都取得到"]:
        print("  → 正確：字體 404 攔得住，其餘唔受影響\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期只有字體那項）\n" % f3)
        ok_all = False

    # 對照 D：字體正常，但 og:image 回一個 HTML 錯誤頁（HTTP 200 都唔算圖）。
    # 刻意用 200 而唔係 404：某些主機會用 200 送錯誤頁，純看狀態碼攔唔住。
    c4 = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, local_html),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, b"<!doctype html><title>404</title>" + b" " * 9000),
        "goatcounter.com/count": (200, b""),
    }))
    f4 = [n for ok, n, _ in c4.rows if not ok]
    print("  對照 D（og:image 回 HTTP 200 但內容係 HTML，應該只有卡圖那項被攔住）")
    c4.report()
    if f4 == ["分享卡圖線上取得到"]:
        print("  → 正確：唔係圖就攔住，冇被 HTTP 200 騙到\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期只有卡圖那項）\n" % f4)
        ok_all = False

    # 對照 E：頁面完全冇 woff2 引用 —— 即排程喺 fresh session 漏咗攞 fonts/ 嘅情形。
    # 呢個失敗最惡：所有檔案都「成功」，位元組線上本機一致，部署亦 success，只係字體
    # 靜靜消失。所以要另造一個目錄（本機檔亦冇字體引用，令第 1 項位元組仍然相同），
    # 證明攔住佢嘅係第 7 項本身，而唔係順手被位元組不符攔住。
    d2 = tempfile.mkdtemp()
    os.makedirs(os.path.join(d2, "archive"), exist_ok=True)
    nofont = ("<title>AI Marketing Daily · %s</title>" % today
              + OG_REF + AN_REF + '<div class="story">x</div>' * 10).encode()
    with open(os.path.join(d2, "index.html"), "wb") as f:
        f.write(nofont)
    with open(os.path.join(d2, "archive/manifest.json"), "w") as f:
        json.dump([{"date": today}, {"date": yday}], f)
    c5 = verify(today, d2, Checks(), fetcher=fake({
        "/index.html": (200, nofont),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (200, b""),
    }))
    f5 = [n for ok, n, _ in c5.rows if not ok]
    print("  對照 E（頁面零個字體引用＝排程漏攞 fonts/，應該只有字體那項被攔住）")
    c5.report()
    if f5 == ["引用嘅字體檔都取得到"]:
        print("  → 正確：字體靜默消失都攔得住\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期只有字體那項）\n" % f5)
        ok_all = False

    # 對照 F：頁面完全冇統計器 —— 即 routine 喺 fresh session 寫 data.json 時漏咗
    # analytics 鍵（或者有人改壞預設值）。同對照 E 同一個病理：檔案全部「成功」、
    # 位元組一致、部署 success，只係由嗰日起數字變成零。要另造目錄，令第 1 項位元組
    # 仍然相同，證明攔住佢嘅係第 9 項本身。
    d3 = tempfile.mkdtemp()
    os.makedirs(os.path.join(d3, "archive"), exist_ok=True)
    nocount = ("<title>AI Marketing Daily · %s</title>" % today
               + FONT_REF + OG_REF + '<div class="story">x</div>' * 10).encode()
    with open(os.path.join(d3, "index.html"), "wb") as f:
        f.write(nocount)
    with open(os.path.join(d3, "archive/manifest.json"), "w") as f:
        json.dump([{"date": today}, {"date": yday}], f)
    c6 = verify(today, d3, Checks(), fetcher=fake({
        "/index.html": (200, nocount),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (200, b""),
    }))
    f6 = [n for ok, n, _ in c6.rows if not ok]
    print("  對照 F（頁面冇統計器＝漏咗 analytics，應該只有統計器那項被攔住）")
    c6.report()
    if f6 == ["統計器已接通且收得到"]:
        print("  → 正確：統計器靜默消失都攔得住\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期只有統計器那項）\n" % f6)
        ok_all = False

    # 對照 G：兩個頁面都有統計器，但端點打錯字（帳號唔存在 → GoatCounter 回 400）。
    # 刻意同對照 F 分開：F 證明「冇」攔得住，G 證明「有但收唔到」亦攔得住。若只有 F，
    # 第 9 項就退化成「頁面有冇嗰串字」，而一個 typo 嘅端點照樣會過。
    c7 = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, local_html),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, JPG_OK),
        "goatcounter.com/count": (400, b""),   # 帳號唔存在嘅真實回應
    }))
    f7 = [n for ok, n, _ in c7.rows if not ok]
    print("  對照 G（端點回 400＝帳號打錯字，應該只有統計器那項被攔住）")
    c7.report()
    if f7 == ["統計器已接通且收得到"]:
        print("  → 正確：唔會只睇頁面有冇嗰串字\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期只有統計器那項）\n" % f7)
        ok_all = False

    # 對照 H：刻意關掉統計（data.json 寫 analytics.provider = ""）→ 第 9 項應該略過
    # 而唔係 fail。呢個係針對上面「略過」分支嘅對照：一個會吞掉真失敗嘅逃生門，
    # 比冇檢查更差，所以要同時證明兩件事 ——
    #   H1 明確關掉 + 頁面冇統計器 → 唔算失敗（否則關唔得，日日阻住發佈）；
    #   H2 冇寫 analytics 鍵（即排程漏咗）+ 頁面冇統計器 → 仍然 fail（對照 F 已證），
    #      所以「鍵缺失」唔會被誤當成「刻意關掉」。
    with open(os.path.join(d3, "data.json"), "w", encoding="utf-8") as f:
        json.dump({"analytics": {"provider": ""}}, f)
    c8 = verify(today, d3, Checks(), fetcher=fake({
        "/index.html": (200, nocount),
        "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
        "manifest.json": (200, good_manifest),
        "/archive/": (200, ARCH_LIST),
        ".woff2": (200, WOFF_OK),
        ".jpg": (200, JPG_OK),
    }))
    f8 = [n for ok, n, _ in c8.rows if not ok]
    print("  對照 H（刻意關掉統計，應該略過而唔係 fail）")
    c8.report()
    if not f8:
        print("  → 正確：關得掉，唔會日日阻住發佈\n")
    else:
        print("  → 工具壞了：fail 清單係 %s（預期一項都唔 fail）\n" % f8)
        ok_all = False
    os.remove(os.path.join(d3, "data.json"))   # 唔好污染對照 F 嘅目錄

    # 對照 I：GoatCounter 一時連唔上（DNS／TLS／timeout，fetch 三次都 raise）。
    # 呢個係第二個逃生門嘅對照。冇佢嘅時候，一個網絡抖動會由 verify() raise 出去
    # 變成 exit 2 —— 整日報 failed，而另外八項根本唔會印出嚟，變成完全啞嘅失敗。
    # 要同時證明兩件事：
    #   I1 連唔上 → 唔當今日失敗（頁面真係出版咗，唔應該因為我哋呢邊嘅網絡而卡住）；
    #   I2 但要喺 detail 講明「未能確認」，否則會被讀成「已驗過，統計正常」——
    #      即係 Carrie 嘅假精準第②種：摘要那行寫得比內文肯定。
    # 分辨得開係因為帳號出事 GoatCounter 回 HTTP（對照 G 嘅 400），唔係連線失敗。
    def _flaky(url, **kw):
        if "goatcounter.com/count" in url:
            raise RuntimeError("連線逾時（模擬）")
        for k, v in {
            "/index.html": (200, local_html),
            "/archive/%s.html" % today: (200, ("存檔 " + today).encode()),
            "manifest.json": (200, good_manifest),
            "/archive/": (200, ARCH_LIST),
            ".woff2": (200, WOFF_OK),
            ".jpg": (200, JPG_OK),
        }.items():
            if k in url:
                return v
        return 200, b""

    try:
        c9 = verify(today, d, Checks(), fetcher=_flaky)
        f9 = [n for ok, n, _ in c9.rows if not ok]
        note9 = [dt for ok, n, dt in c9.rows if n == "統計器已接通且收得到"][0]
    except Exception as e:
        c9, f9, note9 = None, ["<verify 自身 raise：%s>" % e], ""
    print("  對照 I（端點一時連唔上，應該唔當失敗、但要寫明未能確認）")
    if c9 is not None:
        c9.report()
    if not f9 and "未能確認" in note9:
        print("  → 正確：網絡抖動唔會冤枉今日停更，而且冇講大話\n")
    else:
        print("  → 工具壞了：fail 清單 %s；統計器那行寫「%s」\n" % (f9, note9))
        ok_all = False

    print("self-test %s" % ("通過：九個對照都符合預期" if ok_all else "不通過：檢查器本身有問題"))
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="期號 YYYY-MM-DD")
    ap.add_argument("--dir", default=".", help="剛 build 出嘅檔案所在資料夾")
    ap.add_argument("--self-test", action="store_true", help="跑有效性對照，唔碰網絡")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.today:
        print("要 --today YYYY-MM-DD", file=sys.stderr)
        return 2

    print("=== 發佈後驗證 %s ===" % a.today)
    try:
        c = verify(a.today, a.dir, Checks())
    except Exception as e:
        print("驗證腳本自身出錯：%s" % e, file=sys.stderr)
        return 2
    c.report()
    if c.failed:
        print("\n驗證不通過（%d 項）。今日並未成功出版。" % len(c.failed))
        print("routine 必須以失敗結束並發失敗通知 —— 唔准當 success 收尾。")
        return 1
    print("\n全部通過：今日確實已出版，可以行第 7 步發快訊。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
