#!/usr/bin/env python3
"""The contract gate.

Validates every artifact the pipeline produces against its schema, and exits
non-zero if anything drifts:

  - the ingest stage (data/raw) and transform stage (data/processed) canonical
    records, against data/schemas/document.schema.json;
  - the analyse stage artifacts (data/analysis/*.json), against
    data/schemas/analysis.schema.json.

The CI workflow runs this on every pull request, so non-conforming output cannot
be merged. One gate, every stage.

Run locally:
    python scripts/validate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_SCHEMA_PATH = ROOT / "data" / "schemas" / "document.schema.json"
ANALYSIS_SCHEMA_PATH = ROOT / "data" / "schemas" / "analysis.schema.json"
MANIFESTS = [
    ROOT / "data" / "raw" / "manifest.json",
    ROOT / "data" / "processed" / "manifest.json",
]
ANALYSIS_DIR = ROOT / "data" / "analysis"


def _report(label, errors):
    if errors:
        print(f"DRIFT  {label}:")
        for err in errors:
            where = "/".join(str(p) for p in err.path) or "(root)"
            print(f"    - {where}: {err.message}")
        return 1
    print(f"ok     {label}")
    return 0


def validate_manifest(path, validator):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    failures = 0
    stage = path.parent.name
    for record in documents:
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        failures += _report(f"{stage}/{record.get('id', '<no id>')}", errors)
    return failures, len(documents)


def validate_analysis(path, validator):
    artifact = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.path))
    failures = _report(f"analysis/{path.stem}", errors)
    return failures, 1


def main():
    document_validator = jsonschema.Draft202012Validator(
        json.loads(DOCUMENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    analysis_validator = jsonschema.Draft202012Validator(
        json.loads(ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8"))
    )

    total_failures = 0
    total_records = 0
    checked_any = False

    for path in MANIFESTS:
        if not path.exists():
            continue
        checked_any = True
        failures, count = validate_manifest(path, document_validator)
        total_failures += failures
        total_records += count

    for path in sorted(ANALYSIS_DIR.glob("*.json")):
        checked_any = True
        failures, count = validate_analysis(path, analysis_validator)
        total_failures += failures
        total_records += count

    if not checked_any:
        print("No manifests or analysis artifacts to validate yet — nothing to check. OK.")
        return 0
    if total_failures:
        print(f"\nFAILED: {total_failures} of {total_records} item(s) drifted from the contract.")
        return 1
    print(f"\nPASSED: {total_records} item(s) conform to the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
