# The analyse stage

`build_topic.py` turns canonical records plus cached AI outputs into one topic
model per council and topic:

```
data/processed/manifest.json                 what the council published
data/ai-cache/<council>/<topic>/*.json   +   what was written about it
                                         ->  data/analysed/<council>/<topic>.json
```

It makes no network calls and no model calls. Run it offline, on a plane, in CI:
same inputs, same file, byte for byte. `generated_at` comes from the newest
timestamp that went into the build rather than the clock, so a rebuild of an
unchanged repo produces an identical file.

```
python src/analyse/build_topic.py
python scripts/validate.py
```

## What is in the cache

One JSON file per item, named after its cache key, in
`data/ai-cache/<council-slug>/<topic-slug>/`. Slugs come from the council and
topic names in the manifest: anything in brackets is dropped, so
`Licensing policy (alcohol, entertainment and late-night venues)` becomes
`licensing-policy`.

Every file has the same envelope:

```json
{
  "kind": "summary",
  "council_slug": "norwich-city-council",
  "topic_slug": "licensing-policy",
  "payload": { "source_id": "...", "summary": "..." },
  "ai": {
    "source_ids": ["..."], "prompt_version": "summarise-v1",
    "model": "claude-opus-5 (agent session)", "confidence": "high",
    "review_status": "needs_review", "reviewed_by": null,
    "generated_at": "2026-09-07T20:15:00+00:00", "cache_key": "..."
  }
}
```

Five kinds, and what each `payload` carries:

| kind | payload | prompt version |
|---|---|---|
| `topic` | the council block (website, tier, remit note, platforms) and the topic block (name, plain-English description, the asked / decided / done answers) | `topic-v1` |
| `summary` | `source_id` and a 2–4 sentence plain-English `summary` of that one document | `summarise-v1` |
| `event` | one thing that happened: id, stage, date, date precision, title, summary, detail bullets, source ids, a deep link, and a status for outcomes | `event-v1` |
| `linkage` | one feedback-to-decision comparison: from, to, tier, verbatim evidence quote, evidence link, explanation | `linkage-v1` |
| `gap` | something we looked for and could not find: id, stage, description | `gap-v1` |

## How `cache_key` is worked out

```
cache_key = sha256( item_key | sorted(source text fingerprints) | prompt_version )
```
joined with `|`, hex digest, lowercase.

- `item_key` is the source id for a summary, the event id for an event, the
  figure id for a figure, `<from_event>><to_event>` for a linkage, `gap:<gap id>`
  for a gap, and `topic:<council-slug>/<topic-slug>` for the overview.
- a **text fingerprint** is `sha256` of the `text` field in
  `data/processed/manifest.json` — the words the transform stage read out of the
  document. Fingerprints are taken for exactly the documents listed in
  `ai.source_ids`, sorted, so the order they were listed in cannot change the key.
  A document with no extracted text falls back to its raw `sha256`.

### Why the extracted text and not the file

The obvious thing to hash is the document as it came down the wire, and that is
what this used to do. It does not survive contact with council software. CMIS
committee pages and EngagementHQ consultation pages stamp every response with
session tokens, view-state blobs and a timestamp, so fetching the same unchanged
agenda twice gives two different raw hashes. Under the old rule, one routine
re-fetch would have marked every reviewed summary, event, comparison and figure
on the site stale — dozens of items sent back for re-checking because a hidden
form field moved.

The extracted text is what the AI output was actually written from, so it is what
the key should follow. The council changes its words, the fingerprint changes and
the item is flagged. The platform reshuffles its plumbing and nothing happens,
which is the correct amount of happening.

The raw `sha256` has not gone anywhere: it stays in every canonical record, in
the manifests and on the site, as the provenance of the download — proof of the
exact bytes that arrived and when. It is a different job from cache invalidation,
and conflating the two was the bug.

Two properties fall out of the rule, and both matter more than the key itself:

**The cache invalidates itself.** Change what a council document says, re-fetch
it, and its fingerprint changes, so the key no longer matches. `build_topic.py`
recomputes every key on every run. A mismatch means the output was written about
a version of the document that no longer exists, so the item is marked
`needs_review`, its confidence is dropped to `low`, and a gap is recorded saying
it needs re-checking. The item is kept and flagged, never silently reused and
never silently dropped.

**Two outputs from the same documents stay separate.** Five events written off
one set of minutes get five different keys, because the item key is part of the
hash.

The cache was re-keyed onto this rule in one pass by
`scripts/migrate_cache_keys.py`, which rewrote `ai.cache_key` and the filename
that mirrors it and left every payload alone. It has done its job and is kept for
the record; there is no reason to run it again.

## What happens when something is missing

Nothing is invented, and the build still exits 0 — a hole in the evidence is a
fact about what the council has published, not a build failure.

- No summary cached for a document: the source gets a visible placeholder saying
  it has not been summarised, provenance recording `model: none (no cached
  output)`, and a gap naming the document.
- An event or linkage citing a document that is not in the archive, or one that
  has changed: kept, flagged `needs_review`, gap recorded.
- No `topic` entry: placeholder remit note and answers, plus a gap.
- A source enabled in the topic's config file that produced no record: a gap.
- No `config/councils/<council-slug>.yaml`: placeholder remit note, plus a gap.
- A feedback and a decision entry that nobody has compared: a gap. Every
  feedback-to-decision pair has to be judged, including the ones judged ⚪.

## Marking something reviewed

Human review is what moves an item from "the model wrote this" to "a person
stands behind it". To review an item:

1. Open the cache file. `data/ai-cache/<council>/<topic>/<cache_key>.json`.
2. Read the payload against the sources listed in `ai.source_ids`. The documents
   are in `data/raw/`, the extracted text in `data/processed/manifest.json`.
3. Correct the payload if it is wrong. If you change the wording, leave the key
   alone — the key tracks which documents the output came from, not who edited it.
4. Set the two fields:

```json
"review_status": "reviewed",
"reviewed_by": "your name or GitHub handle"
```

5. Rebuild and validate:

```
python src/analyse/build_topic.py
python scripts/validate.py
```

A reviewer setting `reviewed` is asserting three things: every claim is in the
cited sources, no linkage tier is stronger than the evidence, and no causation is
implied that the records do not establish. If a claim cannot be checked against a
cited document, it comes out.

`confidence` is a separate judgement and stays as it is. It says how well the
sources support the reading — `high` where the document states it outright,
`medium` where it is assembled from several places or from a long document read
in part, `low` where the sources are thin. It is not a forecast about what the
council will do next.
