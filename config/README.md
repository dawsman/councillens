# Config

- `councils/<council-slug>.yaml` — who a council is: website, tier, plain-English remit note, which platforms it publishes on. Shared by every topic for that council.
- `sources/<council-slug>/<topic-slug>.yaml` — one council + one topic: `council:`, `topic:`, and the reviewed list of public `sources:` that evidence it.
- The slugs in the paths are load-bearing: the directory must equal the slug of `council:`, the filename the slug of `topic:`. That is what `--only <council-slug>/<topic-slug>` selects.
- Adding a topic or a council is adding a file here. No pipeline code changes.
- Every URL is fetched and read by a person before it is added; anything that could not be verified stays `enabled: false` with a note saying what was searched.
