# Contributing to CouncilLens

Thank you for helping make local government easier to understand. You do not need to be technical to contribute.

## Anyone can help
- **Report a problem:** open an issue describing what looks wrong.
- **Suggest a public source:** share a link to a public council document we have missed.
- **Improve clarity:** suggest plainer wording for a summary.

## Ground rules
1. **Open an issue before large changes** so we can agree the approach.
2. **Keep changes small and reviewable.**
3. **Link your sources** for any data change — every claim must trace to a public document.
4. **Never assert causation.** Do not claim feedback caused a decision unless the council's own records establish it (see the linkage tiers in `methodology/`).
5. **Follow the methodology and corrections policy.**

## The contract (non-negotiable)

CouncilLens is ONE pipeline per topic, reused across every council (see
`docs/architecture.md`). To keep outputs comparable, council-specific work has a
fixed, narrow surface:

- **You may add:** a config entry for a council (`config/sources.yaml`), or a
  platform adapter (`src/ingest/adapters.py`) when a council uses a platform no
  adapter supports yet.
- **You may not add:** bespoke, per-council summarising, tagging, or comparison
  logic. That logic is written once and runs everywhere.

Every record any adapter produces MUST match `data/schemas/document.schema.json`.
The schema is strict — unknown fields are rejected. This is checked twice:

1. **At ingest:** `fetch.py` validates every record and exits with an error if any
   record drifts.
2. **In CI:** the `validate` check runs `scripts/validate.py` on every pull request.

**A pull request that fails the `validate` check cannot be merged.** Changes to the
schema or the shared pipeline core require maintainer review (see
`.github/CODEOWNERS`). This is deliberate: drift is rejected automatically, not
debated case by case.

## Corrections
If something is wrong, or you are named and want it reviewed, open an issue or contact the maintainers. We take accuracy seriously and will respond.

By contributing, you agree your contributions are released under the project's MIT licence.
