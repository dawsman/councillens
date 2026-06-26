#!/usr/bin/env python3
"""Linkage tiers — the honest heart of CouncilLens.

The hardest question in accountability is whether feedback actually changed a
decision. Usually nobody writes that down. So instead of guessing we label every
feedback -> decision (and decision -> outcome) relationship with a tier, and we
default *down* unless the records prove otherwise:

    🟢 confirmed  — the later record cites the earlier source. Provable.
    🟡 possible   — same topic, configured stage roles, but no citation found.
                    The relationship is documented; the causation is not.
    ⚪ none        — nothing to link to (e.g. no decision yet — "still waiting").

This logic is deliberately deterministic and rule-based, not AI: the tier is the
load-bearing claim of the whole project, so it must be auditable. Every tier
records the evidence it rests on so a reviewer (and a resident) can check it.

Only 🟢 asserts influence, and it only fires on an explicit citation — so we never
imply a connection we cannot evidence.
"""
from __future__ import annotations

SYMBOLS = {"confirmed": "🟢", "possible": "🟡", "none": "⚪"}

# feedback -> decision -> outcome. We link across each adjacent step.
TRANSITIONS = [("feedback", "decision"), ("decision", "outcome")]

_SNIPPET_PAD = 100


def _collapse(text):
    """Collapse whitespace but keep the original case (for readable citation quotes)."""
    return " ".join((text or "").split())


def _normalise(text):
    return _collapse(text).lower()


def _url_needle(url):
    """The host + path of a URL, normalised, with scheme/query/fragment dropped.

    A later record that quotes the earlier source's address is citing it. Matching
    on host+path is conservative: a passing topical word will not trigger it.
    """
    needle = _normalise(url)
    for scheme in ("https://", "http://"):
        if needle.startswith(scheme):
            needle = needle[len(scheme):]
            break
    for cut in ("?", "#"):
        if cut in needle:
            needle = needle.split(cut, 1)[0]
    return needle.rstrip("/")


def _snippet(haystack, index, length):
    start = max(0, index - _SNIPPET_PAD)
    end = min(len(haystack), index + length + _SNIPPET_PAD)
    snippet = haystack[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(haystack):
        snippet = snippet + "…"
    return snippet


def find_citation(from_record, to_text):
    """Return {matched_on, snippet} if `to_text` cites `from_record`, else None.

    Conservative on purpose — two strong signals only, to keep 🟢 trustworthy:
      - the earlier source's URL (host + path) appears in the later text, or
      - the earlier document's full title appears in the later text.
    A single shared keyword is NOT enough; that is what 🟡 is for.
    """
    display = _collapse(to_text)
    hay = display.lower()
    if not hay:
        return None

    # Match case-insensitively, but quote the snippet from the original-case text.
    # _collapse() and .lower() both preserve length, so indices line up.
    url_needle = _url_needle(from_record.get("source_url", ""))
    if url_needle and url_needle in hay:
        return {"matched_on": "source_url", "snippet": _snippet(display, hay.find(url_needle), len(url_needle))}

    title_needle = _normalise(from_record.get("title", ""))
    if len(title_needle) >= 12 and title_needle in hay:
        return {"matched_on": "title", "snippet": _snippet(display, hay.find(title_needle), len(title_needle))}

    return None


def link_pair(from_record, to_record, from_stage, to_stage):
    """Tier a single (earlier, later) document pair on the same topic."""
    citation = find_citation(from_record, to_record.get("text", ""))
    if citation is not None:
        return {
            "from_stage": from_stage,
            "to_stage": to_stage,
            "from_id": from_record["id"],
            "to_id": to_record["id"],
            "tier": "confirmed",
            "symbol": SYMBOLS["confirmed"],
            "reason": (
                f"The {to_stage} record cites the {from_stage} source "
                f"(matched on {citation['matched_on']}), so the records themselves "
                f"document the connection."
            ),
            "evidence": {"citation": citation["snippet"], "matched_on": citation["matched_on"]},
            "review": "pending",
        }
    return {
        "from_stage": from_stage,
        "to_stage": to_stage,
        "from_id": from_record["id"],
        "to_id": to_record["id"],
        "tier": "possible",
        "symbol": SYMBOLS["possible"],
        "reason": (
            f"Both concern the same topic and are configured as {from_stage} → "
            f"{to_stage}, but no citation of the {from_stage} was found in the "
            f"{to_stage} record. We do not claim the {from_stage} shaped the "
            f"{to_stage}."
        ),
        "evidence": {
            "basis": "same topic; configured stage roles; no citation found",
            # Fetch times, not document publication dates (the canonical record does
            # not yet carry document dates). Shown for transparency, not relied on
            # for precedence — that is why this stays 🟡, never 🟢.
            "from_fetched_at": from_record.get("fetched_at"),
            "to_fetched_at": to_record.get("fetched_at"),
        },
        "review": "pending",
    }


def gap_link(from_stage, to_stage):
    """A ⚪ 'no link found' row when the later stage has no documents yet.

    This is the resident-facing 'still waiting' signal: people gave feedback (or a
    decision was taken) but the next step is not on the record yet.
    """
    return {
        "from_stage": from_stage,
        "to_stage": to_stage,
        "from_id": None,
        "to_id": None,
        "tier": "none",
        "symbol": SYMBOLS["none"],
        "reason": (
            f"No {to_stage} document was found for this topic yet — no link found "
            f"(still waiting)."
        ),
        "evidence": {"basis": f"no {to_stage} document present"},
        "review": "pending",
    }


def build_linkages(by_stage):
    """Build every linkage for one topic from documents grouped by stage.

    For each adjacent step: if both stages have documents, tier every pair; if the
    earlier stage has documents but the later stage is empty, record one ⚪ gap.
    """
    linkages = []
    for from_stage, to_stage in TRANSITIONS:
        froms = by_stage.get(from_stage, [])
        tos = by_stage.get(to_stage, [])
        if froms and not tos:
            linkages.append(gap_link(from_stage, to_stage))
            continue
        for from_record in froms:
            for to_record in tos:
                linkages.append(link_pair(from_record, to_record, from_stage, to_stage))
    return linkages
