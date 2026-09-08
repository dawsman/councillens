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
    python src/transform/extract.py --only norwich-city-council/housing-allocations

`--only` re-extracts one topic and replaces just that topic's records in the
processed manifest, leaving every other topic's extracted text untouched.

Config key this stage understands, in the topic config file alongside `match`,
`exclude` and `max_bytes`:

    max_text_chars:  how much extracted text this source's records keep. Defaults
                     to 200,000. Raise it for a source whose documents are long
                     enough that the part a claim rests on falls off the end — a
                     Statement of Accounts, say, whose notes sit at the back.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_MANIFEST = ROOT / "data" / "raw" / "manifest.json"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_MANIFEST = PROCESSED_DIR / "manifest.json"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ingest"))
import canonical  # noqa: E402
import config as cfg  # noqa: E402

# How much extracted text a record keeps. A cap is needed: a few council PDFs run
# to hundreds of pages, and an unbounded manifest becomes unreadable and unusable
# in a diff. 200,000 characters covers the whole of nearly every document a
# council publishes.
#
# It does not cover all of them. A Statement of Accounts runs past a third of a
# million characters, and the notes at the back — the ones that say what a failed
# company cost, or how a property portfolio moved — fall off the end. A claim
# drawn from the back of such a document cannot then be checked against the
# archive, which breaks the rule that every claim links to its source.
#
# So the cap is a default, not a law. Any source may raise it for itself with
# `max_text_chars` in its topic config file. Raising it only ever ADDS text: the
# characters already kept do not move, so nothing already cited can disappear.
DEFAULT_MAX_TEXT_CHARS = 200_000


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


def text_limits():
    """The character cap for each source id, from the topic config files.

    Config, not code, decides which documents need more room — the same rule that
    keeps `match`, `exclude` and `max_bytes` out of the adapters. Nothing here
    knows a council or a document; it knows that a source may ask for a larger cap.
    """
    limits = {}
    for topic in cfg.load_topics():
        for source in topic.sources:
            limit = source.get("max_text_chars")
            if limit and str(source.get("id") or "").strip():
                limits[source["id"]] = int(limit)
    return limits


def limit_for(record_id, limits):
    """The cap that applies to one record.

    A record is either a source's own page (`<source-id>`) or a document found
    under it (`<source-id>--<slug>`). The longest matching source id wins, so a
    source id that is a prefix of another cannot claim its documents.
    """
    best = None
    for source_id, limit in limits.items():
        if record_id == source_id or record_id.startswith(f"{source_id}--"):
            if best is None or len(source_id) > len(best[0]):
                best = (source_id, limit)
    return best[1] if best else DEFAULT_MAX_TEXT_CHARS


def load_existing():
    if not PROCESSED_MANIFEST.exists():
        return []
    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))
    return manifest.get("documents", []) or []


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract plain text from the fetched raw files.")
    parser.add_argument(
        "--only", metavar="COUNCIL/TOPIC",
        help="Re-extract one topic only, e.g. norwich-city-council/licensing-policy.",
    )
    args = parser.parse_args(argv)

    try:
        wanted = cfg.parse_only(args.only)
    except ValueError as exc:
        print(exc)
        return 1

    if not RAW_MANIFEST.exists():
        print("No raw manifest. Run the ingest stage first.")
        return 0
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    if not documents:
        print("Raw manifest has no documents.")
        return 0

    if wanted:
        selected = [
            d for d in documents
            if (cfg.slugify(d.get("council")), cfg.slugify(d.get("topic"))) == wanted
        ]
        if not selected:
            print(f"No records for {wanted[0]}/{wanted[1]} in the raw manifest.")
            return 1
    else:
        selected = documents

    limits = text_limits()
    processed = []
    failures = 0
    for record in selected:
        out = dict(record)
        saved = record.get("saved_to")
        path = ROOT / saved if saved else None
        if path and path.exists():
            try:
                out["text"] = extract_text(path)[:limit_for(record.get("id", ""), limits)]
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

    if wanted:
        kept = [
            r for r in load_existing()
            if (cfg.slugify(r.get("council")), cfg.slugify(r.get("topic"))) != wanted
        ]
        documents_out = kept + processed
    else:
        documents_out = processed

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_MANIFEST.write_text(
        json.dumps(
            {
                "topics": manifest.get("topics", []),
                "documents": documents_out,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(processed)} record(s) this run; "
          f"manifest holds {len(documents_out)}; {failures} rejected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
