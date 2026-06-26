#!/usr/bin/env python3
"""CouncilLens — ingest stage.

Reads config/sources.yaml, downloads each ENABLED public source, saves the raw
file under data/raw/<id>/, and records provenance (URL, timestamp, content hash)
in data/raw/manifest.json.

Pipeline: ingest -> transform -> analyse -> publish

Run locally:
    pip install -r requirements.txt
    python src/ingest/fetch.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"No config at {CONFIG_PATH} — nothing to do.")
        return {}, []
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    meta = {"council": data.get("council"), "topic": data.get("topic")}
    return meta, data.get("sources", []) or []


def is_placeholder(url):
    if not url:
        return True
    host = urlparse(url).netloc.lower()
    return host.endswith("example.com") or "REPLACE_ME" in url


def fetch_one(source):
    out_dir = RAW_DIR / source["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(
        source["url"], timeout=30,
        headers={"User-Agent": "CouncilLens-ingest/0.1"},
    )
    resp.raise_for_status()
    name = Path(urlparse(source["url"]).path).name or "index.html"
    out_path = out_dir / name
    out_path.write_bytes(resp.content)
    return {
        "id": source["id"],
        "title": source.get("title", source["id"]),
        "type": source.get("type", "unknown"),
        "url": source["url"],
        "saved_to": str(out_path.relative_to(ROOT)),
        "bytes": len(resp.content),
        "sha256": hashlib.sha256(resp.content).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    meta, sources = load_config()
    enabled = [s for s in sources if s.get("enabled")]
    if not enabled:
        print("No enabled sources yet. Edit config/sources.yaml: set enabled: true "
              "and add real public document URLs.")
        return 0
    print(f"Council: {meta.get('council')!r}  Topic: {meta.get('topic')!r}")
    records = []
    for s in enabled:
        if is_placeholder(s.get("url", "")):
            print(f"  skip {s.get('id')}: placeholder URL")
            continue
        try:
            rec = fetch_one(s)
            records.append(rec)
            print(f"  ok   {rec['id']}: {rec['bytes']} bytes -> {rec['saved_to']}")
        except Exception as exc:
            print(f"  FAIL {s.get('id')}: {exc}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "council": meta.get("council"),
                "topic": meta.get("topic"),
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "documents": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} record(s) to {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
