#!/usr/bin/env python3
"""Render an analysis artifact into a plain-English digest a resident can read.

This is a readable *preview* of the analysis, generated deterministically from the
analysis JSON. Final, styled publishing is the publish stage's job; this exists so
the analyse stage produces something legible the moment it runs.

It states the project's three questions in order — what people asked for, what the
council decided, what happened — labels every connection with its tier, and links
every claim back to its source. Nothing here asserts more than the linkage tiers do.
"""
from __future__ import annotations

STAGE_HEADINGS = {
    "feedback": "📣 What people asked for",
    "decision": "🏛️ What the council decided",
    "outcome": "🚧 What actually happened",
}
TIER_WORD = {"confirmed": "Confirmed", "possible": "Possible", "none": "No link found"}
REVIEW_NOTE = {
    "auto-extractive": "_Draft summary — auto-generated from the document, awaiting an AI + human pass._",
    "no_text": "_No text has been extracted from this document yet._",
    "pending": "_AI summary — awaiting human review before publishing._",
}


def _doc_by_id(analysis):
    return {doc["id"]: doc for doc in analysis["documents"]}


def _summary_block(doc):
    summary = doc["summary"]
    note = REVIEW_NOTE.get(summary["review"])
    text = summary["text"].strip()
    lines = []
    if text:
        lines.append(text)
    if note:
        lines.append(note)
    if not lines:
        lines.append("_No summary available yet._")
    return "\n\n".join(lines)


def _render_documents(analysis):
    by_stage = {"feedback": [], "decision": [], "outcome": [], None: []}
    for doc in analysis["documents"]:
        by_stage.setdefault(doc["stage"], []).append(doc)

    parts = []
    for stage in ("feedback", "decision", "outcome"):
        docs = by_stage.get(stage, [])
        parts.append(f"### {STAGE_HEADINGS[stage]}")
        if not docs:
            parts.append("_Nothing on the record for this step yet._")
            continue
        for doc in docs:
            parts.append(f"**[{doc['title']}]({doc['source_url']})**")
            parts.append(_summary_block(doc))
        # blank line between stages handled by join
    extras = by_stage.get(None, [])
    if extras:
        parts.append("### 📄 Other documents")
        for doc in extras:
            parts.append(f"**[{doc['title']}]({doc['source_url']})**")
            parts.append(_summary_block(doc))
    return "\n\n".join(parts)


def _render_linkages(analysis, docs):
    if not analysis["linkages"]:
        return "_No feedback, decision or outcome documents to compare yet._"
    rows = []
    for link in analysis["linkages"]:
        frm = docs.get(link["from_id"], {}).get("title") if link["from_id"] else None
        to = docs.get(link["to_id"], {}).get("title") if link["to_id"] else None
        if frm and to:
            pair = f"**{frm}** → **{to}**"
        else:
            pair = f"_{link['from_stage']} → {link['to_stage']}_"
        rows.append(f"{link['symbol']} **{TIER_WORD[link['tier']]}** — {pair}")
        rows.append(f"> {link['reason']}")
        citation = link["evidence"].get("citation")
        if citation:
            rows.append(f"> Cited: “{citation}”")
    return "\n\n".join(rows)


def _coverage_line(coverage):
    bits = [
        f"📣 Feedback: {coverage['feedback']}",
        f"🏛️ Decision: {coverage['decision']}",
        f"🚧 Outcome: {coverage['outcome']}",
    ]
    line = " · ".join(bits)
    waiting = [name for name in ("feedback", "decision", "outcome") if coverage[name] == 0]
    if waiting:
        line += f"\n\n> ⚪ Still waiting: no { ' and no '.join(waiting) } document on the record yet."
    return line


def render_digest(analysis):
    """Return a Markdown digest string for one analysis artifact."""
    docs = _doc_by_id(analysis)
    out = [
        f"# {analysis['topic']}",
        f"**{analysis['council']}**",
        "What people asked for, what the council decided, and what actually "
        "happened — in plain English, with a link for every claim.",
        "## At a glance",
        _coverage_line(analysis["coverage"]),
        "## How feedback lines up with decisions",
        _render_linkages(analysis, docs),
        "## The documents",
        _render_documents(analysis),
        "## How to read the labels",
        (
            "🟢 **Confirmed** — the council's own record cites the feedback.  \n"
            "🟡 **Possible** — the feedback and the decision are on the same topic, "
            "but we found no proof one shaped the other, so we don't claim it.  \n"
            "⚪ **No link found** — we didn't find a connection, and we say so plainly."
        ),
        (
            "---\n"
            "_CouncilLens lines up public information so you can see for yourself. "
            "It doesn't tell you what to think, and it never claims a decision was "
            "caused by feedback unless the records prove it. "
            "Summaries and linkages are reviewed by a person before they are "
            "published — see the [methodology](../../methodology/README.md)._"
        ),
    ]
    return "\n\n".join(out).strip() + "\n"
