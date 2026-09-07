#!/usr/bin/env python3
"""CouncilLens — analyse stage.

Assembles one topic model per council + topic from two inputs that are both in
the repo already:

    data/processed/manifest.json     the canonical records (what the council published)
    data/ai-cache/<council>/<topic>/ the cached AI outputs (summaries, events, linkages)

and writes data/analysed/<council-slug>/<topic-slug>.json, which must match
data/schemas/topic.schema.json.

Three rules this stage never breaks:

1. No network, no model calls. Everything it needs is on disk and versioned.
2. Nothing is invented. If a cache entry is missing, or the document it was
   written from has changed since, the item is marked `needs_review`, a gap is
   recorded saying exactly what is missing, and the build still exits 0. A hole
   in the evidence is a fact about the council's publishing, not a build failure.
3. Council-agnostic. There is no council name, committee name or URL in this
   file. Council-specific detail lives in config/sources.yaml and in the cache.

Run locally:
    python src/analyse/build_topic.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_MANIFEST = ROOT / "data" / "processed" / "manifest.json"
SOURCES_CONFIG = ROOT / "config" / "sources.yaml"
CACHE_ROOT = ROOT / "data" / "ai-cache"
ANALYSED_ROOT = ROOT / "data" / "analysed"

SCHEMA_VERSION = "1"
CORRECTIONS_URL = "https://github.com/dawsman/councillens/issues/new?template=correction.yml"

# Kinds of cached AI output. One file per item, named <cache_key>.json.
KINDS = ("topic", "summary", "event", "linkage", "gap")

PLACEHOLDER_SUMMARY = (
    "Not summarised yet. This document is in the archive but no reviewed "
    "plain-English summary has been written for it."
)
PLACEHOLDER_REMIT = (
    "Not written yet. This council's remit note — what it does and does not "
    "control — has not been drafted."
)
PLACEHOLDER_ANSWER = "We do not have a reviewed answer to this question yet."


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def slugify(value):
    """Lowercase hyphen slug. Anything in brackets is dropped first, so
    'Licensing policy (alcohol, entertainment and late-night venues)' becomes
    'licensing-policy' — the short name a URL wants."""
    value = re.sub(r"\(.*?\)", " ", value or "")
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-")


def short_name(value):
    """The part of a configured name before any bracketed qualifier."""
    return re.sub(r"\(.*?\)", " ", value or "").strip(" -,")


def cache_key(item_key, sha256s, prompt_version):
    """sha256 over the item's identity, the sha256 of every source it was written
    from, and the prompt version.

    Including the source hashes is what makes the cache self-invalidating: edit a
    council document and re-fetch it, and the key no longer matches, so the stale
    summary is flagged instead of being quietly reused. Including the item key
    keeps two outputs written from the same documents (two events off one set of
    minutes, say) in separate files."""
    joined = "|".join([item_key] + sorted(sha256s) + [prompt_version])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def ai_placeholder(source_ids, prompt_version, reason_key):
    """The provenance block for something we could not load. It says 'no model
    wrote this' as plainly as the schema allows."""
    return {
        "source_ids": list(source_ids),
        "prompt_version": prompt_version,
        "model": "none (no cached output)",
        "confidence": "low",
        "review_status": "needs_review",
        "reviewed_by": None,
        "generated_at": "1970-01-01T00:00:00+00:00",
        "cache_key": reason_key,
    }


def load_cache(cache_dir):
    """Read every cache file in the directory, grouped by kind."""
    grouped = {kind: [] for kind in KINDS}
    if not cache_dir.is_dir():
        return grouped, ["The AI cache directory for this council and topic does not exist."]

    problems = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"Cache file {path.name} could not be read ({exc.msg}).")
            continue
        kind = entry.get("kind")
        if kind not in grouped:
            problems.append(f"Cache file {path.name} has an unknown kind {kind!r}.")
            continue
        entry["_file"] = path.name
        grouped[kind].append(entry)
    return grouped, problems


def check_key(entry, item_key, prompt_version, hashes_by_id):
    """Recompute the cache key from today's manifest. Returns (ok, note).

    A mismatch means the source documents have moved on since the output was
    written, so the output is stale — it is kept and flagged, never dropped.
    """
    ai = entry.get("ai", {})
    source_ids = ai.get("source_ids", [])
    missing = [sid for sid in source_ids if sid not in hashes_by_id]
    if missing:
        return False, "it cites documents that are not in the archive: " + ", ".join(sorted(missing))
    expected = cache_key(item_key, [hashes_by_id[sid] for sid in source_ids], prompt_version)
    if expected != ai.get("cache_key"):
        return False, "the documents it was written from have changed since it was written"
    return True, None


def flag_stale(entry, note, gaps, stage, what):
    ai = dict(entry.get("ai", {}))
    ai["review_status"] = "needs_review"
    ai["confidence"] = "low"
    gaps.append({
        "stage": stage,
        "description": f"{what} needs re-checking: {note}.",
    })
    return ai


def sort_key_for_event(event):
    """Undated events sort last; otherwise oldest first, then by id."""
    return (event.get("date") or "9999", event.get("id", ""))


def newest(timestamps):
    stamps = [t for t in timestamps if t]
    return max(stamps) if stamps else "1970-01-01T00:00:00+00:00"


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build(manifest, config):
    council_name = manifest.get("council") or config.get("council") or "Unknown council"
    topic_config_name = manifest.get("topic") or config.get("topic") or "Unknown topic"

    council_slug = slugify(council_name)
    topic_slug = slugify(topic_config_name)

    documents = manifest.get("documents", [])
    hashes_by_id = {d["id"]: d.get("sha256", "") for d in documents if d.get("id")}

    cache_dir = CACHE_ROOT / council_slug / topic_slug
    cache, cache_problems = load_cache(cache_dir)

    gaps = []
    for problem in cache_problems:
        gaps.append({"stage": None, "description": problem})

    # --- an enabled source that never produced a record is itself a gap -----
    manifest_ids = set(hashes_by_id)
    for entry in config.get("sources", []) or []:
        if not entry.get("enabled", True):
            continue
        sid = entry.get("id")
        if sid and sid not in manifest_ids and not any(i.startswith(f"{sid}--") for i in manifest_ids):
            gaps.append({
                "stage": entry.get("stage"),
                "description": (
                    f"The source '{entry.get('title', sid)}' is listed in the source "
                    "config but no document from it reached the archive."
                ),
            })

    # --- council and topic prose -------------------------------------------
    topic_entries = cache["topic"]
    council_block = {
        "name": council_name,
        "slug": council_slug,
        "website": "https://www.gov.uk/find-local-council",
        "tier": "unknown",
        "remit_note": PLACEHOLDER_REMIT,
        "platforms": {},
    }
    topic_block = {
        "name": short_name(topic_config_name),
        "slug": topic_slug,
        "plain_english": PLACEHOLDER_ANSWER,
        "questions": {"asked": PLACEHOLDER_ANSWER, "decided": PLACEHOLDER_ANSWER, "done": PLACEHOLDER_ANSWER},
    }
    ai_stamps = []

    if not topic_entries:
        gaps.append({
            "stage": None,
            "description": (
                "No cached overview for this council and topic, so the remit note "
                "and the asked / decided / done answers are missing."
            ),
        })
    else:
        entry = topic_entries[0]
        if len(topic_entries) > 1:
            gaps.append({
                "stage": None,
                "description": f"{len(topic_entries)} cached overviews found; the build used {entry['_file']}.",
            })
        payload = entry.get("payload", {})
        ok, note = check_key(entry, f"topic:{council_slug}/{topic_slug}", entry.get("ai", {}).get("prompt_version", ""), hashes_by_id)
        if not ok:
            flag_stale(entry, note, gaps, None, "The council and topic overview")
        council_block.update({k: v for k, v in payload.get("council", {}).items() if v is not None})
        council_block["name"] = council_name
        council_block["slug"] = council_slug
        topic_block.update({k: v for k, v in payload.get("topic", {}).items() if v is not None})
        topic_block["slug"] = topic_slug
        ai_stamps.append(entry.get("ai", {}).get("generated_at"))

    # --- sources ------------------------------------------------------------
    summaries = {}
    for entry in cache["summary"]:
        sid = entry.get("payload", {}).get("source_id")
        if sid:
            summaries.setdefault(sid, entry)

    sources = []
    for doc in documents:
        sid = doc.get("id")
        entry = summaries.get(sid)
        if entry is None:
            gaps.append({
                "stage": doc.get("stage"),
                "description": f"No plain-English summary has been written for '{doc.get('title', sid)}'.",
            })
            summary_text = PLACEHOLDER_SUMMARY
            ai = ai_placeholder([sid], "summarise-v1", "0" * 64)
        else:
            ai = dict(entry.get("ai", {}))
            prompt_version = ai.get("prompt_version", "summarise-v1")
            ok, note = check_key(entry, sid, prompt_version, hashes_by_id)
            summary_text = entry.get("payload", {}).get("summary", PLACEHOLDER_SUMMARY)
            if not ok:
                ai = flag_stale(entry, note, gaps, doc.get("stage"),
                                f"The summary of '{doc.get('title', sid)}'")
            ai_stamps.append(ai.get("generated_at"))

        sources.append({
            "id": sid,
            "title": doc.get("title", sid),
            "type": doc.get("type", "unknown"),
            "stage": doc.get("stage"),
            "body": doc.get("body"),
            "platform": doc.get("platform", "generic"),
            "source_url": doc.get("source_url"),
            "fetched_at": doc.get("fetched_at"),
            "sha256": doc.get("sha256"),
            "saved_to": doc.get("saved_to"),
            "summary": summary_text,
            "ai": ai,
        })

    # --- events -------------------------------------------------------------
    events = []
    for entry in cache["event"]:
        payload = entry.get("payload", {})
        eid = payload.get("id")
        if not eid:
            gaps.append({"stage": None, "description": f"Cache file {entry['_file']} describes an event with no id."})
            continue
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, eid, ai.get("prompt_version", "event-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, payload.get("stage"), f"The entry '{payload.get('title', eid)}'")
        ai_stamps.append(ai.get("generated_at"))
        events.append({
            "id": eid,
            "stage": payload.get("stage"),
            "date": payload.get("date"),
            "date_precision": payload.get("date_precision", "unknown"),
            "title": payload.get("title", ""),
            "summary": payload.get("summary", ""),
            "detail": payload.get("detail", []),
            "source_ids": payload.get("source_ids", []),
            "source_url": payload.get("source_url"),
            "status": payload.get("status"),
            "ai": ai,
        })
    events.sort(key=sort_key_for_event)
    event_ids = {e["id"] for e in events}

    for stage in ("feedback", "decision", "outcome"):
        if not any(e["stage"] == stage for e in events):
            gaps.append({
                "stage": stage,
                "description": f"Nothing has been recorded at the {stage} stage for this topic yet.",
            })

    # --- linkages -----------------------------------------------------------
    linkages = []
    for entry in cache["linkage"]:
        payload = entry.get("payload", {})
        src, dst = payload.get("from_event"), payload.get("to_event")
        if src not in event_ids or dst not in event_ids:
            gaps.append({
                "stage": None,
                "description": (
                    f"A cached comparison refers to entries that are not on this page "
                    f"({src} to {dst}), so it has been left out."
                ),
            })
            continue
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, f"{src}>{dst}", ai.get("prompt_version", "linkage-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, None, f"The comparison between {src} and {dst}")
        ai_stamps.append(ai.get("generated_at"))
        linkages.append({
            "from_event": src,
            "to_event": dst,
            "tier": payload.get("tier", "none"),
            "evidence": payload.get("evidence"),
            "evidence_url": payload.get("evidence_url"),
            "explanation": payload.get("explanation", ""),
            "ai": ai,
        })
    linkages.sort(key=lambda l: (l["from_event"], l["to_event"]))

    # Every feedback entry should be compared against every decision entry. A
    # pair nobody has judged is a hole in the reasoning, so say so.
    judged = {(l["from_event"], l["to_event"]) for l in linkages}
    for feedback in [e for e in events if e["stage"] == "feedback"]:
        for decision in [e for e in events if e["stage"] == "decision"]:
            if (feedback["id"], decision["id"]) not in judged:
                gaps.append({
                    "stage": "decision",
                    "description": (
                        f"No one has yet judged whether '{feedback['title']}' is connected "
                        f"to '{decision['title']}'."
                    ),
                })

    # --- gaps recorded by hand ---------------------------------------------
    for entry in cache["gap"]:
        payload = entry.get("payload", {})
        gaps.append({"stage": payload.get("stage"), "description": payload.get("description", "")})
        ai_stamps.append(entry.get("ai", {}).get("generated_at"))

    stage_order = {"feedback": 0, "decision": 1, "outcome": 2}
    gaps.sort(key=lambda g: (stage_order.get(g["stage"], 3), g["description"]))

    # generated_at is the newest thing that went into the build, not the clock,
    # so an unchanged repo rebuilds byte for byte.
    generated_at = newest(ai_stamps + [d.get("fetched_at") for d in documents])

    return council_slug, topic_slug, {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "council": council_block,
        "topic": topic_block,
        "sources": sources,
        "events": events,
        "linkages": linkages,
        "gaps": gaps,
        "corrections_url": CORRECTIONS_URL,
    }


def main():
    if not PROCESSED_MANIFEST.exists():
        print(f"No processed manifest at {PROCESSED_MANIFEST.relative_to(ROOT)} — run the transform stage first.")
        return 0

    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))
    config = yaml.safe_load(SOURCES_CONFIG.read_text(encoding="utf-8")) if SOURCES_CONFIG.exists() else {}

    council_slug, topic_slug, model = build(manifest, config or {})

    out_dir = ANALYSED_ROOT / council_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{topic_slug}.json"
    out_path.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    tiers = {}
    for link in model["linkages"]:
        tiers[link["tier"]] = tiers.get(link["tier"], 0) + 1
    needs_review = sum(
        1 for item in model["sources"] + model["events"] + model["linkages"]
        if item["ai"].get("review_status") == "needs_review"
    )

    print(f"wrote  {out_path.relative_to(ROOT)}")
    print(f"       {len(model['sources'])} sources, {len(model['events'])} entries, "
          f"{len(model['linkages'])} comparisons, {len(model['gaps'])} gaps")
    if tiers:
        print("       comparisons by tier: " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    print(f"       {needs_review} item(s) awaiting human review")
    for gap in model["gaps"]:
        print(f"  gap  [{gap['stage'] or '-'}] {gap['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
