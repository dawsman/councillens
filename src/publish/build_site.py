#!/usr/bin/env python3
"""CouncilLens — publish stage.

Reads the analyse-stage artifacts (data/analysis/*.json) and renders a static,
resident-facing website into _site/: one page per topic (the feedback -> decision
-> outcome view, with linkage tiers and a link for every claim) plus an index.

Static-first and dependency-free: plain semantic HTML and one stylesheet, no
framework and no JavaScript needed to read it. Deterministic — a pure function of
the analysis artifacts, so the published site regenerates byte-for-byte (the model
is never called here; that already happened, cached, upstream).

Faithful to the methodology: every claim links to its source, every linkage shows
its tier and the reason for it, draft or unreviewed content is labelled as such,
and nothing asserts causation beyond what the records support.

Run locally:
    python src/analyse/analyse.py     # produces data/analysis/<topic>.json
    python src/publish/build_site.py   # produces _site/
    # then open _site/index.html
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "data" / "analysis"
SCHEMA_PATH = ROOT / "data" / "schemas" / "analysis.schema.json"
BANNER_SRC = ROOT / "docs" / "banner.svg"
SITE_DIR = ROOT / "_site"

STAGE_HEADINGS = {
    "feedback": "📣 What people asked for",
    "decision": "🏛️ What the council decided",
    "outcome": "🚧 What actually happened",
}
TIER_WORD = {"confirmed": "Confirmed", "possible": "Possible", "none": "No link found"}
REVIEW_NOTE = {
    "auto-extractive": "Draft summary — auto-generated from the document, awaiting an AI + human review.",
    "no_text": "No text has been extracted from this document yet.",
    "pending": "AI summary — awaiting human review before publishing.",
}


def esc(value):
    return html.escape("" if value is None else str(value))


# --- small HTML helpers -------------------------------------------------------

def _page(title, body):
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        '<link rel="stylesheet" href="style.css">\n'
        "</head>\n<body>\n"
        '<a class="skip" href="#main">Skip to content</a>\n'
        '<header class="site"><a href="index.html">'
        '<img src="banner.svg" alt="CouncilLens — see how your council listens"></a></header>\n'
        f'<main id="main">\n{body}\n</main>\n'
        '<footer class="site">\n'
        "<p>CouncilLens lines up public information so you can see for yourself. "
        "It doesn’t tell you what to think, and it never claims a decision was caused "
        "by feedback unless the records prove it.</p>\n"
        '<p>Summaries and linkages are reviewed by a person before publishing. '
        'Read the <a href="https://github.com/dawsman/councillens/blob/main/methodology/README.md">methodology</a>. '
        "Spotted a mistake? <a href=\"https://github.com/dawsman/councillens/issues\">Tell us</a>.</p>\n"
        "</footer>\n</body>\n</html>\n"
    )


def _coverage_chips(coverage):
    labels = [("feedback", "📣 Feedback"), ("decision", "🏛️ Decision"), ("outcome", "🚧 Outcome")]
    chips = "".join(
        f'<span class="chip"><b>{coverage[key]}</b> {esc(label)}</span>' for key, label in labels
    )
    waiting = [name for name in ("feedback", "decision", "outcome") if coverage[name] == 0]
    note = ""
    if waiting:
        joined = " and no ".join(waiting)
        note = f'<p class="waiting">⚪ <b>Still waiting</b> — no {esc(joined)} document on the record yet.</p>'
    return f'<div class="chips">{chips}</div>{note}'


def _tier_key():
    rows = [
        ("confirmed", "🟢", "the council’s own record cites the feedback."),
        ("possible", "🟡", "feedback and decision are on the same topic, but we found no proof one shaped the other — so we don’t claim it."),
        ("none", "⚪", "we didn’t find a connection, and we say so plainly."),
    ]
    items = "".join(
        f'<li><span class="badge tier-{t}">{sym} {esc(TIER_WORD[t])}</span> — {esc(text)}</li>'
        for t, sym, text in rows
    )
    return f'<section class="key"><h2>How to read the labels</h2><ul class="tier-key">{items}</ul></section>'


# --- topic page ---------------------------------------------------------------

def _linkage_card(link, titles):
    frm = titles.get(link["from_id"])
    to = titles.get(link["to_id"])
    if frm and to:
        pair = (
            f'<a href="#doc-{esc(link["from_id"])}">{esc(frm)}</a> → '
            f'<a href="#doc-{esc(link["to_id"])}">{esc(to)}</a>'
        )
    else:
        pair = f'<i>{esc(link["from_stage"])} → {esc(link["to_stage"])}</i>'
    cite = link["evidence"].get("citation")
    cite_html = f'<blockquote class="cited">“{esc(cite)}”</blockquote>' if cite else ""
    return (
        f'<article class="linkage tier-{esc(link["tier"])}">'
        f'<p class="head"><span class="badge tier-{esc(link["tier"])}">{esc(link["symbol"])} '
        f'{esc(TIER_WORD[link["tier"]])}</span> {pair}</p>'
        f'<p class="reason">{esc(link["reason"])}</p>{cite_html}</article>'
    )


def _document_entry(doc):
    summary = doc["summary"]
    text = summary["text"].strip()
    body = f"<p>{esc(text)}</p>" if text else ""
    note = REVIEW_NOTE.get(summary["review"])
    note_html = f'<p class="review">{esc(note)}</p>' if note else ""
    if not text and not note_html:
        body = '<p class="review">No summary available yet.</p>'
    return (
        f'<article class="doc" id="doc-{esc(doc["id"])}">'
        f'<h3><a href="{esc(doc["source_url"])}">{esc(doc["title"])}</a></h3>'
        f'<p class="meta">{esc(doc["type"])} · '
        f'<a href="{esc(doc["source_url"])}">view source</a></p>'
        f"{body}{note_html}</article>"
    )


def render_topic_page(analysis):
    docs = analysis["documents"]
    titles = {doc["id"]: doc["title"] for doc in docs}

    linkages = analysis["linkages"]
    if linkages:
        linkage_html = "".join(_linkage_card(link, titles) for link in linkages)
    else:
        linkage_html = '<p class="empty">No feedback, decision or outcome documents to compare yet.</p>'

    sections = []
    by_stage = {"feedback": [], "decision": [], "outcome": [], None: []}
    for doc in docs:
        by_stage.setdefault(doc["stage"], []).append(doc)
    for stage in ("feedback", "decision", "outcome"):
        entries = by_stage.get(stage, [])
        inner = (
            "".join(_document_entry(doc) for doc in entries)
            if entries
            else '<p class="empty">Nothing on the record for this step yet.</p>'
        )
        sections.append(f'<section class="stage"><h2>{esc(STAGE_HEADINGS[stage])}</h2>{inner}</section>')
    extras = by_stage.get(None, [])
    if extras:
        inner = "".join(_document_entry(doc) for doc in extras)
        sections.append(f'<section class="stage"><h2>📄 Other documents</h2>{inner}</section>')

    body = (
        f'<p class="crumb"><a href="index.html">← All topics</a></p>'
        f'<h1>{esc(analysis["topic"])}</h1>'
        f'<p class="council">{esc(analysis["council"])}</p>'
        '<p class="lede">What people asked for, what the council decided, and what '
        "actually happened — in plain English, with a link for every claim.</p>"
        f'<section class="glance"><h2>At a glance</h2>{_coverage_chips(analysis["coverage"])}</section>'
        f'<section class="linkages"><h2>How feedback lines up with decisions</h2>{linkage_html}</section>'
        f'{"".join(sections)}'
        f"{_tier_key()}"
    )
    return _page(f'{analysis["topic"]} — CouncilLens', body)


# --- index page ---------------------------------------------------------------

def _index_row(analysis, href):
    cov = analysis["coverage"]
    return (
        f'<li class="topic-card"><a href="{esc(href)}">'
        f'<span class="topic-title">{esc(analysis["topic"])}</span></a>'
        f'<p class="meta">{esc(analysis["council"])}</p>'
        f"{_coverage_chips(cov)}</li>"
    )


def render_index(analyses):
    by_council = {}
    for analysis, href in analyses:
        by_council.setdefault(analysis["council"], []).append((analysis, href))

    blocks = []
    for council in sorted(by_council):
        rows = "".join(
            _index_row(analysis, href)
            for analysis, href in sorted(by_council[council], key=lambda a: a[0]["topic"])
        )
        blocks.append(f'<section class="council-block"><h2>{esc(council)}</h2><ul class="topics">{rows}</ul></section>')

    if not blocks:
        blocks.append('<p class="empty">No topics published yet. Run the analyse stage first.</p>')

    body = (
        "<h1>See how your council listens</h1>"
        '<p class="lede">CouncilLens lines up what people asked for, what the council '
        "decided, and what actually happened — with a link for every claim.</p>"
        f'{"".join(blocks)}'
        f"{_tier_key()}"
    )
    return _page("CouncilLens", body)


# --- build --------------------------------------------------------------------

def _validate(artifact):
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(artifact)


def build(analysis_dir=ANALYSIS_DIR, site_dir=SITE_DIR):
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "style.css").write_text(STYLESHEET, encoding="utf-8")
    if BANNER_SRC.exists():
        shutil.copyfile(BANNER_SRC, site_dir / "banner.svg")

    analyses = []
    for path in sorted(analysis_dir.glob("*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        _validate(artifact)
        href = f"{path.stem}.html"
        (site_dir / href).write_text(render_topic_page(artifact), encoding="utf-8")
        analyses.append((artifact, href))
        print(f"  ok    {href}  [{artifact['council']} — {artifact['topic']}]")

    (site_dir / "index.html").write_text(render_index(analyses), encoding="utf-8")
    try:
        shown = site_dir.relative_to(ROOT)
    except ValueError:
        shown = site_dir
    print(f"Wrote {len(analyses)} topic page(s) + index to {shown}/")
    return len(analyses)


def main():
    if not ANALYSIS_DIR.exists() or not any(ANALYSIS_DIR.glob("*.json")):
        print("No analysis artifacts. Run the analyse stage first.")
        return 0
    build()
    return 0


STYLESHEET = """\
:root {
  --teal: #0F5C6B; --teal-dark: #0B2D37; --teal-mid: #127D86;
  --bg: #F4FAFB; --panel: #FFFFFF; --line: #D4ECF0;
  --green: #06D6A0; --amber: #FFB703; --grey: #9FCAD2;
  --ink: #0B2D37; --muted: #4A6b73;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.skip { position: absolute; left: -999px; }
.skip:focus { left: 8px; top: 8px; background: #fff; padding: 8px; z-index: 10; }
header.site { background: var(--teal-dark); padding: 0; line-height: 0; }
header.site img { width: 100%; max-height: 200px; object-fit: cover; display: block; }
main { max-width: 760px; margin: 0 auto; padding: 28px 20px 8px; }
h1 { font-size: 2rem; line-height: 1.2; margin: 12px 0 4px; color: var(--teal-dark); }
h2 { font-size: 1.2rem; margin: 32px 0 12px; color: var(--teal); }
h3 { font-size: 1.05rem; margin: 0 0 4px; }
a { color: var(--teal-mid); }
.crumb { margin: 0 0 8px; } .crumb a { text-decoration: none; }
.council, .meta { color: var(--muted); }
.council { font-weight: 600; margin: 0 0 16px; }
.lede { font-size: 1.15rem; color: var(--teal-dark); }
.chips { display: flex; flex-wrap: wrap; gap: 10px; margin: 8px 0; }
.chip { background: var(--panel); border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; }
.chip b { color: var(--teal); font-size: 1.1rem; }
.waiting { background: #FFF8E8; border-left: 4px solid var(--amber); padding: 10px 14px; border-radius: 6px; }
.linkage { background: var(--panel); border: 1px solid var(--line); border-left-width: 6px; border-radius: 8px; padding: 14px 16px; margin: 12px 0; }
.linkage.tier-confirmed { border-left-color: var(--green); }
.linkage.tier-possible { border-left-color: var(--amber); }
.linkage.tier-none { border-left-color: var(--grey); }
.linkage .head { margin: 0 0 6px; }
.linkage .reason { margin: 6px 0 0; }
.badge { display: inline-block; font-weight: 700; font-size: .8rem; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.tier-confirmed.badge { background: #E2FBF3; color: #045f47; }
.tier-possible.badge { background: #FFF3D6; color: #7a5600; }
.tier-none.badge { background: #EAF3F5; color: #3a5a62; }
.cited { margin: 8px 0 0; padding: 8px 12px; background: var(--bg); border-radius: 6px; color: var(--muted); font-size: .95rem; }
.doc { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; margin: 12px 0; }
.doc .meta { font-size: .85rem; margin: 0 0 8px; }
.review { color: #7a5600; background: #FFF8E8; padding: 6px 10px; border-radius: 6px; font-size: .9rem; margin: 8px 0 0; }
.empty { color: var(--muted); font-style: italic; }
.tier-key { list-style: none; padding: 0; } .tier-key li { margin: 8px 0; }
.topics { list-style: none; padding: 0; }
.topic-card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin: 12px 0; }
.topic-title { font-size: 1.15rem; font-weight: 700; }
footer.site { max-width: 760px; margin: 24px auto 0; padding: 20px; color: var(--muted); font-size: .9rem; border-top: 1px solid var(--line); }
"""


if __name__ == "__main__":
    raise SystemExit(main())
