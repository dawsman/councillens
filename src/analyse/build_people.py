#!/usr/bin/env python3
"""CouncilLens — analyse stage, the "who runs the council" model.

Sister to ``build_topic.py`` and built the same way, from the same three inputs:

    data/processed/manifest.json      what the council published about itself
    data/ai-cache/<council>/_people/  what was written from those documents
    config/councils/<council>.yaml    who the council is

and it writes one ``data/analysed/<council-slug>/people.json`` per council, which
must match ``data/schemas/people.schema.json``.

Where a topic model answers "what happened about licensing", this one answers the
question every topic page eventually raises: who decided it. Who sits on this
council, how long they have been there, what jobs they hold, what they have
declared about themselves, and who the senior paid officers are.

What this stage will not do
---------------------------
It is built to be dull on purpose, because a page about named people is where a
transparency project is most likely to do harm.

* **Official and self-declared sources only.** The council's own councillor
  directory, its committee system, its election results, its allowances schedule,
  its senior-pay publication — and the Register of Members' Interests, which is
  the councillor's own sworn declaration under the Localism Act 2011. Nothing
  from a social network, a company register, or the press.
* **No profiles.** Nothing here is assembled by matching a person's name against
  an outside database. Every line about a person comes from a document that
  person's own council published, and links back to it.
* **No judgements.** There is no score, no ranking, no "worst attender". The
  model carries what the record says and stops.
* **Data minimisation.** No family, no health, no home address. Land interests
  are carried at ward level, as the register itself frames them, never as a
  street. Where a council prints a personal mobile number, this model does not
  carry it: a council email address is a contact route, a mobile number is a
  person's phone.
* **Declared links are recorded, never followed.** If a councillor asked their
  council to print their website on their council page, the URL is recorded as
  published. This project does not fetch it, read it, or summarise it.

The three rules the topic build keeps, this one keeps too: no network and no model
calls; nothing invented, with a missing cache entry becoming a visible gap rather
than a guess; and no council-specific detail in this file.

Run locally:
    python src/analyse/build_people.py
    python src/analyse/build_people.py --only norwich-city-council
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

# The name of the analyse stage a source config asks for with `model:`.
MODEL_NAME = "people"
# The cache lives beside the topics, under a name no topic slug can take: slugs
# never start with an underscore, so `_people` cannot collide with a real topic.
CACHE_DIRNAME = "_people"
OUTPUT_FILENAME = "people.json"

KINDS = ("composition", "person", "officer", "body", "gap")

PLACEHOLDER_REMIT = (
    "Not written yet. This council's remit note — what it does and does not "
    "control — has not been drafted."
)

slugify = cfg.slugify


# --------------------------------------------------------------------------
# Cache plumbing — identical rules to the topic build, deliberately
# --------------------------------------------------------------------------

def text_fingerprint(record):
    """The sha256 of a document's extracted text. See src/analyse/README.md for
    why the key follows the words rather than the downloaded bytes."""
    text = record.get("text")
    if text:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    return record.get("sha256", "")


def cache_key(item_key, text_hashes, prompt_version):
    joined = "|".join([item_key] + sorted(text_hashes) + [prompt_version])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def load_cache(cache_dir):
    grouped = {kind: [] for kind in KINDS}
    if not cache_dir.is_dir():
        return grouped, ["The AI cache directory for this council's people has not been created."]
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
    """Recompute the key from today's manifest. A mismatch means the documents
    have moved on since the entry was written, so it is flagged, never dropped."""
    ai = entry.get("ai", {})
    source_ids = ai.get("source_ids", [])
    missing = [sid for sid in source_ids if sid not in hashes_by_id]
    if missing:
        return False, "it cites documents that are not in the archive: " + ", ".join(sorted(missing))
    expected = cache_key(item_key, [hashes_by_id[sid] for sid in source_ids], prompt_version)
    if expected != ai.get("cache_key"):
        return False, "the documents it was written from have changed since it was written"
    return True, None


def flag_stale(entry, note, gaps, area, what):
    ai = dict(entry.get("ai", {}))
    ai["review_status"] = "needs_review"
    ai["confidence"] = "low"
    gaps.append({"area": area, "description": f"{what} needs re-checking: {note}."})
    return ai


def newest(timestamps):
    stamps = [t for t in timestamps if t]
    return max(stamps) if stamps else "1970-01-01T00:00:00+00:00"


def payload_list(payload, key):
    value = payload.get(key)
    return value if isinstance(value, list) else []


# --------------------------------------------------------------------------
# Shaping — every field the schema asks for, filled from the cache or nulled
# --------------------------------------------------------------------------

def shape_election(raw):
    return {
        "date": raw.get("date"),
        "date_precision": raw.get("date_precision", "unknown"),
        "result": raw.get("result", "unknown"),
        "ward": raw.get("ward"),
        "votes": raw.get("votes"),
        "majority": raw.get("majority"),
        "turnout_percent": raw.get("turnout_percent"),
        "source_url": raw.get("source_url"),
    }


def shape_role(raw):
    return {
        "title": raw.get("title", ""),
        "body_slug": raw.get("body_slug"),
        "since": raw.get("since"),
        "source_url": raw.get("source_url"),
    }


def shape_party_history(raw):
    return {
        "party": raw.get("party", ""),
        "from": raw.get("from"),
        "to": raw.get("to"),
        "source_url": raw.get("source_url"),
    }


def shape_committee(raw):
    name = raw.get("name", "")
    return {
        "slug": raw.get("slug") or slugify(name),
        "name": name,
        "role": raw.get("role", "Member"),
        "since": raw.get("since"),
    }


def shape_outside_body(raw):
    return {"name": raw.get("name", ""), "since": raw.get("since")}


def shape_declared(raw):
    """One line of a register, in the councillor's own words."""
    if isinstance(raw, str):
        return {"text": raw, "category": ""}
    return {"text": raw.get("text", ""), "category": raw.get("category", "")}


def shape_interests(raw):
    raw = raw or {}
    out = {
        "register_url": raw.get("register_url"),
        "register_date": raw.get("register_date"),
        "note": raw.get("note"),
    }
    for key in ("employment", "directorships", "memberships", "sponsorship", "land", "other"):
        out[key] = [shape_declared(item) for item in payload_list(raw, key)]
    return out


def shape_attendance(raw):
    """Both halves of the council's own figure, or neither.

    A committee system that publishes "absent 11, apologies received 11" is
    saying two things, and carrying only the first would make a councillor who
    apologised for every absence look like one who did not bother."""
    if not raw:
        return None
    return {
        "expected": raw.get("expected"),
        "attended": raw.get("attended"),
        "apologies": raw.get("apologies"),
        "period": raw.get("period"),
        "source_url": raw.get("source_url"),
        "note": raw.get("note"),
    }


def shape_allowances(raw):
    if not raw:
        return None
    return {
        "basic": raw.get("basic"),
        "special_responsibility": raw.get("special_responsibility"),
        "total": raw.get("total"),
        "currency": raw.get("currency", "GBP"),
        "year": raw.get("year"),
        "source_url": raw.get("source_url"),
        "note": raw.get("note"),
    }


def shape_contact(raw):
    """Council contact route only. A personal telephone number is not a contact
    route the council chose to give this person — it is that person's phone — so
    even where a council prints one, it does not travel through here."""
    raw = raw or {}
    return {"email": raw.get("email"), "address": raw.get("address")}


def shape_declared_links(raw):
    """Recorded exactly as the council prints them, and never fetched."""
    out = []
    for item in raw or []:
        if isinstance(item, str):
            out.append({"label": item, "url": item})
        elif item.get("url"):
            out.append({"label": item.get("label") or item["url"], "url": item["url"]})
    return out


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build(council_name, documents):
    council_slug = slugify(council_name)
    hashes_by_id = {d["id"]: text_fingerprint(d) for d in documents if d.get("id")}

    cache, cache_problems = load_cache(CACHE_ROOT / council_slug / CACHE_DIRNAME)
    gaps = [{"area": None, "description": p} for p in cache_problems]
    ai_stamps = []

    # --- who the council is -------------------------------------------------
    council_block = {
        "name": council_name,
        "slug": council_slug,
        "website": "https://www.gov.uk/find-local-council",
        "tier": "unknown",
        "remit_note": PLACEHOLDER_REMIT,
        "platforms": {},
    }
    council_config = cfg.load_council(council_slug)
    if council_config is None:
        gaps.append({
            "area": None,
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

    # --- the councillors ----------------------------------------------------
    councillors = []
    seen_person_ids = set()
    for entry in cache["person"]:
        payload = entry.get("payload", {})
        pid = payload.get("id")
        if not pid:
            gaps.append({"area": "councillors",
                         "description": f"Cache file {entry['_file']} describes a councillor with no id."})
            continue
        if pid in seen_person_ids:
            gaps.append({"area": "councillors",
                         "description": f"Two cached entries share the councillor id {pid}; the build used the first."})
            continue
        seen_person_ids.add(pid)
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, pid, ai.get("prompt_version", "person-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, "councillors",
                            f"The entry for {payload.get('name', pid)}")
        ai_stamps.append(ai.get("generated_at"))
        councillors.append({
            "id": pid,
            "name": payload.get("name", pid),
            "party": payload.get("party"),
            "ward": payload.get("ward"),
            "party_history": [shape_party_history(h) for h in payload_list(payload, "party_history")],
            "first_elected": payload.get("first_elected"),
            "first_elected_precision": payload.get("first_elected_precision", "unknown"),
            "current_term_start": payload.get("current_term_start"),
            "elections": [shape_election(e) for e in payload_list(payload, "elections")],
            "roles": [shape_role(r) for r in payload_list(payload, "roles")],
            "committees": [shape_committee(c) for c in payload_list(payload, "committees")],
            "outside_bodies": [shape_outside_body(b) for b in payload_list(payload, "outside_bodies")],
            "attendance": shape_attendance(payload.get("attendance")),
            "allowances": shape_allowances(payload.get("allowances")),
            "interests": shape_interests(payload.get("interests")),
            "declared_links": shape_declared_links(payload.get("declared_links")),
            "contact": shape_contact(payload.get("contact")),
            "summary": payload.get("summary", ""),
            "source_ids": payload.get("source_ids", ai.get("source_ids", [])),
            "source_urls": payload.get("source_urls", []),
            "ai": ai,
            "_order": payload.get("order", 10 ** 6),
        })
    councillors.sort(key=lambda c: (c.pop("_order"), c["name"], c["id"]))

    if not councillors:
        gaps.append({
            "area": "councillors",
            "description": (
                "No councillors have been recorded for this council, so there is "
                "nothing to show about who sits on it."
            ),
        })

    known_ids = {c["id"] for c in councillors}

    # --- senior officers ----------------------------------------------------
    officers = []
    seen_officer_ids = set()
    for entry in cache["officer"]:
        payload = entry.get("payload", {})
        oid = payload.get("id")
        if not oid:
            gaps.append({"area": "officers",
                         "description": f"Cache file {entry['_file']} describes an officer with no id."})
            continue
        if oid in seen_officer_ids:
            gaps.append({"area": "officers",
                         "description": f"Two cached entries share the officer id {oid}; the build used the first."})
            continue
        seen_officer_ids.add(oid)
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, oid, ai.get("prompt_version", "officer-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, "officers",
                            f"The entry for the post '{payload.get('role', oid)}'")
        ai_stamps.append(ai.get("generated_at"))
        officers.append({
            "id": oid,
            "role": payload.get("role", oid),
            "name": payload.get("name"),
            "statutory_role": payload.get("statutory_role"),
            "pay_band": payload.get("pay_band"),
            "pay_note": payload.get("pay_note"),
            "as_of": payload.get("as_of"),
            "summary": payload.get("summary", ""),
            "source_ids": payload.get("source_ids", ai.get("source_ids", [])),
            "source_url": payload.get("source_url"),
            "ai": ai,
            "_order": payload.get("order", 10 ** 6),
        })
    officers.sort(key=lambda o: (o.pop("_order"), o["role"], o["id"]))

    if not officers:
        gaps.append({
            "area": "officers",
            "description": (
                "No senior officers have been recorded for this council, so the page "
                "cannot say who the paid people in charge are."
            ),
        })

    # --- committees and panels ---------------------------------------------
    bodies = []
    seen_body_slugs = set()
    for entry in cache["body"]:
        payload = entry.get("payload", {})
        slug = payload.get("slug")
        if not slug:
            gaps.append({"area": "bodies",
                         "description": f"Cache file {entry['_file']} describes a committee with no slug."})
            continue
        if slug in seen_body_slugs:
            gaps.append({"area": "bodies",
                         "description": f"Two cached entries share the committee slug {slug}; the build used the first."})
            continue
        seen_body_slugs.add(slug)
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, f"body:{slug}", ai.get("prompt_version", "body-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, "bodies",
                            f"The entry for '{payload.get('name', slug)}'")
        ai_stamps.append(ai.get("generated_at"))

        members = []
        for mid in payload_list(payload, "members"):
            if mid in known_ids:
                members.append(mid)
            else:
                gaps.append({
                    "area": "bodies",
                    "description": (
                        f"'{payload.get('name', slug)}' lists a member ({mid}) who is not "
                        "among the councillors on this page, so they have been left off it."
                    ),
                })
        chair = payload.get("chair")
        if chair and chair not in known_ids:
            gaps.append({
                "area": "bodies",
                "description": (
                    f"The chair recorded for '{payload.get('name', slug)}' ({chair}) is not "
                    "among the councillors on this page."
                ),
            })
            chair = None
        vice = payload.get("vice_chair")
        if vice and vice not in known_ids:
            vice = None

        bodies.append({
            "slug": slug,
            "name": payload.get("name", slug),
            "kind": payload.get("kind", "committee"),
            "purpose": payload.get("purpose", ""),
            "members": members,
            "chair": chair,
            "vice_chair": vice,
            "source_ids": payload.get("source_ids", ai.get("source_ids", [])),
            "source_url": payload.get("source_url"),
            "ai": ai,
            "_order": payload.get("order", 10 ** 6),
        })
    bodies.sort(key=lambda b: (b.pop("_order"), b["name"], b["slug"]))

    if not bodies:
        gaps.append({
            "area": "bodies",
            "description": (
                "No committees have been recorded for this council, so a topic page "
                "cannot yet say which councillors sat on the committee that decided it."
            ),
        })

    # A councillor who says they sit on a committee that is not on this page is a
    # hole in the wiring, and the site would quietly show a dead end.
    body_slugs = {b["slug"] for b in bodies}
    for person in councillors:
        for committee in person["committees"]:
            if committee["slug"] not in body_slugs:
                gaps.append({
                    "area": "bodies",
                    "description": (
                        f"{person['name']} is recorded on '{committee['name']}', but that "
                        "committee has no entry of its own yet."
                    ),
                })

    # --- who has how many seats --------------------------------------------
    composition = None
    if not cache["composition"]:
        gaps.append({
            "area": "composition",
            "description": (
                "No cached record of how the seats are shared out, so the page cannot "
                "say which party runs this council."
            ),
        })
    else:
        entry = cache["composition"][0]
        if len(cache["composition"]) > 1:
            gaps.append({
                "area": "composition",
                "description": f"{len(cache['composition'])} cached seat counts found; the build used {entry['_file']}.",
            })
        payload = entry.get("payload", {})
        ai = dict(entry.get("ai", {}))
        ok, note = check_key(entry, f"composition:{council_slug}",
                             ai.get("prompt_version", "composition-v1"), hashes_by_id)
        if not ok:
            ai = flag_stale(entry, note, gaps, "composition", "The count of seats by party")
        ai_stamps.append(ai.get("generated_at"))
        seats = [
            {"party": s.get("party", ""), "seats": s.get("seats", 0)}
            for s in payload_list(payload, "seats_by_party")
        ]
        composition = {
            "as_of": payload.get("as_of"),
            "total_seats": payload.get("total_seats"),
            "seats_by_party": seats,
            "next_election": payload.get("next_election"),
            "next_election_note": payload.get("next_election_note"),
            "source_ids": payload.get("source_ids", ai.get("source_ids", [])),
            "source_url": payload.get("source_url"),
            "summary": payload.get("summary", ""),
            "ai": ai,
        }
        # The seat count and the list of councillors are two readings of the same
        # directory. If they disagree, say so rather than picking a winner.
        declared_total = sum(s["seats"] for s in seats)
        if composition["total_seats"] is not None and declared_total != composition["total_seats"]:
            gaps.append({
                "area": "composition",
                "description": (
                    f"The seats listed by party add up to {declared_total}, but the total "
                    f"recorded is {composition['total_seats']}."
                ),
            })
        if councillors and composition["total_seats"] is not None \
                and len(councillors) != composition["total_seats"]:
            gaps.append({
                "area": "composition",
                "description": (
                    f"This page lists {len(councillors)} councillors but records "
                    f"{composition['total_seats']} seats. A seat may be vacant, or a "
                    "councillor may be missing from the page."
                ),
            })

    if composition is None:
        composition = {
            "as_of": None, "total_seats": None, "seats_by_party": [],
            "next_election": None, "next_election_note": None,
            "source_ids": [], "source_url": None,
            "summary": "We have not recorded how the seats on this council are shared out.",
            "ai": {
                "source_ids": [], "prompt_version": "composition-v1",
                "model": "none (no cached output)", "confidence": "low",
                "review_status": "needs_review", "reviewed_by": None,
                "generated_at": "1970-01-01T00:00:00+00:00", "cache_key": "0" * 64,
            },
        }

    # --- gaps recorded by hand ---------------------------------------------
    for entry in cache["gap"]:
        payload = entry.get("payload", {})
        gaps.append({"area": payload.get("area"), "description": payload.get("description", "")})
        ai_stamps.append(entry.get("ai", {}).get("generated_at"))

    area_order = {"composition": 0, "councillors": 1, "elections": 2, "interests": 3,
                  "attendance": 4, "allowances": 5, "bodies": 6, "officers": 7}
    gaps.sort(key=lambda g: (area_order.get(g["area"], 8), g["description"]))

    generated_at = newest(ai_stamps + [d.get("fetched_at") for d in documents])

    return council_slug, {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "council": council_block,
        "composition": composition,
        "councillors": councillors,
        "officers": officers,
        "bodies": bodies,
        "gaps": gaps,
        "corrections_url": CORRECTIONS_URL,
    }


def report(model, out_path):
    counts = {"needs_review": 0, "ai_reviewed": 0, "reviewed": 0}
    for item in model["councillors"] + model["officers"] + model["bodies"] + [model["composition"]]:
        status = item["ai"].get("review_status")
        if status in counts:
            counts[status] += 1
    parties = {}
    for person in model["councillors"]:
        parties[person["party"] or "no party recorded"] = parties.get(person["party"] or "no party recorded", 0) + 1

    print(f"wrote  {out_path.relative_to(ROOT)}")
    print(f"       {len(model['councillors'])} councillors, {len(model['officers'])} senior officers, "
          f"{len(model['bodies'])} committees, {len(model['gaps'])} gaps")
    if parties:
        print("       by party: " + ", ".join(f"{k}={v}" for k, v in sorted(parties.items())))
    print(f"       review status: {counts['needs_review']} unchecked, "
          f"{counts['ai_reviewed']} checked by a second AI pass, "
          f"{counts['reviewed']} checked by a person")
    for gap in model["gaps"]:
        print(f"  gap  [{gap['area'] or '-'}] {gap['description']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assemble the 'who runs the council' model, one per council.")
    parser.add_argument("--only", metavar="COUNCIL",
                        help="Build one council only, e.g. norwich-city-council.")
    args = parser.parse_args(argv)

    try:
        topics = cfg.load_topics()
    except ValueError as exc:
        print(exc)
        return 1

    # Which council+topic configs feed this model is a config question, answered by
    # `model: people` in the source file. Nothing here knows a council's name.
    wanted_keys = {
        (t.council_slug, t.topic_slug) for t in topics
        if t.model == MODEL_NAME and not t.has_placeholders()
    }
    if not wanted_keys:
        print(f"No source config sets `model: {MODEL_NAME}` — nothing to assemble.")
        return 0

    if not PROCESSED_MANIFEST.exists():
        print(f"No processed manifest at {PROCESSED_MANIFEST.relative_to(ROOT)} — "
              "run the transform stage first.")
        return 0

    manifest = json.loads(PROCESSED_MANIFEST.read_text(encoding="utf-8"))
    groups = {}
    for record in manifest.get("documents", []):
        council_name = record.get("council") or "Unknown council"
        topic_name = record.get("topic") or "Unknown topic"
        if (slugify(council_name), slugify(topic_name)) not in wanted_keys:
            continue
        groups.setdefault(slugify(council_name), (council_name, []))[1].append(record)

    if not groups:
        print("No documents in the processed manifest belong to a people config.")
        return 0

    built = 0
    for council_slug in sorted(groups):
        if args.only and council_slug != args.only:
            continue
        council_name, documents = groups[council_slug]
        slug, model = build(council_name, documents)
        out_dir = ANALYSED_ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / OUTPUT_FILENAME
        out_path.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report(model, out_path)
        built += 1

    if not built:
        print(f"No people documents for {args.only} in the processed manifest.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
