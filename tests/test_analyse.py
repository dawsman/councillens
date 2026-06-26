#!/usr/bin/env python3
"""Tests for the analyse stage.

Covers the parts that carry the project's integrity guarantees:
  - the three linkage tiers (🟢 confirmed / 🟡 possible / ⚪ no link found),
  - the conservative citation rule that keeps 🟢 trustworthy,
  - the provenance every summary must carry,
  - byte-for-byte reproducibility of the output,
  - the AI cache taking precedence over the extractive fallback.

The data here is synthetic ("Example Council") and exists only to exercise the
logic — it is not a real council record. Run with either:

    python tests/test_analyse.py        # no dependencies beyond requirements.txt
    pytest tests/test_analyse.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "analyse"))

import analyse  # noqa: E402
import contract  # noqa: E402
import linkage  # noqa: E402
import summarise  # noqa: E402
from digest import render_digest  # noqa: E402

CITED_URL = "https://example-council.gov.uk/consult/skate-ramp"
UNCITED_URL = "https://example-council.gov.uk/petitions/play-areas"


def make_manifest():
    """A topic with two feedback docs, one decision that cites one of them, and no
    outcome yet — so a single run exercises all three tiers."""
    return {
        "council": "Example Council (synthetic)",
        "topic": "New skate ramp in Example Park (illustrative example)",
        "documents": [
            {
                "id": "consultation-skate-ramp",
                "title": "Skate ramp consultation",
                "stage": "feedback",
                "type": "consultation",
                "source_url": CITED_URL,
                "sha256": "sha-feedback-cited",
                "text": (
                    "The consultation ran for six weeks. Most respondents supported a "
                    "new skate ramp in Example Park. Several asked for better lighting "
                    "and a litter bin nearby."
                ),
                "fetched_at": "2026-01-10T09:00:00+00:00",
            },
            {
                "id": "petition-play-areas",
                "title": "Petition for more play areas",
                "stage": "feedback",
                "type": "feedback",
                "source_url": UNCITED_URL,
                "sha256": "sha-feedback-uncited",
                "text": "A petition signed by 240 residents asked for more play areas across the city.",
                "fetched_at": "2026-01-12T09:00:00+00:00",
            },
            {
                "id": "committee-minutes",
                "title": "Community committee minutes, March 2026",
                "stage": "decision",
                "type": "minutes",
                "source_url": "https://example-council.gov.uk/committee/minutes-2026-03",
                "sha256": "sha-decision",
                "text": (
                    "Members considered the responses received via the consultation at "
                    "example-council.gov.uk/consult/skate-ramp. The committee resolved to "
                    "fund the new skate ramp in Example Park, with lighting included."
                ),
                "fetched_at": "2026-03-20T09:00:00+00:00",
            },
        ],
    }


def _link(linkages, from_id, to_id):
    for link in linkages:
        if link["from_id"] == from_id and link["to_id"] == to_id:
            return link
    return None


def test_tiers():
    with tempfile.TemporaryDirectory() as cache:
        analysis = analyse.analyse(make_manifest(), cache)

    assert analysis["coverage"] == {"feedback": 2, "decision": 1, "outcome": 0, "unstaged": 0}

    # 🟢 the decision cites the consultation URL -> confirmed, with the snippet kept.
    confirmed = _link(analysis["linkages"], "consultation-skate-ramp", "committee-minutes")
    assert confirmed["tier"] == "confirmed", confirmed
    assert confirmed["symbol"] == "🟢"
    assert confirmed["evidence"]["matched_on"] == "source_url"
    assert "skate-ramp" in confirmed["evidence"]["citation"]

    # 🟡 the petition is on the same topic but is not cited -> possible, never claimed.
    possible = _link(analysis["linkages"], "petition-play-areas", "committee-minutes")
    assert possible["tier"] == "possible", possible
    assert possible["symbol"] == "🟡"
    assert "do not claim" in possible["reason"].lower()

    # ⚪ no outcome document yet -> a 'still waiting' gap row.
    gap = _link(analysis["linkages"], None, None)
    assert gap["tier"] == "none" and gap["symbol"] == "⚪", gap
    assert gap["from_stage"] == "decision" and gap["to_stage"] == "outcome"


def test_citation_is_conservative():
    feedback = {"source_url": CITED_URL, "title": "Skate ramp consultation"}
    # A merely topical mention (shared keyword) must NOT count as a citation.
    assert linkage.find_citation(feedback, "We talked about skateboarding in general.") is None
    # The source URL appearing in the text is a citation.
    assert linkage.find_citation(feedback, "see example-council.gov.uk/consult/skate-ramp") is not None
    # The full document title appearing in the text is a citation.
    assert linkage.find_citation(feedback, "as raised in the Skate ramp consultation") is not None


def test_summary_provenance():
    with tempfile.TemporaryDirectory() as cache:
        analysis = analyse.analyse(make_manifest(), cache)
    doc = next(d for d in analysis["documents"] if d["id"] == "committee-minutes")
    summary = doc["summary"]
    assert summary["method"] == "extractive"
    assert summary["model"] == summarise.EXTRACTIVE_MODEL
    assert summary["prompt_version"] == summarise.PROMPT_VERSION
    assert summary["source_document_ids"] == ["committee-minutes"]
    assert summary["review"] == "auto-extractive"
    # Timestamp is the source fetch time, not the wall clock (keeps builds reproducible).
    assert summary["generated_at"] == "2026-03-20T09:00:00+00:00"


def test_validates_against_contract():
    with tempfile.TemporaryDirectory() as cache:
        analysis = analyse.analyse(make_manifest(), cache)
    contract.validate_analysis(analysis)  # raises ValueError on drift


def test_reproducible():
    manifest = make_manifest()
    with tempfile.TemporaryDirectory() as cache:
        first = json.dumps(analyse.analyse(manifest, cache), ensure_ascii=False, indent=2)
        second = json.dumps(analyse.analyse(manifest, cache), ensure_ascii=False, indent=2)
    assert first == second, "analyse output must be byte-for-byte reproducible"


def test_cache_takes_precedence():
    with tempfile.TemporaryDirectory() as cache:
        summaries = Path(cache) / "summaries"
        summaries.mkdir(parents=True)
        (summaries / f"sha-decision.{summarise.PROMPT_VERSION}.json").write_text(
            json.dumps(
                {
                    "source_sha256": "sha-decision",
                    "source_document_ids": ["committee-minutes"],
                    "text": "The committee agreed to fund a new skate ramp in Example Park.",
                    "prompt_version": summarise.PROMPT_VERSION,
                    "model": "example-model-v1",
                    "review": "approved",
                    "confidence": "high",
                    "generated_at": "2026-03-21T10:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        analysis = analyse.analyse(make_manifest(), cache)

    doc = next(d for d in analysis["documents"] if d["id"] == "committee-minutes")
    summary = doc["summary"]
    assert summary["method"] == "ai"
    assert summary["review"] == "approved"
    assert summary["model"] == "example-model-v1"
    assert "fund a new skate ramp" in summary["text"]


def test_digest_renders():
    with tempfile.TemporaryDirectory() as cache:
        analysis = analyse.analyse(make_manifest(), cache)
    md = render_digest(analysis)
    assert "# New skate ramp in Example Park (illustrative example)" in md
    assert "🟢" in md and "🟡" in md and "⚪" in md
    assert "Still waiting" in md


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ok    {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
