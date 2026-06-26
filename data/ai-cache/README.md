# AI cache

This folder holds the **cached, versioned outputs of AI-assisted tasks** (right
now: document summaries). It is the mechanism the methodology relies on for
reproducibility:

> AI outputs are cached and versioned. The published site can be regenerated
> byte-for-byte from those cached outputs plus the raw inputs, even though the
> model itself is not deterministic.

## Why the build never calls a model

The analyse stage (`src/analyse/`) reads this cache; it does **not** call a model
live. That keeps the build deterministic, runnable in CI without secrets, and
faithful to the contract that the site regenerates byte-for-byte. Generating a
summary with a model is a **separate, offline step**, and — per the methodology —
its output is **reviewed by a person before it is committed** here. This folder is
where a model plugs in; the pipeline is not.

If no cache entry exists for a document, the analyse stage falls back to a
deterministic **extractive draft** (the document's lead sentences) and flags it
`auto-extractive` so it is never mistaken for a finished, reviewed summary.

## Layout

```
data/ai-cache/
  summaries/
    <sha256>.<prompt_version>.json   # one cached summary per document content
```

The key is the **document's content hash** (`sha256` from the canonical record)
plus the **prompt version**. Keying on the content hash means a summary is only
ever reused for the exact bytes it was written for; if the document changes, its
hash changes, the old entry no longer matches, and a fresh summary is required.

## Cache entry format

```json
{
  "source_sha256": "<the document sha256 this summary was made from>",
  "source_document_ids": ["licensing-committee"],
  "text": "Plain-English summary, reviewed by a person.",
  "prompt_version": "summary-v1",
  "model": "<model name / version that produced it>",
  "review": "approved",
  "confidence": "medium",
  "generated_at": "2026-06-26T12:00:00+00:00"
}
```

- `source_sha256` **must** match the document's hash, or the entry is ignored as
  stale.
- `review` should be `approved` before the summary is used in anything published.
  An `ai`-method summary that is still `pending` is shown only as a draft.
- `model`, `prompt_version`, `generated_at`, `source_document_ids` are the
  provenance every AI output must carry (see `methodology/`).

Entries are committed to the repo on purpose — they are inputs to the
reproducible build, not throwaway cache.
