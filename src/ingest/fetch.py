#!/usr/bin/env python3
"""CouncilLens — ingest stage.

Reads config/sources.yaml, runs the right ADAPTER for each enabled source,
validates every record against the contract (data/schemas/document.schema.json),
and writes data/raw/manifest.json.

One pipeline, every council. Council-specific detail lives in config and in
platform adapters — never in this file.

Run locally:
    pip install -r requirements.txt
    python src/ingest/fetch.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical  # noqa: E402
from adapters import get_adapter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"
PLACEHOLDER = "REPLACE_ME"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"No config at {CONFIG_PATH} — nothing to do.")
        return None, None, []
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return data.get("council"), data.get("topic"), data.get("sources", []) or []


def main():
    council, topic, sources = load_config()
    if PLACEHOLDER in str(council) or PLACEHOLDER in str(topic):
        print("Config still has placeholders. Set the real council and topic first.")
        return 0

    enabled = [s for s in sources if s.get("enabled") and PLACEHOLDER not in s.get("url", "")]
    if not enabled:
        print("No enabled sources yet. Edit config/sources.yaml.")
        return 0

    print(f"Council: {council!r}  Topic: {topic!r}")
    records = []
    failures = 0
    for source in enabled:
        adapter = get_adapter(source.get("platform"))
        try:
            produced = adapter.fetch(source, council, topic)
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

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "council": council,
                "topic": topic,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "documents": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} record(s); {failures} rejected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
