#!/usr/bin/env python3
"""CouncilLens — analyse stage.

Reads data/processed/manifest.json (canonical records with extracted text),
summarises each document, lines up feedback -> decision -> outcome, attaches a
linkage tier (🟢/🟡/⚪) to every relationship, and writes the analysis artifact to
data/analysis/<topic>.json (validated against data/schemas/analysis.schema.json)
plus a readable Markdown digest alongside it.

This is the council-agnostic topic pipeline (docs/architecture.md): it runs only
on canonical records, so it behaves identically for every council. There is no
per-council logic here — that is the whole point.

It is also deterministic: AI summaries come from the versioned cache
(data/ai-cache), never from a live model call, and no wall-clock time is written
into the output. The same inputs always produce byte-for-byte identical output, so
the published site can be regenerated from cached outputs plus raw inputs.

Run locally:
    pip install -r requirements.txt
    python src/ingest/fetch.py        # produces data/raw/manifest.json
    python src/transform/extract.py   # produces data/processed/manifest.json
    python src/analyse/analyse.py     # produces data/analysis/<topic>.json + .md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract  # noqa: E402
import linkage  # noqa: E402
import summarise  # noqa: E402
from digest import render_digest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_MANIFEST = ROOT / "data" / "processed" / "manifest.json"
AI_CACHE_DIR = ROOT / "data" / "ai-cache"
ANALYSIS_DIR = ROOT / "data" / "analysis"

PIPELINE_VERSION = "analyse-1"
_STAGES = ("feedback", "decision", "outcome")


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "topic"


def analyse(manifest, cache_dir):
    """Pure transform: processed manifest -> analysis artifact. No I/O of its own."""
    documents = manifest.get("documents", [])
    by_stage = {stage: [] for stage in _STAGES}
    coverage = {stage: 0 for stage in _STAGES}
    coverage["unstaged"] = 0

    analysed = []
    for record in documents:
        stage = record.get("stage")
        if stage in by_stage:
            by_stage[stage].append(record)
            coverage[stage] += 1
        else:
            stage = None
            coverage["unstaged"] += 1
        analysed.append(
            {
                "id": record["id"],
                "title": record.get("title", record["id"]),
                "stage": stage,
                "type": record.get("type", "unknown"),
                "source_url": record["source_url"],
                "sha256": record["sha256"],
                "summary": summarise.summary_for(record, cache_dir),
            }
        )

    return {
        "council": manifest.get("council"),
        "topic": manifest.get("topic"),
        "pipeline_version": PIPELINE_VERSION,
        "prompt_version": summarise.PROMPT_VERSION,
        "coverage": coverage,
        "documents": analysed,
        "linkages": linkage.build_linkages(by_stage),
    }


def _report(analysis):
    for doc in analysis["documents"]:
        summary = doc["summary"]
        stage = doc["stage"] or "unstaged"
        print(f"  ok    {stage}/{doc['id']} [{summary['method']}] "
              f"{len(summary['text'])} chars ({summary['review']})")
    for link in analysis["linkages"]:
        pair = f"{link['from_id'] or '—'} -> {link['to_id'] or '—'}"
        print(f"  {link['symbol']} {link['tier']:9} {pair}")


def main():
    if not PROCESSED_MANIFEST.exists():
        print("No processed manifest. Run the transform stage first.")
        return 0
    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("documents"):
        print("Processed manifest has no documents.")
        return 0

    print(f"Council: {manifest.get('council')!r}  Topic: {manifest.get('topic')!r}")
    analysis = analyse(manifest, AI_CACHE_DIR)

    try:
        contract.validate_analysis(analysis)
    except ValueError as exc:
        print(exc)
        return 1

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(analysis["topic"])
    json_path = ANALYSIS_DIR / f"{slug}.json"
    md_path = ANALYSIS_DIR / f"{slug}.md"
    json_path.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_digest(analysis), encoding="utf-8")

    _report(analysis)
    cov = analysis["coverage"]
    print(
        f"Wrote {json_path.relative_to(ROOT)} and {md_path.relative_to(ROOT)} — "
        f"{len(analysis['documents'])} document(s), {len(analysis['linkages'])} "
        f"linkage(s) [feedback {cov['feedback']} · decision {cov['decision']} · "
        f"outcome {cov['outcome']}]."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
