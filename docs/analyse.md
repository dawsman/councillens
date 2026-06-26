# The analyse stage

The analyse stage is where CouncilLens stops collecting documents and starts
producing something a resident can read: a plain-English summary of every
document, lined up as **feedback → decision → outcome**, with a linkage tier
(🟢 / 🟡 / ⚪) on every relationship.

It is the council-agnostic topic pipeline from
[`architecture.md`](architecture.md): it runs only on canonical records, so it
behaves identically for every council. There is deliberately **no per-council
logic** here.

## Input and output

```
data/processed/manifest.json   →   data/analysis/<topic>.json   (+ <topic>.md)
        (transform stage)               (validated against
                                         data/schemas/analysis.schema.json)
```

- **`<topic>.json`** is the structured artifact: summarised documents + linkages,
  validated against the analysis contract. This is what a future `publish` stage
  renders into the site.
- **`<topic>.md`** is a readable preview of the same data, generated on the spot
  so the stage produces something legible the moment it runs. (Styled publishing
  is the publish stage's job; see [`example-analysis.md`](example-analysis.md) for
  what it looks like.)

Run it after ingest and transform:

```bash
python src/ingest/fetch.py        # data/raw/manifest.json
python src/transform/extract.py   # data/processed/manifest.json
python src/analyse/analyse.py     # data/analysis/<topic>.json + .md
```

## Summarising documents (`summarise.py`)

The methodology lets AI assist with bounded tasks, requires every AI output to
carry provenance, and requires AI outputs to be **cached and versioned** so the
site regenerates byte-for-byte. The summariser honours all three:

1. **Cache first.** If a human-reviewed AI summary exists in
   [`data/ai-cache/`](../data/ai-cache/README.md) for the document's exact content
   (keyed by its `sha256` + prompt version), it is used. **The build never calls a
   model live** — that keeps it deterministic and runnable in CI without secrets.
   Producing a summary with a model is a separate, offline, human-reviewed step;
   the cache is where a model plugs in, not the pipeline.

2. **Deterministic fallback.** With no cache entry, the stage produces an
   *extractive draft* (the document's lead sentences) and flags it
   `auto-extractive`, so a placeholder is never mistaken for a finished, reviewed
   summary.

Every summary — cached or extractive — carries the full provenance envelope:
source document IDs, prompt version, model (or method id), review flag, and a
timestamp.

## Linkage tiers (`linkage.py`)

The tier is the load-bearing claim of the whole project, so it is assigned by a
**deterministic, auditable rule — not by AI** — and it always **defaults down**
unless the records prove otherwise. Every tier records the evidence it rests on.

| Tier | When | What it means |
|------|------|---------------|
| 🟢 **confirmed** | The later record **cites** the earlier source (its URL or full title appears in the text). | The records themselves document the connection. |
| 🟡 **possible** | Same topic, configured as `feedback → decision` (or `decision → outcome`), but **no citation found**. | A relationship exists; causation is not claimed. |
| ⚪ **none** | The later stage has **no document yet**. | "No link found / still waiting" — said plainly. |

Only 🟢 asserts influence, and the citation check is intentionally conservative
(host+path of the URL, or the full document title — never a single shared
keyword), so 🟢 stays trustworthy. Everything else is 🟡 or ⚪.

> **On dates.** The canonical record carries a *fetch* time, not the document's own
> publication date, so we do not rely on it to prove precedence — that is exactly
> why a same-topic pair with no citation stays 🟡 and never silently becomes 🟢.
> When document dates are added to the contract, the rule can tighten.

## Determinism

The analyse output is a **pure function of its inputs** (the processed manifest +
the AI cache). No wall-clock time is written into it — an extractive summary's
timestamp is the source document's fetch time. So two builds of the same inputs
are byte-for-byte identical, which is what lets the published site be regenerated
from cached outputs plus raw inputs. `tests/test_analyse.py` asserts this.

## Human review before publishing

Per the methodology, any summary or linkage is reviewed by a person before it is
published. The stage records this state but does not block on it: summaries are
`approved` / `pending` / `auto-extractive`, and linkages are `pending` until
reviewed. A future `publish` stage gates on `approved`.

## What stays out of this stage

No council-specific summarising, tagging, or comparison logic. If a council needs
different handling, that belongs in config or a platform adapter (see
[`CONTRIBUTING.md`](../CONTRIBUTING.md)), never here — otherwise the comparison the
project exists to make stops meaning the same thing across councils.
