#!/usr/bin/env python3
"""The canonical record contract.

Every document that enters CouncilLens — from any council, via any adapter — must
match data/schemas/document.schema.json. This module is the single place that
contract is enforced in code. Adapters validate before returning, and the CI gate
(scripts/validate.py) checks the same schema.

If a record does not conform, it is rejected. There is no per-council escape hatch:
that is what keeps outputs comparable across every council.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "schemas" / "document.schema.json"

_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_validator = jsonschema.Draft202012Validator(_schema)


def validate_record(record):
    """Raise ValueError if the record does not match the contract."""
    errors = sorted(_validator.iter_errors(record), key=lambda e: list(e.path))
    if errors:
        lines = []
        for err in errors:
            where = "/".join(str(p) for p in err.path) or "(root)"
            lines.append(f"  - {where}: {err.message}")
        rid = record.get("id", "<no id>")
        raise ValueError(f"Record {rid!r} drifts from the contract:\n" + "\n".join(lines))
    return record


def validate_many(records):
    for record in records:
        validate_record(record)
    return records
