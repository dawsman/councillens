<!-- GENERATED FILE. Do not edit by hand.
     Written by src/analyse/build_topic.py from the docstrings in
     src/analyse/rules.py. Change a rule there and rebuild. -->

# How a red, amber or green status is worked out

CouncilLens does not grade councils. A colour on this site is never our opinion
about whether a council is doing well. It is the result of a rule, written down
here in plain English and applied by code, comparing the council's own numbers
against each other: its own budget against its own outturn, its own target
against its own reported figure, its own written promise against its own later
report.

Four answers are possible, and the word matters more than the colour:

| Colour | Word | What it means |
|---|---|---|
| Green | Met | The council's own record shows it did what it planned. |
| Amber | Close | Nearly, or late, or only partly. |
| Red | Missed | The council's own record shows it did not. |
| Grey | Can't tell | The published record does not answer the question. |

Grey is a real answer and an honest one. It is not a mark against the council and
it is not a shrug from us: it says the documents a resident can read do not
settle the question. Where a whole area is grey, that is worth knowing on its own.

Every status on the site shows, one tap away, the rule that produced it, the
target, the figure, a link to the document both came from, and any explanation the
council itself gave. If you think a status is wrong, the numbers behind it are all
public and there is a correction link at the bottom of every page.

## The rules

### Did the council spend what it planned on day-to-day services?

Rule id `budget-variance-v1`.

Green if the year's actual spending came within 2% of the budget the council approved, amber if it came within 5%, red if it missed by more than 5%, and grey if the council has not published an outturn for that year yet.

The comparison is the council's own: its approved budget against the outturn it reports in its own accounts. Over and under count the same. An underspend is not automatically good news — money not spent is a service not delivered or a plan that was wrong — and an overspend is not automatically bad. The measure is how close the plan came to the year, nothing more.

| What decides the colour | Value |
|---|---|
| Within this much of budget is green | 2% |
| Within this much of budget is amber | 5% |

### Did the council build what it said it would build?

Rule id `capital-delivery-v1`.

Green if the council spent at least 90% of its approved building programme that year, amber if it spent at least 70%, red if it spent less than 70%, and grey if no outturn has been published.

A council's capital programme is the list of buildings, roads, homes and repairs it has agreed to pay for. Money not spent is not money lost — most of it rolls into next year — but a programme that is only half delivered is a programme that was never a reliable statement of what would happen.

| What decides the colour | Value |
|---|---|
| Delivered at least this share is green | 90% |
| Delivered at least this share is amber | 70% |

### Did the council hit its own target, and if it missed, did it cross its own warning line?

Rule id `council-threshold-v1`.

Green if the council's reported figure met or beat the target it set itself. Amber if it missed the target but stayed on the safe side of the council's own intervention level — the point at which the council says it will step in and act. Red if it crossed that line. Grey if the council has not published a target, an intervention level, or the figure.

This is the strictest form of "the council's own rule": both the pass mark and the alarm line are the council's, published beside the figure in its own performance report, so the colour here should be the colour on the council's own dashboard. Where a council publishes a target but no alarm line, target-met-v1 is used instead.

| What decides the colour | Value |
|---|---|
| Met or beat the council's own target | green |
| Missed the target, stayed the safe side of the council's own intervention level | amber |
| Crossed the council's own intervention level | red |

### Did the council do the thing it put in writing, by the date it gave?

Rule id `promise-kept-v1`.

Green if a later council record confirms it was done by that date. Amber if a later record shows it was done late, or only partly. Red if a later record says it was not done. Grey if no later council record mentions it — which means the promise cannot be checked, not that it was broken.

A promise here is narrow on purpose: a dated commitment the council made in one of its own published papers ("a final policy will come to Council in November 2026", "£3.2m of savings in 2025/26"). Manifestos, speeches and press quotes are not promises for this purpose, because the council as an organisation did not write them down. `target` carries the commitment in the council's own words with the date it gave; `actual` carries what the later record says.

| What decides the colour | Value |
|---|---|
| Done by the promised date | green |
| Done late, or only partly done | amber |
| A later record says it was not done | red |
| No later record mentions it | grey |

### Does the council hold as much in reserve as its own policy says it should?

Rule id `reserves-vs-policy-v1`.

Green if the money set aside for emergencies is at or above the minimum the council's own finance officer sets and publishes. Amber if it is below that minimum but by less than a tenth of it. Red if it is further below. Grey if the council does not publish a minimum, or has not published the balance.

The floor is the council's, not ours. Every council's chief finance officer has to state a prudent minimum for the general reserve and say whether the balance is adequate, so this compares the council against the line it drew itself. Holding much more than the minimum is not scored: reserves that look large are usually ring-fenced for things like council housing, and calling that "hoarding" would be an opinion.

| What decides the colour | Value |
|---|---|
| At or above the council's own minimum | green |
| Below the minimum by less than this share of it | 10% |

### Did the council actually make the savings it said it would?

Rule id `savings-delivered-v1`.

Green if at least 95% of the savings target was delivered, amber if at least 80% was, red if less than 80% was, and grey if the council does not report what it delivered — which is common, and is itself worth knowing.

Councils set a savings target when they set the budget, then report against it afterwards, or don't. Where a council only publishes the savings it *found* when writing the budget, and never says how much actually arrived, this measure stays grey and says so.

| What decides the colour | Value |
|---|---|
| Delivered at least this share of the target is green | 95% |
| Delivered at least this share of the target is amber | 80% |

### Did the council hit the target it set itself?

Rule id `target-met-v1`.

Green if the council's own reported figure met or beat its own published target. Amber if it missed but came within 10% of the target. Red if it missed by more than 10%. Grey if the council publishes a figure but no target, or a target but no figure — which is the commonest case, and is worth saying out loud.

Both numbers belong to the council. We do not invent targets, borrow another council's, or compare a council against an average. `direction` says which way is good: `higher_is_better` (homes let, calls answered), `lower_is_better` (days to process a claim, money borrowed against a limit) or `on_target`, where being under is as much of a miss as being over.

| What decides the colour | Value |
|---|---|
| Missing by no more than this share of the target is amber | 10% |
