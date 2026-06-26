#!/usr/bin/env python3
"""The analyse-stage contract.

The analyse stage produces a different artifact from a canonical record — a
plain-English summary plus feedback -> decision -> outcome linkages — so it has
its own schema (data/schemas/analysis.schema.json). This module is the single
place that contract is enforced in code, mirroring src/ingest/canonical.py for
the document contract.

Same discipline as the rest of the project: if the analyse output does not
conform, it is rejected. The output is checked here when it is written, and again
in CI by scripts/validate.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "schemas" / "analysis.schema.json"

_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_validator = jsonschema.Draft202012Validator(_schema)


def validate_analysis(analysis):
    """Raise ValueError if the analysis artifact does not match the contract."""
    errors = sorted(_validator.iter_errors(analysis), key=lambda e: list(e.path))
    if errors:
        lines = []
        for err in errors:
            where = "/".join(str(p) for p in err.path) or "(root)"
            lines.append(f"  - {where}: {err.message}")
        topic = analysis.get("topic", "<no topic>")
        raise ValueError(
            f"Analysis for {topic!r} drifts from the contract:\n" + "\n".join(lines)
        )
    return analysis
