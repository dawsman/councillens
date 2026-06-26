#!/usr/bin/env python3
"""The contract gate.

Validates every canonical record against data/schemas/document.schema.json and
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
MANIFEST_PATH = ROOT / "data" / "raw" / "manifest.json"


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    if not MANIFEST_PATH.exists():
        print("No manifest to validate yet — nothing to check. OK.")
        return 0

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    failures = 0
    for record in documents:
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        if errors:
            failures += 1
            print(f"DRIFT  {record.get('id', '<no id>')}:")
            for err in errors:
                where = "/".join(str(p) for p in err.path) or "(root)"
                print(f"    - {where}: {err.message}")
        else:
            print(f"ok     {record.get('id')}")

    total = len(documents)
    if failures:
        print(f"\nFAILED: {failures} of {total} record(s) drifted from the contract.")
        return 1
    print(f"\nPASSED: {total} record(s) conform to the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
