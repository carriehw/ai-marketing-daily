# -*- coding: utf-8 -*-
"""Build a Traditional Chinese, email-safe Morning Brief from verified data.json.
Only generates artifacts; the existing editorial publication gate must run first.
"""
import json, html, re, hashlib
from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree as ET

HOME="https://carriehw.github.io/ai-marketing-daily/"
FONT="Arial,'PingFang HK','Microsoft JhengHei',sans-serif"
PALETTE=["#39689F","#3F5BC8","#6249D7","#9A3A9E","#7D266B"]
PRIORITY={"影響生意":30,"可即用":24,"要留意":12}
CATEGORY={"廣告平台 & 行銷科技":15,"行業影響 & 品牌案例":13,"AI 大模型 & 市場動態":10,"創意生產工具":8,"即學技巧 & 玩法":7}
def e(v): return html.escape(str(v or ""),quote=True)
def rank(items):
    def key(entry):
        i,s=entry
        p=s.get("edm_priority")
        if type(p) in (int,float): return (0,float(p),i)
        return (1,-PRIORITY.get(s.get("action"),0)-CATEGORY.get(s.get("section"),0),i)
    return [s for _,s in sorted(enumerate(items),key=key)[:6]]
def link(site,date,part,item=None,anchors=None):
    params=urlencode({"lang":"zh","utm_source":"edm","utm_medium":"email",
                     "utm_campaign":"ai-daily-"+date,"utm_content":part})
    result=site.rstrip("/")+"/?"+params
    if item is not None and anchors:
        u=urlsplit(item["url"])
        norm=(u.netloc.lower().replace("www.","")+u.path.rstrip("/")).encode()
        slug=anchors.get(hashlib.sha1(norm).hexdigest()[:6])
        if slug:result+="#"+slug
    return e(result)
def build(root=Path(".")):
    root=Path(root)
    data=json.loads((root/"data.json").read_text(encoding="utf-8"))
    date=data["date"]; day=datetime.strptime(date,"%Y-%m-%d")
    items=data.get("items",[])
    if len(items)<10: raise ValueError("HELD: editorial minimum of 10 articles not met")
    for i,item in enumerate(items):
        if not all(item.get(k) for k in ("title","section","action","url","why")):
            raise ValueError("HELD: missing required fields in story "+str(i+1))
        if not item["url"].startswith("https://"):
            raise ValueError("HELD: invalid source URL in story "+str(i+1))
    index=root/"index.html";anchors={}
    if index.exists():
        for m in re.finditer(r'id="([a-z0-9][a-z0-9-]*-[0-9a-f]{6})"',index.read_text(encoding="utf-8")):
            anchors[m.group(1).rsplit("-",1)[1]]=m.group(1)
    selected=rank(items)
    if index.exists():
        for it in selected:
            u=urlsplit(it["url"])
            digest=hashlib.sha1((u.netloc.lower().replace("www.","")+u.path.rstrip("/")).encode()).hexdigest()[:6]
            if digest not in anchors:raise ValueError("HELD: website story anchor missing for "+it["title"])
    site=data.get("site_url") or HOME
    display=f'{day.year}年{day.month}月{day.day}日 · 星期{"一二三四五六日"[day.weekday()]}'
    subject=f"AI Marketing Daily｜{date}｜今日 6 大重點"
    p=[f'''<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="#EEEDE7" style="width:100%;border-collapse:collapse;background:#EEEDE7"><tr><td align="center" style="padding:12px 5px"><table role="presentation" cellpadding="0" cellspacing="0" border="0" width="640" bgcolor="#F7F5EF" style="width:100%;max-width:640px;border-collapse:collapse;background:#F7F5EF">
<tr><td bgcolor="#11154A" style="padding:27px 25px;background-color:#11154A;background-image:linear-gradient(115deg,#553FBA,#2F5582,#11154A)"><div style="font:800 21px {FONT};color:#D3FE66">AI・行銷情報</div><div style="font:11px {FONT};color:#D6D4E8;padding-top:4px">AI MARKETING DAILY · HK / CN</div><div style="font:700 11px {FONT};color:#D3FE66;padding-top:23px">MORNING BRIEF · {e(display)}</div><div style="font:800 28px/1.35 {FONT};color:white;padding-top:11px">少一點 AI 噪音。<span style="color:#D3FE66">多一點行銷訊號。</span></div><div style="font:12px {FONT};color:#EDEBF6;padding-top:14px">{len(items)} 則新聞 · 精選 6 則 · 約 3 分鐘閱讀</div></td></tr>
<tr><td style="padding:25px 25px 13px"><div style="font:800 11px {FONT};color:#5A42F4">TODAY'S BIG PICTURE / 今日核心訊號</div><div style="font:800 19px/1.5 {FONT};color:#101114;padding-top:9px">{e(data.get("thesis") or "每日值得行銷團隊關注的 AI 訊號。")}</div><div style="font:13px/1.65 {FONT};color:#4B4D55;padding-top:6px">{e(data.get("thesis_note"))}</div></td></tr>
<tr><td style="padding:13px 25px 7px"><div style="font:800 23px {FONT};color:#101114">今日 6 大重點</div><div style="font:12px {FONT};color:#656A73;padding-top:3px">TOP KEY HIGHLIGHTS · 依行銷相關度排序</div></td></tr>''']
    for i,s in enumerate(selected):
        cat=data["sections"].index(s["section"]) if s["section"] in data["sections"] else 0
        color=PALETTE[cat%5];href=link(site,date,f"highlight-{i+1}",s,anchors)
        summary=(f'<div style="font:13px/1.65 {FONT};color:#4B4D55;padding-top:9px">{e(s.get("summary"))}</div>' if i<3 else "")
        p.append(f'''<tr><td style="padding:9px 25px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#FFFFFF" style="background:#FFFFFF;border:1px solid #DEDBD2;border-top:4px solid {color};border-collapse:collapse"><tr><td style="padding:17px"><div style="font:800 11px {FONT};color:{color}">{i+1:02d} / {e(s["section"])} · {e(s["action"])}</div><div style="font:800 {18 if i<3 else 16}px/1.4 {FONT};color:#101114;padding-top:11px"><a href="{href}" style="color:#101114;text-decoration:none">{e(s["title"])}</a></div>{summary}<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;border-collapse:collapse"><tr><td bgcolor="#EBE8FF" style="border-left:3px solid #5A42F4;background:#EBE8FF;padding:10px 12px"><div style="font:800 10px {FONT};color:#5A42F4">MARKETER TAKEAWAY</div><div style="font:13px/1.6 {FONT};color:#101114;padding-top:4px">{e(s["why"])}</div></td></tr></table><div style="font:700 12px {FONT};padding-top:11px"><a href="{href}" style="color:#5A42F4;text-decoration:none">閱讀完整新聞 &#8594;</a></div></td></tr></table></td></tr>''')
    acts=[x["next_step"] for x in selected if x.get("next_step")][:3]
    if acts:
        rows="".join(f'<tr><td valign="top" style="font:800 12px {FONT};color:#5A42F4;padding:0 9px 10px 0">{i:02d}</td><td style="font:13px/1.6 {FONT};color:#101114;padding-bottom:10px">{e(t)}</td></tr>' for i,t in enumerate(acts,1))
        p.append(f'''<tr><td style="padding:23px 25px 0"><table role="presentation" width="100%" bgcolor="#EBE8FF" style="background:#EBE8FF"><tr><td style="border-left:4px solid #5A42F4;padding:17px"><div style="font:800 11px {FONT};color:#5A42F4">TEAM ACTION BOARD</div><div style="font:800 18px {FONT};color:#101114;padding:7px 0 12px">今日可以跟進嘅方向</div><table role="presentation">{rows}</table></td></tr></table></td></tr>''')
    p.append(f'''<tr><td align="center" style="padding:28px 25px"><table role="presentation"><tr><td bgcolor="#5A42F4" style="background:#5A42F4;border-radius:24px;padding:13px 25px"><a href="{link(site,date,"cta")}" style="font:800 14px {FONT};color:white;text-decoration:none">閱讀今日完整新聞 &#8594;</a></td></tr></table></td></tr><tr><td bgcolor="#151841" style="background:#151841;padding:24px"><div style="font:800 16px {FONT};color:#D3FE66">AI Marketing Daily</div><div style="font:12px/1.8 {FONT};color:#E5E2EF;padding-top:8px">Curated by Carrie Hui · AI Marketing Intelligence</div><div style="font:11px/1.8 {FONT};color:#B9BADA;padding-top:9px">本電郵為已發佈網站內容精選，原始來源請查閱網站。</div><a href="{link(site,date,"footer")}" style="font:12px {FONT};color:#D3FE66">在瀏覽器閱讀</a></td></tr></table></td></tr></table>''')
    inner="".join(p)
    doc=f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(subject)}</title></head><body style="margin:0;padding:0">{inner}</body></html>'
    if len(doc.encode("utf-8"))>=102400:raise ValueError("HELD: email over clipping size")
    (root/"edm").mkdir(exist_ok=True)
    (root/"email-zh.html").write_text(doc,encoding="utf-8")
    (root/"email-zh-subject.txt").write_text(subject+"\n",encoding="utf-8")
    rss=(f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>AI Marketing Daily HTML EDM</title><link>{HOME}</link><description>Verified daily Chinese news brief</description><item><title>{e(subject)}</title><link>{HOME}?lang=zh</link><guid isPermaLink="false">ai-daily-{date}</guid><pubDate>{format_datetime(datetime.now(timezone.utc))}</pubDate><description><![CDATA[{inner.replace("]]>", "]] >")}]]></description></item></channel></rss>')
    ET.fromstring(rss)
    (root/"edm/feed.xml").write_text(rss,encoding="utf-8")
    (root/"edm/manifest.json").write_text(json.dumps({"date":date,"stories":len(items),"highlights":6,"source":"data.json"},ensure_ascii=False),encoding="utf-8")
    print("PASS Chinese EDM",date,len(doc.encode()),"bytes")

if __name__=="__main__":build()