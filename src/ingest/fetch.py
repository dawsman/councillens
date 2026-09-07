#!/usr/bin/env python3
"""CouncilLens — ingest stage.

Reads every config file under config/sources/, runs the right ADAPTER for each
enabled source, validates every record against the contract
(data/schemas/document.schema.json), and writes data/raw/manifest.json.

One pipeline, every council, every topic. Council-specific detail lives in config
and in platform adapters — never in this file.

Run locally:
    pip install -r requirements.txt
    python src/ingest/fetch.py
    python src/ingest/fetch.py --only norwich-city-council/housing-allocations

`--only` re-fetches one topic and replaces just that topic's records in the
manifest. Every other topic's `fetched_at` and `sha256` are left exactly as they
were, so their cached AI outputs stay valid and the repo diff stays small.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical  # noqa: E402
import config as cfg  # noqa: E402
from adapters import get_adapter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def load_existing():
    if not MANIFEST_PATH.exists():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return manifest.get("documents", []) or []


def merge(existing, fresh, replaced_keys):
    """Keep every record whose topic was not re-fetched, in its original order,
    then append this run's records. Untouched topics keep their exact bytes."""
    kept = [
        r for r in existing
        if (cfg.slugify(r.get("council")), cfg.slugify(r.get("topic"))) not in replaced_keys
    ]
    return kept + fresh


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch the configured public source documents.")
    parser.add_argument(
        "--only", metavar="COUNCIL/TOPIC",
        help="Re-fetch one topic only, e.g. norwich-city-council/licensing-policy.",
    )
    args = parser.parse_args(argv)

    try:
        all_topics = cfg.load_topics()
        selected = cfg.load_topics(args.only)
    except ValueError as exc:
        print(exc)
        return 1

    if not all_topics:
        print(f"No config files under {cfg.SOURCES_DIR.relative_to(ROOT)} — nothing to do.")
        return 0

    records = []
    failures = 0
    replaced = set()
    for topic in selected:
        if topic.has_placeholders():
            print(f"{topic.rel_path}: still has placeholders. Set the real council and topic first.")
            continue
        enabled = topic.enabled_sources()
        print(f"Council: {topic.council!r}  Topic: {topic.topic!r}  ({len(enabled)} enabled source(s))")
        if not enabled:
            print(f"  no enabled sources yet — edit {topic.rel_path}.")
        replaced.add((topic.council_slug, topic.topic_slug))
        for source in enabled:
            adapter = get_adapter(source.get("platform"))
            try:
                produced = adapter.fetch(source, topic.council, topic.topic)
            except Exception as exc:
                print(f"  FAIL  {source.get('id')}: fetch error: {exc}")
                failures += 1
                continue
            for record in produced:
                try:
                    canonical.validate_record(record)
                except ValueError as exc:
                    print(f"  DRIFT {source.get('id')}: {exc}")
                    failures += 1
                    continue
                records.append(record)
                print(f"  ok    {record['id']} [{record['platform']}]: {record['bytes']} bytes")

    documents = merge(load_existing(), records, replaced) if args.only else records

    seen = {}
    for record in documents:
        if record["id"] in seen:
            print(f"  DRIFT {record['id']}: two sources share this id "
                  f"({seen[record['id']]} and {record.get('topic')}). Source ids must be unique.")
            failures += 1
        seen[record["id"]] = record.get("topic")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "topics": cfg.topics_index(all_topics),
                "documents": documents,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} record(s) this run; manifest holds {len(documents)}; {failures} rejected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
