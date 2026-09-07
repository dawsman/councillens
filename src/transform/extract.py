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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_MANIFEST = ROOT / "data" / "raw" / "manifest.json"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_MANIFEST = PROCESSED_DIR / "manifest.json"

sys.path.insert(0, str(ROOT / "src" / "ingest"))
import canonical  # noqa: E402

MAX_TEXT_CHARS = 200_000


# Site furniture that carries no information about a decision: navigation, cookie
# banners, skip links, social footers. Stripping it is generic HTML hygiene — it
# is not council-specific, and every council site has some version of it.
CHROME_SELECTORS = [
    "nav", "header", "footer", "form",
    "[role=navigation]", "[role=banner]", "[role=contentinfo]", "[role=search]",
    "[class*=cookie]", "[id*=cookie]", "[class*=consent]", "[id*=consent]",
    "[class*=skip-link]", "[class*=breadcrumb]", "[class*=site-nav]",
    "[class*=menu]", "[id*=menu]", "[class*=social]", "[class*=pagination]",
]


def extract_html(data):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    for selector in CHROME_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    # Prefer the page's main content region when it declares one.
    main = soup.select_one("main, [role=main], #main-content, #content, .main-content")
    text = " ".join((main or soup).get_text(separator=" ").split())

    # If stripping the chrome took the substance with it, fall back to the whole
    # document rather than hand the next stage an empty record.
    if len(text) < 200:
        soup2 = BeautifulSoup(data, "html.parser")
        for tag in soup2(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup2.get_text(separator=" ").split())
    return text


def extract_docx(path):
    """Councils publish plenty of consultation drafts as Word files. A .docx is a
    zip of XML, so this needs no extra dependency: pull the paragraph text out of
    word/document.xml and keep paragraph breaks as spaces."""
    import zipfile
    from xml.etree import ElementTree

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    parts = []
    with zipfile.ZipFile(path) as zf:
        names = [n for n in ("word/document.xml",) if n in zf.namelist()]
        names += sorted(n for n in zf.namelist()
                        if n.startswith("word/") and re.match(r"word/(header|footer)\d+\.xml$", n))
        for name in names:
            root = ElementTree.fromstring(zf.read(name))
            for para in root.iter(f"{ns}p"):
                text = "".join(node.text or "" for node in para.iter(f"{ns}t"))
                if text.strip():
                    parts.append(text)
    return " ".join(" ".join(parts).split())


def extract_csv(path):
    """Spending and performance data arrives as CSV more often than anything
    else, and a comma-separated line reads as gibberish once whitespace is
    collapsed. Rendering each row as 'cell | cell | cell' keeps the columns
    legible to a reader and to anything that greps the text later. Stdlib only,
    and nothing here knows which council the file came from."""
    import csv as _csv

    rows = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in _csv.reader(handle):
            cells = [" ".join(str(cell).split()) for cell in row]
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                rows.append(" | ".join(cells))
    return "\n".join(rows)


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
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".csv":
        return extract_csv(path)
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
