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
    local_html = ("<title>AI Marketing Daily · %s</title>" % today + '<div class="story">x</div>' * 10).encode()
    with open(os.path.join(d, "index.html"), "wb") as f:
        f.write(local_html)
    with open(os.path.join(d, "archive/manifest.json"), "w") as f:
        json.dump([{"date": today}, {"date": yday}], f)

    stale = ("<title>AI Marketing Daily · %s</title>" % yday + '<div class="story">x</div>' * 10).encode()
    c = verify(today, d, Checks(), fetcher=fake({
        "/index.html": (200, stale),
        "/archive/%s.html" % today: (404, b""),
        "manifest.json": (200, json.dumps([{"date": yday}]).encode()),
        "/archive/": (200, ("列表 " + yday).encode()),
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
        "/archive/": (200, ("列表 " + today).encode()),
    }))
    print("  對照 B（一切正常，應該全部通過）")
    c2.report()
    if not c2.failed:
        print("  → 正確：全部 pass\n")
    else:
        print("  → 工具壞了：正常情況都 fail %d 項（假警報）\n" % len(c2.failed))
        ok_all = False

    print("self-test %s" % ("通過：兩個對照都符合預期" if ok_all else "不通過：檢查器本身有問題"))
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
