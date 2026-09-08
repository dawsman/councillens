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

Six kinds, and what each `payload` carries:

| kind | payload | prompt version |
|---|---|---|
| `topic` | the council block (website, tier, remit note, platforms) and the topic block (name, plain-English description, the asked / decided / done answers) | `topic-v1` |
| `summary` | `source_id` and a 2–4 sentence plain-English `summary` of that one document | `summarise-v1` |
| `event` | one thing that happened: id, stage, date, date precision, title, summary, detail bullets, source ids, a deep link, and a status for outcomes | `event-v1` |
| `linkage` | one feedback-to-decision comparison: from, to, tier, verbatim evidence quote, evidence link, explanation | `linkage-v1` |
| `measure` | one scored comparison: id, area, question, label, rule_id, target, actual, direction, period, as_of, the council's own caveat, evidence, sources | `measure-v1` |
| `gap` | something we looked for and could not find: id, stage, description | `gap-v1` |

## How `cache_key` is worked out

```
cache_key = sha256( item_key | sorted(source text fingerprints) | prompt_version )
```
joined with `|`, hex digest, lowercase.

- `item_key` is the source id for a summary, the event id for an event, the
  figure id for a figure, the measure id for a measure, `<from_event>><to_event>`
  for a linkage, `gap:<gap id>` for a gap, and
  `topic:<council-slug>/<topic-slug>` for the overview.
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

## Measures: where a red, amber or green comes from

A measure is the council's own plan or target on one side, the council's own
reported figure on the other, and a published rule in between. The rules are
council-agnostic functions in `rules.py`, one per `rule_id`, each with a
plain-English docstring that IS the published rule.

**The cache never carries a status.** It carries `rule_id`, `target`, `actual` and
`direction`; the build runs the rule and computes `status` and `status_word` from
them. Nobody can hand-colour a measure, and changing a threshold recolours every
measure that ever used it. A cache entry naming a `rule_id` that does not exist is
refused outright — the measure is left out and a gap says why — because a status
with no rule behind it is exactly what this project exists not to publish.

`rule` on the published measure is written from the rule's docstring, not from the
cache, so the sentence a reader sees is the sentence of the code that ran.
`methodology/scoring.md` is generated from the same docstrings on every build and
committed, which is why it carries a "do not edit by hand" banner. Edit `rules.py`
and rebuild; never edit the markdown.

A measure with `area: promises` is collected into the model's `promises` array
instead of `measures`. A promise is a dated commitment the council put in writing:
`target` holds the commitment and the date it gave, `actual` holds what a later
council record says happened, as one of `done_on_time`, `done_late`, `partly_done`
or `not_done`. No later record means grey — the promise cannot be checked, which is
not the same as broken.

Every side of a comparison can be null. That is the point: a council that
publishes a figure but no target scores grey, and grey is a finding about the
council's publishing, not a hole in ours.

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
- A measure naming a rule that does not exist: refused, and a gap says which rule
  was asked for. A measure whose target or actual is missing is kept and scores
  grey — "we can't tell from the published record" is an answer, not an error.

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

---

# The people stage

`build_people.py` is the same machine pointed at a different kind of record. Where
`build_topic.py` assembles the trail of one decision, this one assembles the
council's own account of who takes the decisions:

```
data/processed/manifest.json                what the council published about itself
data/ai-cache/<council>/_people/*.json  +   what was written from those documents
                                        ->  data/analysed/<council>/people.json
```

Same rules, deliberately: no network, no model calls, nothing invented, a missing
cache entry becomes a visible gap, and no council name appears in the code. The
cache key is worked out exactly as above — item key, the text fingerprints of the
documents cited, and the prompt version — so a register that is re-filed or a
directory that changes flags the item instead of quietly reprinting it.

```
python src/analyse/build_people.py
python src/analyse/build_people.py --only norwich-city-council
python scripts/validate.py
```

## How the pipeline knows which is which

A source config says so. `config/sources/<council>/<file>.yaml` may set:

```yaml
model: people
```

Default is `topic`. `build_topic.py` skips any group whose config claims another
model, so a councillor directory never becomes a feedback → decision → outcome
page. Ingest, transform and the contract gate treat both identically: one
pipeline, one canonical record, two ways of reading the result at the end.

The cache lives under `_people` rather than a topic slug. Slugs never start with
an underscore, so it cannot collide with a real topic.

## What is in the cache

Same envelope as the topic cache. Five kinds:

| kind | payload | prompt version |
|---|---|---|
| `composition` | seats by party, total, next election if published | `composition-v1` |
| `person` | one councillor: party, ward, first elected, every term, roles, committees, outside bodies, attendance, allowances, declared interests, contact | `person-v1` |
| `officer` | one senior post: role, name if published, statutory duty, pay band | `officer-v1` |
| `body` | one committee: name, purpose, members, chair | `body-v1` |
| `gap` | something looked for and not found | `gap-v1` |

Item keys: the councillor id for a person, the officer id for an officer,
`body:<slug>` for a committee, `composition:<council-slug>` for the seat count,
`gap:<id>` for a gap.

## Rules this stage will not bend

This is the part of the site most capable of doing harm, so the constraints are
tighter than anywhere else and they are enforced by the schema as well as by
whoever writes the cache.

- **Official and self-declared sources only.** The council's own directory,
  committee system, election results, allowances schedule and senior-pay
  publication — plus the Register of Members' Interests, which is the
  councillor's own declaration under the Localism Act 2011. Nothing from a social
  network, a company register, or the press.
- **No profiling.** Nothing is assembled by matching a person's name against an
  outside database. Every line traces to a document that person's own council
  published.
- **No scores, no rankings, no leaderboards.** The model carries what the record
  says and stops. Counting becomes an opinion the moment it is put in an order.
- **Data minimisation.** No family, no health, no home address. Land interests
  stay at ward level. Personal telephone numbers are not carried even where a
  council prints them; a council email address is a contact route, a mobile number
  is a person's phone.
- **Declared links are recorded, never followed.** A councillor's own website is
  printed as the council prints it and is never fetched, read or summarised.

A register entry that cannot be attributed to the councillor with certainty is
left out and the reason is written into `interests.note`. Norwich's form, for
instance, puts a councillor's interests beside their partner's, and the published
PDF does not keep the columns apart when it is read as text. Leaving those entries
out costs the page some detail. Printing a partner's employer under a councillor's
name would cost something that cannot be given back.
