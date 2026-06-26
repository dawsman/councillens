#!/usr/bin/env python3
"""Adapters: one per publishing PLATFORM, never one per council.

A single CMIS adapter serves every council on CMIS; a single LocalGov Drupal
adapter serves every council on that platform. All platform-specific quirks are
absorbed here, so everything downstream sees only canonical records.

Adding a council is a config change (config/sources.yaml). You only add code here
when a council uses a PLATFORM no adapter supports yet.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
USER_AGENT = "CouncilLens-ingest/0.2"


class Adapter(ABC):
    """Base adapter. Subclasses MUST return canonical records (see canonical.py)."""

    platform = "base"

    @abstractmethod
    def fetch(self, source, council, topic):
        """Return a list of canonical-record dicts for one configured source."""
        raise NotImplementedError


class GenericAdapter(Adapter):
    """Fallback: archive the raw page and emit one provenance record.

    Text extraction is left to the transform stage; this adapter only fetches and
    records provenance. It works for any URL, which is why it is the default when a
    platform has no dedicated adapter yet.
    """

    platform = "generic"

    def fetch(self, source, council, topic):
        url = source["url"]
        out_dir = RAW_DIR / source["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        name = Path(urlparse(url).path).name or "index.html"
        out_path = out_dir / name
        out_path.write_bytes(resp.content)
        record = {
            "id": source["id"],
            "council": council,
            "topic": topic,
            "body": source.get("body"),
            "stage": source.get("stage"),
            "type": source.get("type", "unknown"),
            "platform": source.get("platform", self.platform),
            "title": source.get("title", source["id"]),
            "text": "",
            "source_url": url,
            "saved_to": str(out_path.relative_to(ROOT)),
            "bytes": len(resp.content),
            "sha256": hashlib.sha256(resp.content).hexdigest(),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return [record]


class CmisAdapter(GenericAdapter):
    """Norwich and many other councils run committee meetings on CMIS.

    For now this reuses the generic fetch so the pipeline runs end to end.
    TODO: parse the CMIS meeting list into one record per agenda / minutes item.
    Whatever it parses, it MUST still return canonical records.
    """

    platform = "cmis"


# Map a platform name (from config) to its adapter. Unknown platforms fall back to
# the generic adapter, so the pipeline never breaks on an unsupported council.
_ADAPTERS = {
    "generic": GenericAdapter,
    "cmis": CmisAdapter,
    # TODO: "modern_gov", "localgov_drupal", "citizen_space", "engagement"
}


def get_adapter(platform):
    return _ADAPTERS.get(platform or "generic", GenericAdapter)()
