#!/usr/bin/env python3
"""CouncilLens — analyse stage.

Assembles one topic model per council + topic from three inputs that are all in
the repo already:

    data/processed/manifest.json     the canonical records (what the council published)
    data/ai-cache/<council>/<topic>/ the cached AI outputs (summaries, events, linkages)
    config/councils/<council>.yaml   who the council is (website, tier, remit note)

and writes one data/analysed/<council-slug>/<topic-slug>.json per council + topic,
each of which must match data/schemas/topic.schema.json.

Records are grouped by the council and topic they already carry, so one run emits
every topic in the manifest. The council block comes from the council config, not
from a topic's cache, so two topics for the same council can never disagree about
what that council does.

Three rules this stage never breaks:

1. No network, no model calls. Everything it needs is on disk and versioned.
2. Nothing is invented. If a cache entry is missing, or the document it was
   written from has changed since, the item is marked `needs_review`, a gap is
   recorded saying exactly what is missing, and the build still exits 0. A hole
   in the evidence is a fact about the council's publishing, not a build failure.
3. Council-agnostic. There is no council name, committee name or URL in this
   file. Council-specific detail lives under config/ and in the cache.

Run locally:
    python src/analyse/build_topic.py
    python src/analyse/build_topic.py --only norwich-city-council/housing-allocations
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_MANIFEST = ROOT / "data" / "processed" / "manifest.json"
CACHE_ROOT = ROOT / "data" / "ai-cache"
ANALYSED_ROOT = ROOT / "data" / "analysed"

SCHEMA_VERSION = "1"
CORRECTIONS_URL = "https://github.com/dawsman/councillens/issues/new?template=correction.yml"

# Kinds of cached AI output. One file per item, named <cache_key>.json.
KINDS = ("topic", "summary", "event", "linkage", "figure", "gap")

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

slugify = cfg.slugify
short_name = cfg.short_name


def text_fingerprint(record):
    """The sha256 of a document's extracted text — what a cache key is built on.

    Not the sha256 of the file as downloaded. Committee and consultation
    platforms stamp their pages with session tokens, view-state blobs and
    timestamps that change on every request, so two fetches of an unchanged
    agenda have two different raw hashes while the words a reader sees are
    byte-identical. Keying the cache on raw bytes therefore marked reviewed work
    stale for no reason at all. The extracted text is what an AI output was
    actually written from, so it is what the key should track: the text moves,
    the key moves; the page's plumbing moves, the key holds.

    The raw sha256 stays in the canonical record, where it belongs — it is the
    provenance of the download, the proof of what arrived.

    A record with no extracted text (nothing we could read out of the file) falls
    back to its raw hash, so an unreadable document still invalidates when it
    changes."""
    text = record.get("text")
    if text:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    return record.get("sha256", "")


def cache_key(item_key, text_hashes, prompt_version):
    """sha256 over the item's identity, the text fingerprint of every source it
    was written from, and the prompt version.

    Including the source fingerprints is what makes the cache self-invalidating:
    change what a council document says, re-fetch it, and the key no longer
    matches, so the stale summary is flagged instead of being quietly reused.
    Including the item key keeps two outputs written from the same documents (two
    events off one set of minutes, say) in separate files."""
    joined = "|".join([item_key] + sorted(text_hashes) + [prompt_version])
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

def build(council_name, topic_config_name, documents, topic_config):
    """One council + one topic: the records that belong to it, plus its config."""
    council_slug = slugify(council_name)
    topic_slug = slugify(topic_config_name)

    # Keyed on the extracted text, not the downloaded bytes — see text_fingerprint.
    hashes_by_id = {d["id"]: text_fingerprint(d) for d in documents if d.get("id")}

    cache_dir = CACHE_ROOT / council_slug / topic_slug
    cache, cache_problems = load_cache(cache_dir)

    gaps = []
    for problem in cache_problems:
        gaps.append({"stage": None, "description": problem})

    # --- an enabled source that never produced a record is itself a gap -----
    manifest_ids = set(hashes_by_id)
    for entry in (topic_config.sources if topic_config else []):
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
    # Who the council is comes from config/councils/<slug>.yaml — a fact about the
    # council, shared by every one of its topics, so two topics cannot disagree.
    council_config = cfg.load_council(council_slug)
    if council_config is None:
        gaps.append({
            "stage": None,
            "description": (
                "No council record has been written for this council, so its remit "
                "note — what it does and does not control — is missing."
            ),
        })
    else:
        for key in ("website", "tier", "remit_note", "platforms"):
            value = council_config.get(key)
            if value is not None:
                council_block[key] = value
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

    # --- figures ------------------------------------------------------------
    # The at-a-glance numbers. Same rule as everything else: a figure exists only
    # because a cached entry cites a document that is in the archive. Nothing is
    # calculated here, nothing is estimated, and a figure whose documents have
    # moved on is flagged rather than quietly reprinted.
    figures = []
    seen_figure_ids = set()
    for entry in cache["figure"]:
        payload = entry.get("payload", {})
        fid = payload.get("id")
        if not fid:
            gaps.append({
                "stage": None,
                "description": f"Cache file {entry['_file']} describes a key number with no id.",
            })
            continue
        if fid in seen_figure_ids:
            gaps.append({
                "stage": None,
                "description": f"Two cached key numbers share the id {fid}; the build used the first.",
            })
            continue
        seen_figure_ids.add(fid)
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, fid, ai.get("prompt_version", "figure-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, None, f"The number '{payload.get('label', fid)}'")
        ai_stamps.append(ai.get("generated_at"))
        figures.append({
            "id": fid,
            "label": payload.get("label", fid),
            "kind": payload.get("kind", "count"),
            "value": payload.get("value"),
            "unit": payload.get("unit"),
            "display": payload.get("display", ""),
            "as_of": payload.get("as_of"),
            "period": payload.get("period"),
            "source_ids": payload.get("source_ids", []),
            "source_url": payload.get("source_url"),
            "note": payload.get("note", ""),
            "ai": ai,
            # Optional curated position from the cache entry; never published.
            "_order": payload.get("order", 10**6),
        })
    figures.sort(key=lambda f: (f.pop("_order"), f["id"]))

    if not figures:
        gaps.append({
            "stage": None,
            "description": (
                "No key numbers have been recorded for this council and topic, so "
                "there is nothing to show at a glance."
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

    model = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "council": council_block,
        "topic": topic_block,
        "sources": sources,
        "events": events,
        "linkages": linkages,
    }
    # `figures` is optional in the contract. An empty at-a-glance panel is a
    # gap, not an empty array, so the key is left out entirely when there is
    # nothing sourced to put in it.
    if figures:
        model["figures"] = figures
    model["gaps"] = gaps
    model["corrections_url"] = CORRECTIONS_URL
    return council_slug, topic_slug, model


def report(model, out_path):
    tiers = {}
    for link in model["linkages"]:
        tiers[link["tier"]] = tiers.get(link["tier"], 0) + 1
    reviewable = model["sources"] + model["events"] + model["linkages"] + model.get("figures", [])
    counts = {"needs_review": 0, "ai_reviewed": 0, "reviewed": 0}
    for item in reviewable:
        status = item["ai"].get("review_status")
        if status in counts:
            counts[status] += 1

    print(f"wrote  {out_path.relative_to(ROOT)}")
    print(f"       {len(model['sources'])} sources, {len(model['events'])} entries, "
          f"{len(model['linkages'])} comparisons, {len(model.get('figures', []))} key numbers, "
          f"{len(model['gaps'])} gaps")
    if tiers:
        print("       comparisons by tier: " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    print(f"       review status: {counts['needs_review']} unchecked, "
          f"{counts['ai_reviewed']} checked by a second AI pass, "
          f"{counts['reviewed']} checked by a person")
    for gap in model["gaps"]:
        print(f"  gap  [{gap['stage'] or '-'}] {gap['description']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assemble one topic model per council + topic.")
    parser.add_argument(
        "--only", metavar="COUNCIL/TOPIC",
        help="Build one topic only, e.g. norwich-city-council/licensing-policy.",
    )
    args = parser.parse_args(argv)

    try:
        wanted = cfg.parse_only(args.only)
        configs = {t.key: t for t in cfg.load_topics()}
    except ValueError as exc:
        print(exc)
        return 1

    if not PROCESSED_MANIFEST.exists():
        print(f"No processed manifest at {PROCESSED_MANIFEST.relative_to(ROOT)} — run the transform stage first.")
        return 0

    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))

    # Group the records by the council and topic they already carry. Nothing here
    # assumes how many councils or topics the manifest holds.
    groups = {}
    for record in manifest.get("documents", []):
        council_name = record.get("council") or "Unknown council"
        topic_name = record.get("topic") or "Unknown topic"
        key = (slugify(council_name), slugify(topic_name))
        if key not in groups:
            groups[key] = (council_name, topic_name, [])
        groups[key][2].append(record)

    if not groups:
        print("Processed manifest has no documents — nothing to assemble.")
        return 0

    built = 0
    skipped = []
    for key in sorted(groups):
        if wanted and key != wanted:
            continue
        topic_config = configs.get(f"{key[0]}/{key[1]}")
        # Some config files gather a different kind of public record and say so
        # with `model:`. Those documents belong to another analyse stage; building
        # a feedback -> decision -> outcome page out of them would invent a trail
        # that nobody claimed was there.
        if topic_config is not None and topic_config.model != "topic":
            skipped.append(f"{key[0]}/{key[1]} (model: {topic_config.model})")
            continue
        council_name, topic_name, documents = groups[key]
        council_slug, topic_slug, model = build(
            council_name, topic_name, documents, topic_config
        )
        out_dir = ANALYSED_ROOT / council_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{topic_slug}.json"
        out_path.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report(model, out_path)
        built += 1

    for note in skipped:
        print(f"skip   {note} — another analyse stage assembles this one.")

    if not built:
        if skipped:
            return 0
        print(f"No records for {args.only} in the processed manifest.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
