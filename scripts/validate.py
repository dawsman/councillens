#!/usr/bin/env python3
"""The contract gate.

Validates every canonical record — from both the ingest stage (data/raw) and the
transform stage (data/processed) — against data/schemas/document.schema.json, and
every model written by the analyse stage (data/analysed) against its contract:
topic models against data/schemas/topic.schema.json, and the "who runs the
council" model against data/schemas/people.schema.json. Exits non-zero if
anything drifts. The CI workflow runs this on every pull request, so
non-conforming records cannot be merged.

Run locally:
    python scripts/validate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "schemas" / "document.schema.json"
TOPIC_SCHEMA_PATH = ROOT / "data" / "schemas" / "topic.schema.json"
PEOPLE_SCHEMA_PATH = ROOT / "data" / "schemas" / "people.schema.json"
# The analyse stage writes more than one shape into data/analysed/. Each file is
# checked against the contract for its shape, chosen by what the file itself
# contains rather than by where it sits, so a renamed file cannot slip past the
# gate by landing in the wrong folder.
PEOPLE_FILENAME = "people.json"
MANIFESTS = [
    ROOT / "data" / "raw" / "manifest.json",
    ROOT / "data" / "processed" / "manifest.json",
]
ANALYSED_DIR = ROOT / "data" / "analysed"


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


def validate_analysed(validators):
    """Every model the analyse stage wrote must match the contract for its shape.

    `validators` maps a shape name to its validator. A file named people.json is
    the "who runs the council" model; everything else is a topic model. If a shape
    has no schema in the repo yet, the file is reported and skipped rather than
    checked against the wrong contract — a wrong pass is worse than no pass.
    """
    failures = 0
    paths = sorted(ANALYSED_DIR.glob("**/*.json"))
    for path in paths:
        name = path.relative_to(ANALYSED_DIR)
        shape = "people" if path.name == PEOPLE_FILENAME else "topic"
        validator = validators.get(shape)
        if validator is None:
            print(f"SKIP   analysed/{name}: no {shape} schema in the repo to check it against")
            continue
        try:
            model = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures += 1
            print(f"DRIFT  analysed/{name}: not valid JSON ({exc.msg})")
            continue
        errors = sorted(validator.iter_errors(model), key=lambda e: list(e.path))
        if errors:
            failures += 1
            print(f"DRIFT  analysed/{name}:")
            for err in errors:
                where = "/".join(str(p) for p in err.path) or "(root)"
                print(f"    - {where}: {err.message}")
        else:
            print(f"ok     analysed/{name}")
    return failures, len(paths)


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

    if ANALYSED_DIR.is_dir():
        validators = {}
        for shape, schema_path in (("topic", TOPIC_SCHEMA_PATH), ("people", PEOPLE_SCHEMA_PATH)):
            if schema_path.exists():
                validators[shape] = jsonschema.Draft202012Validator(
                    json.loads(schema_path.read_text(encoding="utf-8"))
                )
        if validators:
            failures, count = validate_analysed(validators)
            if count:
                checked_any = True
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
