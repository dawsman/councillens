#!/usr/bin/env python3
"""One-off: re-key the AI cache on extracted text instead of downloaded bytes.

Why this exists
---------------
Cache keys used to be built from the sha256 of each source document as it came
down the wire. Committee and consultation platforms stamp their pages with
session tokens and view-state blobs that change on every request, so re-fetching
an unchanged agenda produced a different raw hash while the words a reader sees
stayed byte-identical. Every reviewed summary, event, comparison and figure
written from those pages would have been marked stale on the next fetch, for no
reason anyone could act on.

The key now hashes the extracted text (`text` in data/processed/manifest.json).
The raw sha256 keeps its place in the canonical record as the provenance of the
download. This script moves the cache that already exists over to the new rule.

What it changes, and nothing else
---------------------------------
Per cache entry: `ai.cache_key`, and the filename, which is that key. Payloads,
review status, confidence, timestamps, source ids — all untouched. Reviewers are
working in these files; this script must be invisible to them.

It refuses to guess. Before rewriting anything it recomputes each entry's key
under the OLD rule; if that does not reproduce the key already in the file, the
entry is reported and skipped, because a key we cannot explain is not one we
should replace.

Run:
    python scripts/migrate_cache_keys.py --dry-run
    python scripts/migrate_cache_keys.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyse.build_topic import cache_key, text_fingerprint  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_MANIFEST = ROOT / "data" / "processed" / "manifest.json"
CACHE_ROOT = ROOT / "data" / "ai-cache"


def old_cache_key(item_key, raw_sha256s, prompt_version):
    """The superseded rule: the same hash, over the raw download hashes."""
    joined = "|".join([item_key] + sorted(raw_sha256s) + [prompt_version])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def item_keys_for(entry, council_slug, topic_slug):
    """The identity half of a key — what the item is, independent of its sources.

    Returns the canonical key first, then any older spelling that entries in the
    cache are known to have been written with. Mirrors src/analyse/build_topic.py.

    The one variant: a handful of gaps were keyed on the bare gap id rather than
    `gap:<id>`. Nothing verifies gap keys, so both spellings sat in the cache
    unnoticed. They are accepted here and written back canonically.
    """
    kind = entry.get("kind")
    payload = entry.get("payload", {})
    if kind == "topic":
        return [f"topic:{council_slug}/{topic_slug}"]
    if kind == "summary":
        return [payload.get("source_id")]
    if kind == "linkage":
        return [f"{payload.get('from_event')}>{payload.get('to_event')}"]
    if kind == "gap":
        return [f"gap:{payload.get('id')}", payload.get("id")]
    if kind in ("event", "figure"):
        return [payload.get("id")]
    return []


def load_documents():
    """Both fingerprints for every document: the raw one to verify the old key,
    the text one to write the new."""
    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))
    raw, text = {}, {}
    for record in manifest.get("documents", []):
        sid = record.get("id")
        if not sid:
            continue
        raw[sid] = record.get("sha256", "")
        text[sid] = text_fingerprint(record)
    return raw, text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change and write nothing.")
    args = parser.parse_args(argv)

    if not PROCESSED_MANIFEST.exists():
        print("No processed manifest — run the transform stage first.")
        return 1
    raw_by_id, text_by_id = load_documents()

    planned = []      # (path, entry, new_key)
    unchanged = 0
    problems = []

    for cache_dir in sorted(p for p in CACHE_ROOT.glob("*/*") if p.is_dir()):
        council_slug, topic_slug = cache_dir.parent.name, cache_dir.name
        for path in sorted(cache_dir.glob("*.json")):
            entry = json.loads(path.read_text(encoding="utf-8"))
            ai = entry.get("ai", {})
            current = ai.get("cache_key")
            prompt_version = ai.get("prompt_version", "")
            source_ids = ai.get("source_ids", [])
            candidates = [k for k in item_keys_for(entry, council_slug, topic_slug) if k]

            where = f"{council_slug}/{topic_slug}/{path.name}"
            if not candidates:
                problems.append(f"{where}: unknown kind {entry.get('kind')!r}")
                continue
            missing = [s for s in source_ids if s not in raw_by_id]
            if missing:
                problems.append(f"{where}: cites documents not in the manifest ({', '.join(missing)})")
                continue
            if path.stem != current:
                problems.append(f"{where}: filename does not match ai.cache_key ({current})")
                continue
            raw_hashes = [raw_by_id[s] for s in source_ids]
            if not any(old_cache_key(k, raw_hashes, prompt_version) == current for k in candidates):
                problems.append(f"{where}: does not reproduce under the old rule — left alone")
                continue

            item_key = candidates[0]
            new_key = cache_key(item_key, [text_by_id[s] for s in source_ids], prompt_version)
            if new_key == current:
                unchanged += 1
                continue
            planned.append((path, entry, new_key))

    # A collision would silently destroy someone's reviewed work. Stop instead.
    by_new = {}
    for path, _entry, new_key in planned:
        by_new.setdefault((path.parent, new_key), []).append(path.name)
    for (parent, new_key), names in sorted(by_new.items()):
        if len(names) > 1:
            problems.append(f"{parent.name}: {len(names)} entries would collide on {new_key}")
    if any("would collide" in p for p in problems):
        for problem in problems:
            print(f"  !! {problem}")
        print("\nAborted: nothing written.")
        return 1

    for path, entry, new_key in planned:
        target = path.parent / f"{new_key}.json"
        rel = path.relative_to(ROOT)
        if args.dry_run:
            print(f"  would rekey {rel}\n           -> {new_key}.json")
            continue
        entry["ai"]["cache_key"] = new_key
        target.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if target != path:
            path.unlink()
        print(f"  rekeyed {rel}\n       -> {new_key}.json")

    for problem in problems:
        print(f"  !! {problem}")

    verb = "would be re-keyed" if args.dry_run else "re-keyed"
    print(f"\n{len(planned)} entries {verb}, {unchanged} already correct, {len(problems)} skipped.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
