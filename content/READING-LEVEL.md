# Reading level: before and after

Target from the wave 4 brief: Flesch reading ease of 60 or better, reading age 12 to 14.

Everything below was measured with `content/reading_level.py`, which uses `textstat` where it is
installed and falls back to its own Flesch implementation where it is not. Both are reported. They
disagree by two or three points, which is normal, and I have quoted the harsher of the two
throughout.

Two things worth knowing before you read the numbers.

Flesch is a crude instrument. It counts syllables and sentence lengths and knows nothing about
whether a sentence makes sense. "Cumulative impact assessment" and "banding" both score well and
neither means anything to a 14-year-old. So the scores below are a floor, not a pass mark, and the
jargon list at the end matters more than the arithmetic.

Second: headings and list items are counted as sentences, which flatters any page with a lot of
structure. That is defensible, because a reader does meet them as separate units, but do not compare
these numbers with a score from a plain essay.

## 1. The live site as it stands

Measured from `https://dawsman.github.io/councillens/` and its pages on 8 September 2026. Quotes
from council documents and document titles are excluded, because those are the council's words and
we do not rewrite them.

| Page | Flesch (textstat) | Reading age | Words per sentence | Words |
|---|---|---|---|---|
| Home | 71.8 | 10.3 | 6.8 | 280 |
| Norwich City Council | 65.5 | 12.2 | 11.2 | 335 |
| Licensing policy | **56.9** | 14.2 | 13.5 | 6,430 |
| Housing allocations | **55.6** | 14.9 | 15.4 | 6,368 |
| How we work | **58.7** | 13.5 | 13.0 | 2,123 |

Three pages sit below the target. The two topic pages are the ones that matter, because they carry
almost all the words on the site.

## 2. Where the problem actually is

This is the finding I would lead with.

The topic pages are roughly nine parts AI-written cache content to one part template chrome. So I
scored the two layers separately.

| Layer | Flesch | Reading age | Words per sentence |
|---|---|---|---|
| Template strings (`src/publish/templates` plus the label constants in `build.py`) | 69.2 | 12.1 | 13.8 |
| AI cache prose, licensing topic | **53.0** | 16.0 | 21.0 |
| AI cache prose, housing topic | **49.4** | 17.2 | 24.3 |

The templates already pass. The cache content does not, and it is dragging the whole page down.
Rewriting every string on the site would move the licensing page by perhaps two points. Fixing the
cache prose would move it by eight or nine.

The single biggest lever is sentence length. Cache summaries average 21 to 24 words per sentence.
Bring that to 15 and both topic pages clear 60 without a single word being replaced.

## 3. After: my proposed template changes

From `content/COPY-CHANGES.md`. Forty-nine strings reviewed, thirty-five changed, fourteen left
alone because they were already right.

| | Flesch | Reading age | Words per sentence |
|---|---|---|---|
| The 35 strings I changed, before | 68.7 | 12.1 | 13.3 |
| The 35 strings I changed, after | **78.0** | 10.4 | 11.4 |
| All 49 reviewed strings, before | 69.2 | 12.1 | 13.8 |
| All 49 reviewed strings, after | **77.8** | 10.5 | 12.0 |

Nine points, and almost all of it came from splitting sentences rather than from simplifying words.
Word count went up by 4%, which is the trade: shorter sentences need more of them.

## 4. After: my new content

| File | Flesch | Reading age | Words |
|---|---|---|---|
| `content/explainers.yaml` | 76.9 | 11.3 | 1,122 |
| `content/glossary.yaml` | 65.1 | 12.7 | 3,728 |
| `learn/index.md` | 66.4 | 12.9 | 458 |
| `learn/how-a-council-works.md` | 69.5 | 11.3 | 520 |
| `learn/who-decides-what.md` | 68.0 | 11.5 | 486 |
| `learn/where-the-money-comes-from.md` | 73.4 | 10.8 | 534 |
| `learn/read-a-budget-in-10-minutes.md` | 72.9 | 11.4 | 517 |
| `learn/how-to-read-minutes.md` | 61.5 | 12.6 | 529 |
| `learn/how-consultations-work.md` | 67.3 | 11.9 | 526 |
| `learn/check-a-claim.md` | 66.1 | 12.0 | 530 |
| `learn/your-council-in-five-questions.md` | 75.5 | 10.4 | 493 |
| `learn/classroom-activities.md` | 62.3 | 12.7 | 564 |

Every file clears 60. The lowest is `how-to-read-minutes.md` at 61.5, which is where it should be:
that page has to use words like resolution, recommendation and declaration of interest, and teaching
them is the point of it.

The glossary sits at 65.1 partly because a definition cannot avoid naming the thing it defines.

## 5. Jargon in the reviewed cache content

**I have not edited any of this.** The cache belongs to the pipeline and to the measures-researcher,
and rewriting a reviewed entry would break its cache key. This is a list for a later pass, ordered
by how much damage each item does.

### Tier 1: the reader stops reading

| Term | Where | Suggested fix |
|---|---|---|
| Sentences over 30 words | Throughout both topics. Housing averages 24.3 words per sentence. | Split them. This alone is worth eight Flesch points and costs nothing in accuracy. |
| "The five changes: a conversation with an adviser for every applicant, with those who do not qualify…" | housing, event detail | Scores 0.6 on Flesch. One 78-word sentence carrying five separate proposals, divided by semicolons. It has to become a list. |
| "The five bands, in the council's own order: emergency…; gold…; silver…; bronze…; standard…" | housing, event detail | Same shape. Already a list in meaning, so make it one on the page. |
| "commences public consultation" | licensing, two summaries | The council's own slip, quoted correctly. Keep the quote, add "(the council's wording)" so it does not read as ours. |
| "as a second limb" | licensing, Cabinet summary | Legal register. "and secondly". |

### Tier 2: needs a glossary link on first use

All of these now have entries in `content/glossary.yaml`, so the fix is a link rather than a
rewrite: **General Fund**, **Housing Revenue Account**, **outturn**, **precept**, **reserves**,
**capital programme**, **Cabinet** (146 uses), **Scrutiny committee** (41), **Full Council** (15),
**minutes** (63), **agenda**, **resolution** and "RESOLVED" (7), **officer** (38), **equality impact
assessment** (5), **allocations scheme**, **banding** and silver band (9), **local connection** (7),
**mutual exchange**, **premises licence** (6), **personal licence**, **temporary event notice**,
**statement of licensing policy** (6), **cumulative impact** assessment (3), **rateable value**,
**business rates**, **Medium Term Financial Strategy** and MTFS (7), **agent of change** (4).

Counts are occurrences across `data/ai-cache`, from the scan saved at
`~/tmp/agent-scratch/councillens/plain-english-editor/jargon-scan.txt`.

### Tier 3: replace the word, keep the meaning

| Found | Replace with | Uses |
|---|---|---|
| facilitate | allow, make possible | 1 |
| provision (meaning a rule) | rule | 3 |
| governance | how it is run | 3 |
| framework | rules, set of rules | 2 |
| general needs housing | ordinary council homes | 1 |
| void (a property) | empty home | none yet in the cache, but standard in council papers and worth pre-empting |
| in accordance with | under, following | in quotations only |
| notwithstanding | despite | in quotations only |

Where any of these sits inside a quotation from the council, it stays. Our words get simplified; the
council's words get quoted whole. That distinction is already the site's method for facts, and it
should be its method for vocabulary too.

### One thing to leave alone

The housing topic's plain-English line quotes the council calling its scheme "a fairer, more
efficient and transparent way of allocating the social housing available". That sentence scores
badly and should stay exactly as it is. It is the council's claim about itself, in its own words,
and paraphrasing it would quietly turn its claim into ours.

## How to re-run this

```
python content/reading_level.py html pages/index.html pages/councils/*/*/index.html
python content/reading_level.py text content/learn/*.md content/glossary.yaml
```

The script needs nothing but Python 3.10 or later. Install `textstat` in the venv for the second
opinion; it works without it.
