## What does this PR do?

<!-- A sentence or two. -->

## Contract checklist (required)

- [ ] This PR changes **adapters or config only** — it does not add bespoke,
      per-council summarising, tagging, or comparison logic.
- [ ] Every record produced still matches `data/schemas/document.schema.json`
      (I ran `python scripts/validate.py` and it passed).
- [ ] New council? It is a new **config** entry in `config/sources.yaml` (and a new
      adapter only if the platform is not supported yet).
- [ ] All sources are **public** and linked.
- [ ] No causation is asserted beyond what the records support (see the linkage
      tiers in `methodology/`).

> The `validate` check must pass before this can be merged. Changes to the schema
> or pipeline core need maintainer (code-owner) review.
