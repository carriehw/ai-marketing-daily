#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produce static, indexable /en/, /zh-hant/, /zh-hans/ editions and archives.

Legacy ?lang= URLs keep working. Each language page has its own URL, canonical,
bidirectional hreflang, locale-fixed navigation, and full local archive history.
Simplified Chinese uses OpenCC T2S plus a controlled Mainland marketing glossary;
do not confuse mechanical validation with independent human translation review.
"""
import argparse
import copy
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup, NavigableString, Comment
from opencc import OpenCC

ROOT = Path(__file__).resolve().parent
CC = OpenCC("t2s")
LOCALES = {"en": "en", "zh-hant": "zh-Hant", "zh-hans": "zh-Hans"}
SOURCE_CLASS = {"en":"l-en", "zh-hant":"l-zh", "zh-hans":"l-zh"}
SEO_LOCALE = {"en":"en_US","zh-hant":"zh_HK","zh-hans":"zh_CN"}
GLOSSARY = [
    ("行销", "营销"),
    ("行销人", "营销人"),
    ("行销团队", "营销团队"),
    ("社群运营", "社交媒体运营"),
    ("社群平台", "社交平台"),
    ("着陆页", "落地页"),
    ("网志", "博客"),
    ("影片", "视频"),
    ("讯息", "消息"),
    ("唔好", "不要"),
    ("唔系", "不是"),
    ("私隐", "隐私"),
    ("唔", "不"),
    ("嘅", "的"),
    ("喺", "在"),
    ("点击率", "点击率"),
    ("广告识别符", "广告标识符"),
    ("台港通用", "中文"),
]
def to_hans(s):
    if not isinstance(s,str):return s
    result=CC.convert(s)
    for original,target in GLOSSARY:
        result=result.replace(original,target)
    return result

def t(s):return to_hans(s) if isinstance(s,str) else s
def fail(reason):raise RuntimeError(reason)

def locale_url(base,locale,kind,date=""):
    prefix=base.rstrip("/")+"/"+locale+"/"
    if kind=="home":return prefix
    if kind=="directory":return prefix+"archive/"
    if kind=="issue":return prefix+"archive/"+date+".html"
    fail("Unknown localized page kind: "+kind)

def rewrite_meta(soup,key,which,value):
    tag=soup.find("meta",attrs={key:which})
    if not tag:
        tag=soup.new_tag("meta",attrs={key:which})
        soup.head.append(tag)
    tag["content"]=value

def replace_script(script,content):
    script.clear()
    script.append(content)

def configure_nav(soup,base,kind,date,selected):
    for div in soup.select(".langtog"):
        nav=soup.new_tag("nav",attrs={"class":"langtog locale-links","aria-label":"Language / 語言 / 语言"})
        for slug,label in (("zh-hant","繁"),("zh-hans","简"),("en","EN")):
            link=soup.new_tag("a",href=locale_url(base,slug,kind,date))
            link.string=label
            link["hreflang"]=LOCALES[slug]
            if slug==selected:
                link["class"]="on"
                link["aria-current"]="page"
            nav.append(link)
        div.replace_with(nav)
    # Keep same responsive footprint as the previous 2-toggle controls.
    sheet=soup.new_tag("style")
    sheet.string="""
.locale-links{display:inline-flex!important;flex:none;align-items:center;border:1px solid rgba(247,245,239,.3);border-radius:99px;overflow:hidden}
.locale-links a{font:inherit;font-size:12px;font-weight:700;color:#dedcf1;display:inline-block;line-height:1.4;text-decoration:none;padding:7px 9px;border-right:1px solid rgba(247,245,239,.2);white-space:nowrap}
.locale-links a:last-child{border-right:0}
.locale-links a.on{background:#d3fe66;color:#11154a}
.locale-links a:focus-visible{outline:2px solid #d3fe66;outline-offset:-2px}
@media(max-width:460px){.locale-links a{padding:7px 7px;font-size:11.5px}}
"""
    if soup.head:soup.head.append(sheet)

def translate_hans(soup):
    """Only translate prose / language labels; preserve IDs, refs and source URLs."""
    # Inline JavaScript contains Chinese UI fallback messages and locale-specific
    # accessibility text, so translate string contents, leaving JS identifiers intact.
    for script in soup.find_all("script"):
        if script.get("type") == "application/ld+json":
            continue
        if script.get("id")=="news-discovery-data":
            try:
                payload=json.loads(script.string or "{}")
                for item in payload.get("items",[]):
                    for key in ("title","summary","why","next_step"):
                        if item.get(key):item[key]=to_hans(item[key])
                replace_script(script,json.dumps(payload,ensure_ascii=False,separators=(",",":")).replace("<",r"\u003c"))
            except (ValueError,TypeError) as exc:
                fail("Bad embedded discovery data: "+str(exc))
            continue
        if script.string:
            replace_script(script,to_hans(str(script.string)).replace("'zh-Hant'","'zh-Hans'"))
    for node in list(soup.find_all(string=True)):
        if isinstance(node,Comment):continue
        if node.parent and node.parent.name in ("script","style"):continue
        if node.strip():node.replace_with(to_hans(str(node)))
    for element in soup.find_all(True):
        for key in ("title","aria-label","placeholder","data-zh","data-title-zh","content"):
            if key in element.attrs and isinstance(element[key],str):
                # Meta description/OG titles are handled separately; URL tags remain untouched.
                if key=="content" and element.name!="meta":continue
                if key=="content" and (element.get("property","").endswith(("url","image")) or
                                       element.get("name","") in ("twitter:image",)):continue
                element[key]=to_hans(element[key])

def render(source,locale,kind,base,date,issue_title,issue_title_en,issue_count):
    soup=BeautifulSoup(source,"html.parser")
    if not soup.html or not soup.head or not soup.body:
        fail("Malformed HTML source for "+kind+" "+date)
    for tag in soup.select("span.l-zh,span.l-en"):
        if SOURCE_CLASS[locale] not in tag.get("class",[]):
            tag.decompose()
        else:
            tag.unwrap()
    soup.html["lang"]=LOCALES[locale]
    soup.html["data-lang"]="en" if locale=="en" else "zh"
    configure_nav(soup,base,kind,date,locale)
    for sc in soup.find_all("script"):
        content=sc.string or ""
        if "Language on entry, resolved before paint" in content or (
            kind=="directory" and "new URLSearchParams(location.search)" in content):
            replace_script(sc,"/* Static edition: URL determines language. */")
    # Rewire the retained sticky share handler to this language's published URL.
    new_url=locale_url(base,locale,kind,date)
    for script in soup.find_all("script"):
        if not script.string:continue
        text=str(script.string)
        if "const SHARE_URL=" in text:
            text,n=re.subn(r'const SHARE_URL=(?:"[^"]*"|location\.href);',
                           "const SHARE_URL="+json.dumps(new_url)+";",text,count=1)
            if not n:fail("Unable to set edition share URL for "+new_url)
            replace_script(script,text)
    # Permanent chapter links resolve within their own language directory.
    for a in soup.find_all("a",href=True):
        old=a["href"]
        if kind=="home" and old=="archive/":
            a["href"]=locale_url(base,locale,"directory")
        elif kind=="issue" and old in ("archive/","./"):
            a["href"]=locale_url(base,locale,"directory")
        elif kind=="issue" and old=="../":
            a["href"]=locale_url(base,locale,"home")
        elif kind=="directory" and old in ("../",):
            a["href"]=locale_url(base,locale,"home")
        elif kind=="directory" and re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html",old):
            a["href"]=locale_url(base,locale,"issue",old[:10])
    for sc in soup.find_all("script",attrs={"id":"news-discovery-data"}):
        payload=json.loads(sc.string or "{}")
        payload["edition_base"]=locale_url(base,locale,"home")
        payload["site_base"]=base
        replace_script(sc,json.dumps(payload,ensure_ascii=False,separators=(",",":")).replace("<",r"\u003c"))
    # Keep the compiled client separate from the page's locale so its in-app status
    # and copy confirmation are also in idiomatic Simplified Chinese.
    if locale=="zh-hans":
        for sc in soup.find_all("script",src=True):
            src=str(sc["src"])
            if src.endswith("/discovery.js") or src=="discovery.js":
                sc["src"]=src.rsplit("/",1)[0]+"/discovery-zh-hans.js" if "/" in src else "discovery-zh-hans.js"
    # In legacy pages scripts may use older UI; archives remain fully readable.
    # Meta and JSON-LD are strictly per-language; don't canonically collapse them.
    canonical=soup.find("link",rel="canonical")
    if not canonical:
        canonical=soup.new_tag("link",rel="canonical")
        soup.head.append(canonical)
    canonical["href"]=new_url
    for old in soup.find_all("link",rel="alternate"):
        if old.has_attr("hreflang"):old.decompose()
    for lang,code in LOCALES.items():
        link=soup.new_tag("link",rel="alternate",
                          href=locale_url(base,lang,kind,date),hreflang=code)
        soup.head.append(link)
    soup.head.append(soup.new_tag("link",rel="alternate",
        href=(base if kind=="home" else base.rstrip("/")+
             ("/archive/" if kind=="directory" else "/archive/"+date+".html")),
        hreflang="x-default"))
    rewrite_meta(soup,"property","og:url",new_url)
    rewrite_meta(soup,"property","og:locale",SEO_LOCALE[locale])
    for meta in soup.find_all("meta",attrs={"property":"og:locale:alternate"}):
        meta.decompose()
    title_text=issue_title_en if locale=="en" else issue_title
    if locale=="zh-hans":title_text=to_hans(title_text)
    if kind=="home" or kind=="issue":
        base_title=(("AI Marketing Daily" if locale=="en" else
                   ("AI・营销情报" if locale=="zh-hans" else "AI・行銷情報")))
        title_value=f"{base_title} · {date}"
    else:
        title_value={"en":"AI Marketing Daily · Archive",
                     "zh-hant":"AI・行銷情報 · 歷史存檔",
                     "zh-hans":"AI・营销情报 · 历史存档"}[locale]
    if soup.title:soup.title.string=title_value
    rewrite_meta(soup,"property","og:title",title_value)
    rewrite_meta(soup,"name","twitter:title",title_value)
    description=soup.find("meta",attrs={"name":"description"})
    if description and locale!="en":
        description["content"]=(f"{issue_count} 則新聞 · {date} · " + title_text)[:190]
    if description:
        rewrite_meta(soup,"property","og:description",description.get("content",""))
        rewrite_meta(soup,"name","twitter:description",description.get("content",""))
    for script in soup.find_all("script",attrs={"type":"application/ld+json"}):
        try:
            data=json.loads(script.string or "{}")
            data["url"]=new_url
            data["inLanguage"]=[LOCALES[locale]]
            data["name"]=title_value
            if description:data["description"]=description.get("content","")
            if isinstance(data.get("hasPart"),list):
                for item in data["hasPart"]:
                    if locale=="zh-hans":item["headline"]=to_hans(item.get("headline",""))
            replace_script(script,json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<",r"\u003c"))
        except (ValueError,TypeError) as exc:
            # Some 2026 legacy archive templates shipped malformed JSON-LD.
            # They remain readable articles: replace only broken machine metadata
            # with a minimal, truthful CollectionPage based on the dated archive.
            # Never repair a broken field by inventing title, publisher or dates.
            print(f"WARN {date}: legacy JSON-LD invalid ({exc}); replaced with minimal CollectionPage")
            fallback={
                "@context":"https://schema.org","@type":"CollectionPage",
                "name":title_value,"url":new_url,
                "datePublished":date,"inLanguage":[LOCALES[locale]]
            }
            replace_script(script,json.dumps(fallback,ensure_ascii=False,separators=(",",":")))
    if locale=="zh-hans":
        translate_hans(soup)
        # Re-set language after translation of JS and source body.
        soup.html["lang"]="zh-Hans"
    return str(soup)+"\n"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=str(ROOT))
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        assert to_hans("行銷情報、廣告投放與社群平台")=="营销情报、广告投放与社交平台"
        assert locale_url("https://example.org/news/","zh-hans","issue","2026-10-26")=="https://example.org/news/zh-hans/archive/2026-10-26.html"
        sample='<html><head><title>Hi</title></head><body><span class="l-zh">你好</span><span class="l-en">hello</span></body></html>'
        assert "hello" not in render(sample,"zh-hans","issue","https://example.org/news/","2026-10-26","新聞","News",1)
        print("PASS locale conversion, directory URLs and truly language-specific text")
        return
    root=Path(args.root)
    data=json.loads((root/"data.json").read_text(encoding="utf-8"))
    manifest=json.loads((root/"archive/manifest.json").read_text(encoding="utf-8"))
    base=data["site_url"]
    date=data["date"]
    issues={issue["date"]:issue for issue in manifest}
    if not base.startswith("https://"):fail("site_url must use HTTPS")
    if date not in issues:fail("Current issue missing from archive manifest")
    if not (root/"index.html").exists():fail("Run build.py before build_locales.py")
    archive_dir=(root/"archive")
    if len(manifest)<1:fail("No historical issues found")
    # The historical search index is shared, with a terminology-reviewed Chinese
    # copy so simplified search results don't display Traditional Chinese.
    archive_search=json.loads((archive_dir/"search-index.json").read_text(encoding="utf-8"))
    localized_search=copy.deepcopy(archive_search)
    for record in localized_search["items"]:
        for key in ("title_zh","summary_zh"):
            if key in record:record[key]=to_hans(record[key])
    (archive_dir/"search-index-zh-hans.json").write_text(
        json.dumps(localized_search,ensure_ascii=False,separators=(",",":"))+"\n",
        encoding="utf-8")
    # Converted front-end messages, statuses and accessible labels.
    js=(root/"discovery.js").read_text(encoding="utf-8")
    (root/"discovery-zh-hans.js").write_text(to_hans(js),encoding="utf-8")
    # Each issue is a durable snapshot; build all legacy issues on the first
    # migration, thereafter retain unchanged copies unless missing.
    src_today=(root/"index.html").read_text(encoding="utf-8")
    src_dir=(archive_dir/"index.html").read_text(encoding="utf-8")
    built=0
    for locale in LOCALES:
        lang_dir=root/locale
        (lang_dir/"archive").mkdir(parents=True,exist_ok=True)
        for kind,source,location in [
            ("home",src_today,lang_dir/"index.html"),
            ("directory",src_dir,lang_dir/"archive/index.html"),
        ]:
            issue=issues[date]
            rendered=render(source,locale,kind,base,date,
                data.get("headline",""),data.get("headline_en",""),issue["total"])
            location.write_text(rendered,encoding="utf-8")
            built+=1
        for archive in manifest:
            issue_date=archive["date"]
            target=lang_dir/"archive"/(issue_date+".html")
            if target.is_file() and issue_date!=date:
                continue
            source=(archive_dir/(issue_date+".html")).read_text(encoding="utf-8")
            html_output=render(source,locale,"issue",base,issue_date,
                archive.get("title",""),archive.get("title_en",""),archive["total"])
            target.write_text(html_output,encoding="utf-8")
            built+=1
    # Sitemap includes only real published language routes; three-way hreflang
    # groups include the source language as recommended by Google Search Central.
    ns="http://www.sitemaps.org/schemas/sitemap/0.9"
    xhtml="http://www.w3.org/1999/xhtml"
    ET.register_namespace("",ns)
    ET.register_namespace("xhtml",xhtml)
    rootxml=ET.Element("{"+ns+"}urlset")
    for kind,dt in [("home",date),("directory",date)]+[("issue",issue["date"]) for issue in manifest]:
        for locale in LOCALES:
            el=ET.SubElement(rootxml,"{"+ns+"}url")
            ET.SubElement(el,"{"+ns+"}loc").text=locale_url(base,locale,kind,dt)
            if kind!="directory":
                ET.SubElement(el,"{"+ns+"}lastmod").text=dt
            for alt,code in LOCALES.items():
                ET.SubElement(el,"{"+xhtml+"}link",{
                    "rel":"alternate","hreflang":code,
                    "href":locale_url(base,alt,kind,dt)})
    ET.ElementTree(rootxml).write(root/"sitemap.xml",encoding="utf-8",xml_declaration=True)
    (root/"robots.txt").write_text("User-agent: *\\nAllow: /\\nSitemap: "+
        base.rstrip("/")+"/sitemap.xml\\n",encoding="utf-8")
    print(f"PASS localized: {built} generated files, {len(manifest)} issues across three languages, current {date}")

if __name__=="__main__":
    main()
