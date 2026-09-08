<!-- GENERATED FILE. Do not edit by hand.
     Written by src/analyse/build_topic.py from the docstrings in
     src/analyse/rules.py. Change a rule there and rebuild. -->

# How a red, amber or green status is worked out

CouncilLens does not grade councils. A colour on this site is not a view of ours
about whether a council is doing well: it is what a published rule returns when
it is run against the council's own numbers — its own budget against its own
outturn, its own target against its own reported figure, its own written promise
against its own later report. The rules are all written out below, in plain
English, and the code that applies them is the code these words come from. Where
the council publishes its own target and its own warning level we use those.
Where it does not, we use the fixed lines stated here, and those lines are ours.
The numbers are always the council's.

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

## Which numbers are the council's, and which are ours

Every status on this site is worked out by the rules below, and the numbers being
compared are always the council's own. Where the council publishes both its target
and the warning level at which it says it will step in, we use those, and the
colour you see should be the colour on the council's own dashboard. Where it
publishes a target and no warning level, the target is still the council's and the
only thing we add is how near a miss counts as "close". And where the council
publishes no target at all — for how closely it keeps to its own budget, how much
of its building programme it delivers, how much of a savings plan arrives — we
compare the council against its own plan and we choose where the line falls. Those
lines are set out under each rule, with the reason we drew them there. They are
ours, nobody at the council picked them, and you are free to think they are in the
wrong place. The numbers on both sides of every comparison are the council's.

Every status on the site shows, one tap away, the rule that produced it, the
target, the figure, a link to the document both came from, and any explanation the
council itself gave. If you think a status is wrong, the numbers behind it are all
public and there is a correction link at the bottom of every page.

## The rules

### Did the council spend what it planned on day-to-day services?

Rule id `budget-variance-v1`.

Green if the year's actual spending came within 2% of the budget the council approved, amber if it came within 5%, red if it missed by more than 5%, and grey if the council has not published an outturn for that year yet.

The comparison is the council's own: its approved budget against the outturn it reports in its own accounts. Over and under count the same. An underspend is not automatically good news — money not spent is a service not delivered or a plan that was wrong — and an overspend is not automatically bad. The measure is how close the plan came to the year, nothing more.

The 2% and 5% lines are ours, not the council's. No council publishes a rule saying how far off its own budget is acceptable, so somebody has to draw the line and say where. We put it where a finance officer's own language changes: a variance inside 2% is the sort of thing an outturn report calls routine, and beyond 5% it is the sort of thing that gets its own paragraph. Both numbers are printed here so you can disagree with them. The figures being compared are always the council's.

| What decides the colour | Value |
|---|---|
| Within this much of budget is green | 2% |
| Within this much of budget is amber | 5% |

### Did the council build what it said it would build?

Rule id `capital-delivery-v1`.

Green if the council spent at least 90% of its approved building programme that year, amber if it spent at least 70%, red if it spent less than 70%, and grey if no outturn has been published.

A council's capital programme is the list of buildings, roads, homes and repairs it has agreed to pay for. Money not spent is not money lost — most of it rolls into next year — but a programme that is only half delivered is a programme that was never a reliable statement of what would happen.

The 90% and 70% lines are ours, and so is the idea that the whole programme is the thing to measure against: the council publishes what it approved and what it spent, and no delivery target at all. We chose 90% because a programme that lands within a tenth of itself is a plan that broadly happened, and 70% because below that the published programme is describing a different year from the one that occurred. The percentage is our division of two council figures.

| What decides the colour | Value |
|---|---|
| Delivered at least this share is green | 90% |
| Delivered at least this share is amber | 70% |

### Did the council hit its own target, and if it missed, did it cross its own warning line?

Rule id `council-threshold-v1`.

Green if the council's reported figure met or beat the target it set itself. Amber if it missed the target but stayed on the safe side of the council's own intervention level — the point at which the council says it will step in and act. Red if it crossed that line. Grey if the council has not published a target, an intervention level, or the figure.

This is the strictest form of "the council's own rule", and the only one where we choose nothing at all: both the pass mark and the alarm line are the council's, published beside the figure in its own performance report, so the colour here should be the colour on the council's own dashboard. Where a council publishes a target but no alarm line, target-met-v1 is used instead.

| What decides the colour | Value |
|---|---|
| Met or beat the council's own target | green |
| Missed the target, stayed the safe side of the council's own intervention level | amber |
| Crossed the council's own intervention level | red |

### Did the council do the thing it put in writing, by the date it gave?

Rule id `promise-kept-v1`.

Green if a later council record confirms it was done by that date. Amber if a later record shows it was done late, or only partly. Red if a later record says it was not done. Grey if no later council record mentions it — which means the promise cannot be checked, not that it was broken.

A promise here is narrow on purpose: a dated commitment the council made in one of its own published papers ("a final policy will come to Council in November 2026", "£3.2m of savings in 2025/26"). Manifestos, speeches and press quotes are not promises for this purpose, because the council as an organisation did not write them down. `target` carries the commitment in the council's own words with the date it gave; `actual` carries what the later record says.

Nothing here is a threshold we chose. The words are the council's, the date is the council's, and the later record is the council's. The only judgement is whether a later document says done, done late, partly done or not done, and where no later document says anything the answer is grey rather than a guess.

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

The floor is the council's. The one thing that is ours is how far below it still counts as a warning rather than a breach: a tenth of the minimum. We drew it there because a reserve a little under its floor is a year to watch and a reserve well under it is a different kind of problem, and because refusing to distinguish them would make the amber pointless.

| What decides the colour | Value |
|---|---|
| At or above the council's own minimum | green |
| Below the minimum by less than this share of it | 10% |

### Did the council actually make the savings it said it would?

Rule id `savings-delivered-v1`.

Green if at least 95% of the savings target was delivered, amber if at least 80% was, red if less than 80% was, and grey if the council does not report what it delivered — which is common, and is itself worth knowing.

Councils set a savings target when they set the budget, then report against it afterwards, or don't. Where a council only publishes the savings it *found* when writing the budget, and never says how much actually arrived, this measure stays grey and says so.

The 95% and 80% lines are ours. A savings plan is a commitment to find a sum of money, and a plan that lands within a twentieth of it has essentially worked; below four fifths the shortfall has to be filled from somewhere else, usually reserves, which is a decision with consequences for the following year. The savings target itself is always the council's own.

| What decides the colour | Value |
|---|---|
| Delivered at least this share of the target is green | 95% |
| Delivered at least this share of the target is amber | 80% |

### Did the council hit the target it set itself?

Rule id `target-met-v1`.

Green if the council's own reported figure met or beat its own published target. Amber if it missed but came within 10% of the target. Red if it missed by more than 10%. Grey if the council publishes a figure but no target, or a target but no figure — which is the commonest case, and is worth saying out loud.

Both numbers belong to the council. We do not invent targets, borrow another council's, or compare a council against an average. `direction` says which way is good: `higher_is_better` (homes let, calls answered), `lower_is_better` (days to process a claim, money borrowed against a limit) or `on_target`, where being under is as much of a miss as being over.

The target is always the council's. The 10% is ours: it exists so that a near miss is not painted the same colour as a wide one, and a tenth of the target is the roundest honest way to say "nearly". Where the council publishes its own warning level as well as its target, this rule is not used at all — council-threshold-v1 is, and then no number in the comparison is ours.

| What decides the colour | Value |
|---|---|
| Missing by no more than this share of the target is amber | 10% |
