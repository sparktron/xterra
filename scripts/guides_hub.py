"""Write the second generation's guide hub, wiki/second-gen/vehicle/guides/index.md, from the guide files and that
generation's tree in config/topics.yaml. Run from the repo root after adding or renaming a guide:

    .venv/bin/python scripts/guides_hub.py

A guide whose file name matches a topic slug is listed under that topic's category (and `xw export` links it from
the topic's row in the section index); any other guide is listed under "More". Titles that contain a digit cite [S3].
"""
import yaml
from pathlib import Path

G = Path("wiki/second-gen/vehicle/guides")
topics = yaml.safe_load(open("config/topics.yaml"))["generations"]["second-gen"]["categories"]
slug_cat = {t["slug"]: (cat, t["title"]) for cat, c in topics.items() for t in c["topics"]}
cat_titles = {cat: c["title"] for cat, c in topics.items()}
guides = {}
for f in sorted(G.glob("*.md")):
    if f.name == "index.md":
        continue
    title = next(l[2:].strip() for l in f.read_text().splitlines() if l.startswith("# "))
    guides[f.stem] = title
by_cat = {c: [] for c in cat_titles}
other = []
for slug, title in guides.items():
    (by_cat[slug_cat[slug][0]] if slug in slug_cat else other).append((title, slug))
out = ["# Xterra how-to guides", "", "[Reference home](../index.md) · [Second-gen wiki index](../../index.md)", "",
       "Step-by-step maintenance, repair and upgrade guides for the second-generation (N50, 2005-2015) Xterra only [S1][S2]. They are written by hand from Nissan's factory service manuals and bulletins, cross-checked against owners' write-ups on thenewx.org and xterranation.org. Every step and number cites its source on the guide's own page, and anything no source states is marked [Unverified].", "",
       "Torque, capacity and part-number values drive real repairs. Where Nissan changed a value between model years, the guide gives each manual year's value. When the guides and your own year's manual disagree, the manual wins.", ""]
for cat, title in cat_titles.items():
    items = sorted(by_cat[cat])
    if not items:
        continue
    out += [f"## {title}", ""] + [f"- [{t}]({s}.md)" + (" [S3]" if any(ch.isdigit() for ch in t) else "") for t, s in items] + [""]
if other:
    out += ["## More", ""] + [f"- [{t}]({s}.md)" for t, s in sorted(other)] + [""]
out += ["## How these guides are kept honest", "",
        "- `xw export` never rewrites this folder; it links each guide from its topic's row in the [second-gen wiki index](../../index.md).",
        "- `xw qa` checks every guide: a line that states a number must cite a source listed at the bottom of its page, or say [Unverified]. That checks traceability, not truth.",
        "- Factory service manual torque values are printed on the manual's exploded-view drawings; each guide names the manual year, section and page.",
        "- Forum write-ups from thenewx.org were read from the Internet Archive's copies, because the site blocks automated access.", "",
        "## Sources", "",
        "- [S1] Nissan North America, 2005 Nissan Xterra Press Kit. https://usa.nissannews.com/en-US/releases/release-f82282403bb549d28fdb180ec46bd9d5-2005-nissan-xterra-press-kit-3",
        "- [S2] Nissan North America, 2015 Nissan Xterra Press Kit (overview, at-a-glance, pricing, specifications). https://usa.nissannews.com/en-US/releases/us-2015-nissan-xterra-press-kit",
        "- [S3] Nissan, Xterra service manuals 2005-2015 (engine, transmission, transfer and axle model codes in the guide titles), as cited section by section on each guide. https://www.nicoclub.com/nissan-service-manuals", ""]
(G / "index.md").write_text("\n".join(out))
print(len(guides), "guides;", "uncategorised:", [s for _, s in other])
