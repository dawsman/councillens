#!/usr/bin/env python3
"""The contract gate.

Validates every canonical record — from both the ingest stage (data/raw) and the
transform stage (data/processed) — against data/schemas/document.schema.json, and
exits non-zero if any record drifts. The CI workflow runs this on every pull
request, so non-conforming records cannot be merged.

Run locally:
    python scripts/validate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "schemas" / "document.schema.json"
MANIFESTS = [
    ROOT / "data" / "raw" / "manifest.json",
    ROOT / "data" / "processed" / "manifest.json",
]


def validate_manifest(path, validator):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    failures = 0
    stage = path.parent.name
    for record in documents:
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        if errors:
            failures += 1
            print(f"DRIFT  {stage}/{record.get('id', '<no id>')}:")
            for err in errors:
                where = "/".join(str(p) for p in err.path) or "(root)"
                print(f"    - {where}: {err.message}")
        else:
            print(f"ok     {stage}/{record.get('id')}")
    return failures, len(documents)


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    total_failures = 0
    total_records = 0
    checked_any = False
    for path in MANIFESTS:
        if not path.exists():
            continue
        checked_any = True
        failures, count = validate_manifest(path, validator)
        total_failures += failures
        total_records += count

    if not checked_any:
        print("No manifests to validate yet — nothing to check. OK.")
        return 0
    if total_failures:
        print(f"\nFAILED: {total_failures} of {total_records} record(s) drifted from the contract.")
        return 1
    print(f"\nPASSED: {total_records} record(s) conform to the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
