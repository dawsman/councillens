#!/usr/bin/env python3
"""CouncilLens — transform stage.

Reads data/raw/manifest.json, extracts plain text from each saved raw file
(HTML or PDF), fills the `text` field, and writes data/processed/manifest.json.

Every record it produces must still match the contract
(data/schemas/document.schema.json) — the same schema as ingest. One contract,
every stage.

Run locally:
    pip install -r requirements.txt
    python src/transform/extract.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_MANIFEST = ROOT / "data" / "raw" / "manifest.json"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_MANIFEST = PROCESSED_DIR / "manifest.json"

sys.path.insert(0, str(ROOT / "src" / "ingest"))
import canonical  # noqa: E402

MAX_TEXT_CHARS = 200_000


def extract_html(data):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def extract_pdf(path):
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    reader = PdfReader(str(path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return " ".join(" ".join(parts).split())


def extract_text(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    data = path.read_bytes()
    if suffix in {".html", ".htm", ".aspx", ""}:
        return extract_html(data)
    text = extract_html(data)
    return text or data.decode("utf-8", errors="replace")


def main():
    if not RAW_MANIFEST.exists():
        print("No raw manifest. Run the ingest stage first.")
        return 0
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    if not documents:
        print("Raw manifest has no documents.")
        return 0

    processed = []
    failures = 0
    for record in documents:
        out = dict(record)
        saved = record.get("saved_to")
        path = ROOT / saved if saved else None
        if path and path.exists():
            try:
                out["text"] = extract_text(path)[:MAX_TEXT_CHARS]
            except Exception as exc:
                print(f"  FAIL  {record.get('id')}: extract error: {exc}")
                failures += 1
                continue
        else:
            out["text"] = ""
        try:
            canonical.validate_record(out)
        except ValueError as exc:
            print(f"  DRIFT {record.get('id')}: {exc}")
            failures += 1
            continue
        processed.append(out)
        print(f"  ok    {out['id']}: {len(out['text'])} chars")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_MANIFEST.write_text(
        json.dumps(
            {
                "council": manifest.get("council"),
                "topic": manifest.get("topic"),
                "documents": processed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(processed)} record(s); {failures} rejected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
