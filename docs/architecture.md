# CouncilLens architecture: one pipeline, every council

**Principle: one pipeline per topic, replicated across all councils. Council-specific
detail lives in configuration and in platform adapters — never in the pipeline.**

## The problem this solves

If onboarding a council means writing a new pipeline, two things go wrong. The
project becomes unmaintainable (a pipeline per council does not scale), and — worse
— outputs stop being comparable. If Norwich's figures come from one person's
pipeline and another council's from someone else's, "feedback vs decision vs
outcome" means something slightly different in each place, and the comparison the
project exists to make turns to mush.

So the rule is the opposite: the pipeline is written once per topic and reused
unchanged across every council.

## Why this is feasible

UK councils look bespoke but mostly run on a small set of shared platforms:

- **Committee documents** (agendas, minutes, decisions): almost always CMIS or
  modern.gov. Norwich uses CMIS.
- **Council websites**: increasingly LocalGov Drupal, a shared open-source platform
  built to standardise. Norwich's site runs on it.
- **Consultations**: a handful of engagement vendors (Citizen Space, Commonplace,
  EngagementHQ and similar).
- **Spending / performance**: published to a common shape under the Local
  Government Transparency Code.

Variation is real, but it clusters into a few platform shapes — not 300 unique
councils. That is what lets a small number of adapters cover the whole country.

## The three layers

1. **Adapters — one per platform, not per council.** One CMIS adapter serves every
   CMIS council. This is the only place platform-specific code is allowed to live.
2. **The canonical record — the contract.** Every adapter must emit the same shape,
   defined by `data/schemas/document.schema.json`. The schema is strict: unknown
   fields are rejected. All messiness is absorbed at this boundary, so nothing
   downstream ever sees a raw council quirk.
3. **The topic pipeline — council-agnostic.** Summarise, tag, compare and linkage
   logic run only on canonical records, so they are written once and behave
   identically everywhere.

The single pipeline you want is only possible *because* layer 2 normalises
everything first. The schema is the load-bearing wall.

## Where council variation goes

Into config and adapters — never into pipeline code.

`config/sources.yaml` is the per-council map: for Norwich, the licensing topic =
this consultation (feedback) + this committee (decision) + this policy page
(outcome), each tagged with the platform that serves it. Onboarding a new council
is writing one reviewed config block. You only write code when a council uses a
platform no adapter supports yet — and even then it is one adapter shared by every
council on that platform.

## The contract is non-negotiable

There are no per-council pipelines, so there is nothing at the pipeline level to
drift. The only drift surface is (a) an adapter emitting an off-contract record, or
(b) someone adding bespoke per-council logic. Both are gated so that drift is
flagged immediately and cannot be merged:

- **At ingest.** `fetch.py` validates every record against the schema and exits
  with an error if any record drifts. Bad data never reaches the manifest.
- **In CI.** `scripts/validate.py` re-checks every record against the same schema
  on every pull request. A failing check is a failing build.
- **At merge.** Branch protection requires the `validate` check to pass before a
  pull request can merge to `main`. This is the step that turns "flagged" into
  "not integrated".
- **By review.** `.github/CODEOWNERS` requires maintainer sign-off on the schema
  and the shared pipeline core, so the contract itself cannot be weakened without
  explicit approval. The pull-request template makes the contributor confirm they
  have not added bespoke per-council logic.

The effect: a contribution that drifts from the contract is rejected automatically
and never merged — not argued case by case.

## Two switches the maintainer must set (one-time)

Two pieces cannot be set by an automated token and must be enabled by a repo admin:

1. **Add `.github/workflows/validate.yml`** (provided separately). Writing workflow
   files needs the token's Workflows permission, so this one is added by hand or
   with an upgraded token. Without it, the CI check does not run.
2. **Turn on branch protection** for `main` (Settings -> Branches): require the
   `validate` status check, require a pull request before merging, and require
   review (including code-owner review). Without this, a failing check would not
   actually block a merge.

Until both are on, the contract is enforced at ingest and runnable locally, but not
yet binding on merge.

## The honest hard parts

- **Topic -> body mapping** is the one genuinely council-specific judgement (Norwich
  files licensing under "Licensing committee"; another council may fold it into
  "Regulatory"). This stays a small, human-maintained, reviewed entry in config.
  Cheap, but real.
- **Two-tier areas** split a topic across authorities (highways are Norfolk County,
  not Norwich City). Model the topic as the spine and let multiple authorities
  attach to it.
- **The long tail publishes badly** — scanned PDFs, no consultation platform. There,
  fall back to the generic adapter and OCR, accept lower confidence, and *label* it
  with the methodology's confidence / linkage tiers rather than letting weak
  coverage quietly drag the average down.

## Current status

- Canonical schema (the contract): in place, strict.
- Ingest-time validation: in place (`fetch.py`).
- Adapter model: in place (`src/ingest/adapters.py`) with generic + CMIS; more
  platforms to follow.
- CI gate script: in place (`scripts/validate.py`).
- CI workflow + branch protection: pending the two one-time switches above.
