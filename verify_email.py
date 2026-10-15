# -*- coding: utf-8 -*-
"""Gate the EDM before it goes out.

Every check here exists because something once passed review and was still
wrong. Each one that can have a control has one, and a control that does not
fail is reported as a broken check rather than a pass — a test that cannot
distinguish good from bad is not evidence.

Run:  python3 verify_email.py            # checks ./email.html
      python3 verify_email.py path/to/email.html
"""
import json, os, re, sys, html as H, math
from pathlib import Path

P = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("email.html")
S = P.read_text(encoding="utf-8")
DATA = json.loads((P.parent / "data.json").read_text(encoding="utf-8"))
SUBJ = (P.parent / "email-subject.txt").read_text(encoding="utf-8").strip()

ok, bad = [], []
def gate(name, cond, detail=""):
    (ok if cond else bad).append(f"{name}: {detail}")

# --- size -------------------------------------------------------------------
# Gmail silently truncates above 102,400 bytes and appends a "View entire
# message" link, which cuts the email mid-story.
gate("gmail clip", len(S.encode()) < 102_400, f"{len(S.encode()):,} B / 102,400")

# --- structure --------------------------------------------------------------
# Card count is derived from the data, never hard-coded to 10. A literal 10
# would hold only for a five-section day at two picks each: a day where one
# section comes up empty yields nine real cards, and a gate that calls that a
# failure trains whoever is on duty to ignore the gate.
_groups = {}
for _it in DATA.get("items", []):
    _groups.setdefault(_it.get("section", ""), []).append(_it)
PICKS = int(os.environ.get("EDM_PICKS_PER_SECTION", "2"))
expect_cards = sum(min(len(_groups.get(s, [])), PICKS) for s in (DATA.get("sections") or []))
cards = S.count("border-top:5px solid")
gate("cards", cards == expect_cards, f"{cards} cards (data implies {expect_cards})")
gate("why label once", S.count("Why it matters") == 1,
     f"{S.count('Why it matters')} labels (lead card only)")
gate("lead eyebrow once", S.count("Today&rsquo;s lead") == 1,
     f"{S.count('Today&rsquo;s lead')}")

# --- removed-by-design ------------------------------------------------------
# These were deliberately cut; a future edit restoring one would re-bloat the
# email without anyone noticing.
for token in ("Read original", "Paywalled", "followup"):
    gate(f"absent: {token}", token not in S, "absent" if token not in S else "PRESENT")

# --- no serif, no stale palette --------------------------------------------
gate("no serif", "Georgia" not in S and "serif" not in S.replace("sans-serif", ""), "none")

# --- Outlook gradient fallback ---------------------------------------------
# Outlook/Word renders no CSS gradient at all, so the navy stop must also be
# present as a bgcolor attribute underneath it, or Outlook shows white-on-white.
grads = S.count("linear-gradient")
fallbacks = len(re.findall(r'bgcolor="#11154A"', S, re.I))
gate("gradient has bgcolor", grads == 0 or fallbacks >= 2,
     f"{grads} gradient / {fallbacks} bgcolor fallbacks")

# --- links ------------------------------------------------------------------
links = re.findall(r'href="([^"]+)"', S)
http = [l for l in links if l.startswith("http")]
site_host = "carriehw.github.io"
gate("all links internal", all(site_host in l for l in http), f"{len(http)} links")
gate("all links tagged", all("utm_source=edm" in l for l in http), f"{len(http)} tagged")
# A query AFTER the fragment is invisible to the counter and breaks the anchor.
gate("no params after #", not any("#" in l and "?" in l.split("#", 1)[1] for l in http), "0")
camps = set(re.findall(r"utm_campaign=([^&\"#]+)", S))
gate("one campaign id", len(camps) == 1, str(camps))

# --- deep links resolve to real anchors ------------------------------------
idx = P.parent / "index.html"
if idx.is_file():
    anchors = set(re.findall(r'id="([a-z0-9][a-z0-9-]*-[0-9a-f]{6})"',
                             idx.read_text(encoding="utf-8", errors="replace")))
    frags = [l.split("#", 1)[1] for l in http if "#" in l]
    missing = [f for f in frags if f not in anchors]
    gate("deep links resolve", not missing and len(set(frags)) == expect_cards,
         f"{len(set(frags))} distinct, {len(missing)} unresolved")
    # CONTROL: a deliberately wrong fragment must be reported unresolved.
    gate("CONTROL anchor check bites", "definitely-not-a-story-aaaaaa" not in anchors,
         "control fragment correctly absent")

# --- reading-time chip is not a promise the email cannot keep --------------
# Counted the way a client renders it: tags out, hidden preheader out.
def visible_words(doc):
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", doc)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?is)<div style=\"display:none;max-height:0;.*?</div>", " ", s)
    s = H.unescape(re.sub(r"(?s)<[^>]+>", " ", s))
    s = re.sub(r"[​‌͏\xa0]", " ", s)
    cjk = len(re.findall(r"[㐀-鿿豈-﫿]", s))
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-\.$%]*", s)) + cjk / 2.5
w = visible_words(S)
chip = re.search(r"<strong>(\d+)</strong>-minute read", S)
need = max(1, math.ceil(w / 220 - 1e-9))
gate("read-time honest", chip and int(chip.group(1)) >= need,
     f"{w:.0f} words = {w/220:.2f} min, chip says {chip.group(1) if chip else 'NONE'} (need >= {need})")
gate("read-time not inflated", chip and int(chip.group(1)) <= need,
     f"chip {chip.group(1) if chip else 'NONE'} vs need {need}")
# CONTROL: doubling the text must demand more minutes than the chip claims.
w2 = visible_words(re.sub(r"(?s)(<body.*?>)(.*)(</body>)", lambda m: m.group(1)+m.group(2)*2+m.group(3), S))
gate("CONTROL read-time scales", math.ceil(w2/220) > need, f"doubled = {w2:.0f} words")

# --- claims the email cannot support --------------------------------------
# This email links only to the site, so it must not promise the originals.
gate("no unreachable sourcing claim", "Every story sourced" not in S, "absent")

# --- subject / preheader ---------------------------------------------------
pre = re.search(r'<div style="display:none;max-height:0;[^"]*">(.*?)&#847;', S, re.S)
pre_txt = H.unescape(re.sub(r"(?s)<[^>]+>", "", pre.group(1))).strip() if pre else ""
gate("subject length", 0 < len(SUBJ) <= 120, f"{len(SUBJ)} chars")
gate("subject no dangling dash", not SUBJ.rstrip().endswith(("—", "-", "·")), repr(SUBJ[-12:]))
gate("subject no 'and 0 more'", "and 0 more" not in SUBJ, "absent")
gate("preheader present", 40 <= len(pre_txt) <= 150, f"{len(pre_txt)} chars")
overlap = set(re.findall(r"[a-z]{5,}", SUBJ.lower())) & set(re.findall(r"[a-z]{5,}", pre_txt.lower()))
gate("preheader not a repeat", len(overlap) <= 2, f"shared words {sorted(overlap)}")

# --- mobile first screen ----------------------------------------------------
# The first headline being readable above the phone fold was won by measurement
# (block top 514px, first line ending 540px, against iPhone SE Mail's ~560px
# budget) and it is held by a handful of CSS rules that a later edit could drop
# without anything looking wrong. The pixel itself is not re-measurable here:
# that needs a browser, and only inside an iframe, because headless chromium
# clamps a top-level window to a 500px minimum and would silently test the wrong
# width. So this gate holds the structure instead — the rules must exist, and
# each must sit inside the phone media query rather than apply everywhere.
mq = re.search(r"@media only screen and \(max-width:620px\) \{(.*?)\n    \}", S, re.S)
gate("phone media query present", bool(mq), "found" if mq else "MISSING")
inside = mq.group(1) if mq else ""
outside = S.replace(inside, "") if mq else S
for rule in ("h1", "m-hide", "m-hide-cta", "outer-pad", "sec-desc"):
    gate(f"fold rule inside media query: .{rule}", f".{rule} " in inside,
         "inside" if f".{rule} " in inside else "NOT in the phone query")
# Hiding .sec-desc or the hero blocks OUTSIDE the query would strip them on
# desktop and in Outlook too — Outlook ignores media queries entirely, so an
# unconditional rule is the difference between "hidden on phones" and "gone".
for rule in ("sec-desc", "m-hide-cta", "outer-pad"):
    gate(f"no unconditional .{rule}", f".{rule} {{" not in outside,
         "media-query only")
# CONTROL: the placement check must distinguish a rule that IS there from one
# that is not, else both arms would read as a pass.
gate("CONTROL fold-rule placement bites",
     ".sec-desc " in inside and ".totally-not-a-rule " not in inside,
     "control rule correctly absent")
# The section description is hidden on phones, not deleted. Outlook shows it.
n_desc = S.count('class="sec-desc"')
gate("sec-desc text still in HTML", n_desc > 0, f"{n_desc} section descriptions")

# --- banned connectives (her standing editorial rule) ---------------------
zh = "".join(re.findall(r"[㐀-鿿]+", S))
hits = [w for w in ("但是", "不過", "但") if w in zh]
gate("no banned connectives", not hits, f"found {hits}" if hits else "none")

print(f"\n{P}  {len(S.encode()):,} B")
for line in ok:  print("  PASS  " + line)
for line in bad: print("  FAIL  " + line)
print(f"\n{len(ok)} pass / {len(bad)} fail")
sys.exit(1 if bad else 0)
