#!/usr/bin/env python3
"""Summarising documents — a bounded, cached, provenance-stamped task.

The methodology lets AI assist with bounded tasks only, and requires that AI
outputs are cached and versioned so the published site regenerates byte-for-byte
from those cached outputs plus the raw inputs. This module honours both:

1. **Cache first.** If a human-reviewed AI summary exists in data/ai-cache for the
   exact document content (keyed by its sha256 + prompt version), it is used.
   The build never calls a model live, so it is deterministic and runs in CI
   without secrets. Writing cache entries is a separate, offline, human-reviewed
   step (see data/ai-cache/README.md) — that is where a model plugs in.

2. **Deterministic fallback.** When no cached summary exists, we produce an
   extractive draft (the document's lead sentences) and flag it `auto-extractive`
   so it is clearly marked as needing an AI + human pass before publishing. The
   draft is a pure function of the document, so the build stays reproducible.

Either way the summary carries the full provenance envelope the methodology
requires: source document IDs, prompt version, model, review flag, timestamp.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Bump these when the summarisation spec / fallback logic changes, so stale
# cached or extractive outputs are regenerated rather than silently reused.
PROMPT_VERSION = "summary-v1"
EXTRACTIVE_MODEL = "extractive-v1"

_MAX_CHARS = 480
_MAX_SENTENCES = 3
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extractive_summary(text, max_chars=_MAX_CHARS, max_sentences=_MAX_SENTENCES):
    """A deterministic lead-sentence summary. No model, no randomness.

    Crude by design: a placeholder draft that a real AI summary (cached and
    reviewed) is meant to replace. We surface it flagged, never as finished prose.
    """
    text = " ".join((text or "").split())
    if not text:
        return ""
    out, total = [], 0
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        out.append(sentence)
        total += len(sentence) + 1
        if len(out) >= max_sentences or total >= max_chars:
            break
    summary = " ".join(out)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip() + "…"
    return summary


def _cache_path(cache_dir, sha256, prompt_version):
    return Path(cache_dir) / "summaries" / f"{sha256}.{prompt_version}.json"


def _load_cached(cache_dir, sha256, prompt_version):
    """Return a cached AI summary for this exact content, or None.

    The cache entry must record the source sha256 it was made from; if that does
    not match the current document, the entry is stale (the document changed) and
    we ignore it rather than show a summary of out-of-date content.
    """
    if not sha256:
        return None
    path = _cache_path(cache_dir, sha256, prompt_version)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if entry.get("source_sha256") and entry["source_sha256"] != sha256:
        return None
    return {
        "text": entry.get("text", ""),
        "method": "ai",
        "source_document_ids": entry.get("source_document_ids") or [],
        "prompt_version": entry.get("prompt_version", prompt_version),
        "model": entry.get("model", "unknown"),
        "review": entry.get("review", "pending"),
        "confidence": entry.get("confidence"),
        "generated_at": entry.get("generated_at", ""),
    }


def summary_for(record, cache_dir, prompt_version=PROMPT_VERSION):
    """Return a summary envelope for one canonical (processed) record.

    Prefers a cached, human-reviewed AI summary; otherwise returns a deterministic
    extractive draft. Always carries full provenance.
    """
    sha256 = record.get("sha256", "")
    cached = _load_cached(cache_dir, sha256, prompt_version)
    if cached is not None:
        return cached

    draft = extractive_summary(record.get("text", ""))
    return {
        "text": draft,
        "method": "extractive",
        "source_document_ids": [record["id"]],
        "prompt_version": prompt_version,
        "model": EXTRACTIVE_MODEL,
        "review": "auto-extractive" if draft else "no_text",
        "confidence": None,
        # Derive the timestamp from the source snapshot, not the wall clock, so two
        # builds of the same inputs are byte-for-byte identical (methodology:
        # reproducibility).
        "generated_at": record["fetched_at"],
    }
