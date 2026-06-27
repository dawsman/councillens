#!/usr/bin/env python3
"""Tests for the publish stage.

Checks the resident-facing guarantees: every claim links to its source, all three
linkage tiers render with their labels, the 'still waiting' signal shows, and text
is HTML-escaped. Synthetic data only.

    python tests/test_publish.py        # or: pytest tests/test_publish.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "analyse"))
sys.path.insert(0, str(ROOT / "src" / "publish"))
sys.path.insert(0, str(ROOT / "tests"))

import analyse  # noqa: E402
import build_site  # noqa: E402
from test_analyse import make_manifest  # noqa: E402


def _build(manifest):
    """Run analyse on a manifest, then publish, returning the topic + index HTML."""
    with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as work:
        analysis = analyse.analyse(manifest, cache)
        analysis_dir = Path(work) / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "topic.json").write_text(json.dumps(analysis), encoding="utf-8")
        site_dir = Path(work) / "_site"
        build_site.build(analysis_dir=analysis_dir, site_dir=site_dir)
        return (
            (site_dir / "topic.html").read_text(encoding="utf-8"),
            (site_dir / "index.html").read_text(encoding="utf-8"),
            analysis,
        )


def test_links_every_document_to_source():
    topic, _, analysis = _build(make_manifest())
    for doc in analysis["documents"]:
        assert f'href="{doc["source_url"]}"' in topic, f"missing source link for {doc['id']}"


def test_renders_all_three_tiers():
    topic, _, _ = _build(make_manifest())
    assert "🟢 Confirmed" in topic
    assert "🟡 Possible" in topic
    assert "⚪ No link found" in topic


def test_shows_still_waiting():
    topic, index, _ = _build(make_manifest())
    assert "Still waiting" in topic
    assert "Still waiting" in index  # the index surfaces it too


def test_index_lists_topic():
    _, index, analysis = _build(make_manifest())
    assert analysis["topic"] in index
    assert 'href="topic.html"' in index


def test_escapes_html():
    manifest = make_manifest()
    manifest["documents"][0]["title"] = "Cafés & <script>alert(1)</script>"
    topic, _, _ = _build(manifest)
    assert "<script>alert(1)</script>" not in topic
    assert "&lt;script&gt;" in topic


def test_draft_summaries_are_flagged():
    topic, _, _ = _build(make_manifest())
    # extractive fallbacks must be visibly marked, never passed off as finished.
    assert "Draft summary" in topic


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
