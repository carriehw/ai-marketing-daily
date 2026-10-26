"""Shared, static author/contact furniture for current and archived editions.

Keep biography and contact details outside daily data.json so routine news
updates cannot discard them. Historical news remains unchanged: only the
bounded author section and its stylesheet link are refreshed.
"""
import html
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

LINKEDIN = "https://www.linkedin.com/in/carriehuiww/"
EMAIL = "carrie.hui@i-click.com"
START = "<!-- author-profile:start -->"
END = "<!-- author-profile:end -->"

COPY = {
    "zh-hant": {
        "label": "關於 Carrie",
        "name": "Carrie Hui 許媛",
        "role": "AI × Marketing｜行業觀察與應用",
        "bio": "超過14年廣告經驗，現職於AI Marketing Agent初創公司，從數碼廣告與客戶管理的角度，整理 AI 趨勢及行銷動態，分享對品牌、代理商與團隊的實際啟示。",
        "heading": "讓資訊，成為下一步的起點。",
        "invitation": "想為公司訂製定期行業簡報，或探索適合業務的AI 解決方案？歡迎聯絡我，交流你的想法與需要。",
        "contact": "聯絡 Carrie",
        "linkedin": "LinkedIn（新視窗開啟）",
    },
    "en": {
        "label": "About Carrie",
        "name": "Carrie Hui 許媛",
        "role": "AI × Marketing | Industry insights & applications",
        "bio": "With over 14 years of advertising experience, I now work at an AI Marketing Agent startup. I bring a digital advertising and account management perspective to AI trends and marketing developments, sharing practical implications for brands, agencies and teams.",
        "heading": "Let information inspire your next step.",
        "invitation": "Looking for a regular industry briefing tailored to your company, or AI solutions suited to your business? Get in touch to discuss your ideas and needs.",
        "contact": "Contact Carrie",
        "linkedin": "LinkedIn (opens in a new tab)",
    },
    "zh-hans": {
        "label": "关于 Carrie",
        "name": "Carrie Hui 许媛",
        "role": "AI × Marketing｜行业观察与应用",
        "bio": "拥有超过14年广告行业经验，目前就职于一家 AI Marketing Agent 初创公司。我从数字广告与客户管理的视角，梳理 AI 趋势及营销动态，分享对品牌、广告代理公司与团队的实际启发。",
        "heading": "让信息，成为下一步的起点。",
        "invitation": "希望为公司定制定期行业简报，或探索适合业务的 AI 解决方案？欢迎联系我，交流你的想法与需求。",
        "contact": "联系 Carrie",
        "linkedin": "LinkedIn（在新窗口中打开）",
    },
}


def asset_base(site_url):
    path = urlsplit(site_url).path or "/"
    return path if path.endswith("/") else path.rsplit("/", 1)[0] + "/"


def render_profile(site_url, locale=None):
    """None retains the legacy page's CSS language toggle; locales are static."""
    def text(key):
        if locale:
            return html.escape(COPY[locale][key])
        return ('<span class="l-zh">' + html.escape(COPY["zh-hant"][key]) +
                '</span><span class="l-en">' + html.escape(COPY["en"][key]) + '</span>')

    base = asset_base(site_url)
    mailto = "mailto:" + EMAIL + "?subject=" + quote("AI Marketing enquiry", safe="")
    linkedin_label = COPY[locale or "en"]["linkedin"]
    return f'''{START}
<section class="author-profile wrap" id="about-carrie" aria-labelledby="author-profile-name">
  <div class="author-profile-card">
    <img class="author-profile-photo" src="{html.escape(base)}assets/carrie-hui.jpeg" alt="{html.escape(COPY[locale or 'zh-hant']['name'])}" width="1280" height="1946" loading="lazy" decoding="async">
    <div class="author-profile-content">
      <p class="author-profile-label">{text('label')}</p>
      <h2 id="author-profile-name">{text('name')}</h2>
      <p class="author-profile-role">{text('role')}</p>
      <p class="author-profile-bio">{text('bio')}</p>
      <div class="author-profile-invitation">
        <h3>{text('heading')}</h3>
        <p>{text('invitation')}</p>
        <div class="author-profile-actions">
          <a class="author-profile-contact" href="{html.escape(mailto, quote=True)}">{text('contact')}<span aria-hidden="true">↗</span></a>
          <a class="author-profile-linkedin" href="{LINKEDIN}" target="_blank" rel="noopener noreferrer" aria-label="{html.escape(linkedin_label, quote=True)}">LinkedIn<span aria-hidden="true">↗</span></a>
        </div>
      </div>
    </div>
  </div>
</section>
{END}'''


def with_author_profile(page, site_url, locale=None):
    # BeautifulSoup may serialize attributes with a different order; match by ID.
    page = re.sub(r'<link\b[^>]*\bid=["\']author-profile-css["\'][^>]*>\s*',
                  '', page, flags=re.I)
    page = re.sub(re.escape(START) + r'.*?' + re.escape(END) + r'\s*',
                  '', page, flags=re.S)
    css = html.escape(asset_base(site_url) + "author-profile.css", quote=True)
    link = f'<link id="author-profile-css" rel="stylesheet" href="{css}">\n'
    if not re.search(r'</head\s*>', page, re.I) or not re.search(r'<footer\b', page, re.I):
        raise ValueError("Author profile requires an HTML head and site footer")
    page = re.sub(r'</head\s*>', lambda _: link + '</head>', page, count=1, flags=re.I)
    return re.sub(r'<footer\b', lambda _: render_profile(site_url, locale) + '\n<footer',
                  page, count=1, flags=re.I)


def refresh_profiles(root, site_url):
    """Update page furniture on every published route, without rebuilding stories."""
    root = Path(root)
    updated = 0
    for prefix, locale in (("", None), ("en", "en"),
                           ("zh-hant", "zh-hant"), ("zh-hans", "zh-hans")):
        directory = root / prefix
        pages = [directory / "index.html", *sorted((directory / "archive").glob("*.html"))]
        for path in pages:
            if not path.is_file():
                continue
            before = path.read_text(encoding="utf-8")
            after = with_author_profile(before, site_url, locale)
            if after != before:
                path.write_text(after, encoding="utf-8")
                updated += 1
    return updated
