#!/usr/bin/env python3
"""第四道閘門：日期與時序主張。

verify_live.py 問「出版成功了嗎」，verify_email.py 問「EDM 版式對嗎」。
兩者都不會讀內文的時間主張，所以 2026-10-26 出過三類缺陷：
  ①『time』欄填今日當預設 → 卡片向讀者印假日期（最嚴重一則差 19 天）
  ②detail 內文自己寫一個日期，與已核實的 time 衝突（可口可樂 10/26 vs 10/22）
  ③followup 寫「今日」，而來源其實比我們的往期報道更早（時序不可能）

用法：python3 verify_dates.py --today 2026-10-26 [--data data.json]
       --control <舊檔>  用改前的檔案自檢：閘門必須在它身上報錯，否則閘門本身是瞎的
exit 0 = 全部通過
"""
import argparse
import json
import re
import sys

DATE = re.compile(r"(?:2026年)?(\d{1,2})月(\d{1,2})日")

# 相對時間詞：在一份隔日仍可讀的刊物裡，這些詞沒有錨點就是錯的。
# 「今日」只在 thesis_note（指今期刊物本身）成立，其餘欄位一律不准。
RELATIVE = ["今日", "今天", "昨日", "昨天", "日前", "本週", "上週", "剛剛", "稍早",
            "同步宣布", "同時宣布", "最新宣布", "數日前"]
RELATIVE_OK_FIELDS = {"thesis_note"}

TEXT_FIELDS = ("title", "summary", "detail", "pattern", "why", "followup")


def iter_strings(item):
    for k in item:
        v = item[k]
        if isinstance(v, str):
            yield k, v
        elif isinstance(v, list):
            for j, x in enumerate(v):
                if isinstance(x, str):
                    yield f"{k}[{j}]", x


def md(s):
    m = DATE.search(s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def run(data, today_md, strict=True, same_day_verified_urls=None):
    """回傳 (fails, checks)。fails 是 list of str。"""
    fails, checks = [], 0
    items = data["items"]

    # --- 1. 每則都要有可解析的 time，且不得等於今日（今日發表的新聞當然存在，
    #        只是 2026-10-26 那一輪的「今日」全部是填空的預設值，所以這裡要求
    #        明示：若真有今日新聞，把它的 url 加進 ALLOW_TODAY 並寫明核實來源）
    # Only reviewed evidence with an explicit source publication date permits a
    # same-day story. This structural check does not replace source inspection.
    ALLOW_TODAY = set(same_day_verified_urls or [])
    for i, it in enumerate(items, 1):
        checks += 1
        tm = md(str(it.get("time", "")))
        if tm is None:
            fails.append(f"#{i:02d} time 欄無法解析為日期：{it.get('time')!r}")
            continue
        checks += 1
        if tm == today_md and it.get("url") not in ALLOW_TODAY:
            fails.append(
                f"#{i:02d} time 等於今日（{it.get('time')}）而未列入 ALLOW_TODAY："
                f"今日日期是填空預設值的徵兆 — {it.get('url','')[:70]}")

    # --- 2. 內文不得出現晚於該則發佈日的日期（那是不可能知道的）
    for i, it in enumerate(items, 1):
        tm = md(str(it.get("time", "")))
        if tm is None:
            continue
        for field, text in iter_strings(it):
            if not any(field.startswith(f) for f in TEXT_FIELDS):
                continue
            # followup 開頭引用的是「我們往期刊物」的日期，本就可以晚於來源發佈日
            # （往期是我們何時報的，不是對方何時發的）。那一個日期由第 4 項檢查
            # 專門處理；在這裡一併算進去，會對正確的檔案誤報。
            matches = list(DATE.finditer(text))
            if field == "followup" and matches:
                matches = matches[1:]
            for mo in matches:
                checks += 1
                d = (int(mo.group(1)), int(mo.group(2)))
                if d > tm:
                    j = mo.start()
                    fails.append(
                        f"#{i:02d} [{field}] 內文日期 {d[0]}月{d[1]}日 晚於該則發佈日 "
                        f"{tm[0]}月{tm[1]}日：…{text[max(0,j-50):j+50]}…")

    # --- 3. 相對時間詞（thesis_note 的「今日」除外）
    for i, it in enumerate(items, 1):
        for field, text in iter_strings(it):
            for n in RELATIVE:
                for mo in re.finditer(re.escape(n), text):
                    checks += 1
                    j = mo.start()
                    fails.append(
                        f"#{i:02d} [{field}] 相對時間詞「{n}」沒有日期錨點："
                        f"…{text[max(0,j-50):j+50]}…")
    for k in data:
        if k == "items" or k in RELATIVE_OK_FIELDS or not isinstance(data[k], str):
            continue
        for n in RELATIVE:
            for mo in re.finditer(re.escape(n), data[k]):
                checks += 1
                fails.append(f"[{k}] 相對時間詞「{n}」沒有日期錨點")

    # --- 4. followup 的時序：若 followup 引用了我們的往期日期，而該則來源更早，
    #        就不能用「補充／進一步」的框架講（那是把因果倒過來）
    for i, it in enumerate(items, 1):
        fu = it.get("followup")
        if not isinstance(fu, str) or not fu:
            continue
        past = md(fu)
        tm = md(str(it.get("time", "")))
        if past is None or tm is None:
            continue
        checks += 1
        if tm < past:
            # 來源早於往期報道 → 必須明示這個先後，不能寫成「補充」
            if "早於" not in fu:
                fails.append(
                    f"#{i:02d} [followup] 來源 {tm[0]}月{tm[1]}日 早於引用的往期 "
                    f"{past[0]}月{past[1]}日，而文中未註明「早於」：時序被倒置")

    # --- 5. 禁用轉折詞（使用者指令，交付文件同樣適用）
    blob = json.dumps(data, ensure_ascii=False)
    for bad in ("但是", "不過"):
        checks += 1
        if bad in blob:
            fails.append(f"禁用轉折詞「{bad}」出現 {blob.count(bad)} 次")

    return fails, checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", required=True)
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--control", help="改前的舊檔；閘門必須在它身上報錯")
    a = ap.parse_args()

    y, m, dd = (int(x) for x in a.today.split("-"))
    today_md = (m, dd)

    data = json.load(open(a.data, encoding="utf-8"))
    same_day_allowed = set()
    proof_path = __import__("pathlib").Path("editorial/evidence") / (a.today + ".json")
    if proof_path.is_file():
        proof = json.load(open(proof_path, encoding="utf-8"))
        for story in proof.get("stories", []):
            if story.get("editorial_decision") != "approved" or story.get("needs_human_review") is not False:
                continue
            if story.get("source_date_display") != f"{m}月{dd}日":
                continue
            for doc in story.get("source_documents", []):
                if (doc.get("source_publication_date") == a.today
                    and doc.get("source_class") in ("A", "B")
                    and len(doc.get("evidence_locator", "")) >= 12):
                    same_day_allowed.add(story.get("source_story_url"))
                    break
    fails, checks = run(data, today_md, same_day_verified_urls=same_day_allowed)

    print(f"=== 日期與時序閘門 {a.today} ===")

    if a.control:
        cdata = json.load(open(a.control, encoding="utf-8"))
        cfails, _ = run(cdata, today_md)
        if cfails:
            print(f"  ok   有效性對照：閘門在舊檔 {a.control} 上報出 {len(cfails)} 項 "
                  f"（閘門會咬人）")
            for f in cfails[:4]:
                print(f"         · {f[:110]}")
        else:
            print(f"  FAIL 有效性對照：閘門在舊檔 {a.control} 上一項都沒報 — "
                  f"閘門本身是瞎的，下面的綠燈不算數")
            return 2

    if fails:
        for f in fails:
            print(f"  FAIL {f}")
        print(f"\n{checks - len(fails)} pass / {len(fails)} fail")
        return 1

    print(f"  PASS 全部 {len(data['items'])} 則：time 可解析、當日日期已有覆核依據、"
          f"內文無超前日期、無失錨的相對時間詞、followup 時序正確、無禁用轉折詞")
    print(f"\n{checks} pass / 0 fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
