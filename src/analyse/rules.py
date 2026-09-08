#!/usr/bin/env python3
"""The published rules that turn a council's own numbers into a colour.

CouncilLens never tells anyone what to think about a council. So a red, amber or
green status is never our opinion. It is the result of a rule — written down here
in plain English, applied by code, and printed on the site next to the number it
judged. The council supplies both sides of every comparison: its own budget
against its own outturn, its own target against its own reported actual, its own
written promise against its own later report.

Four statuses, and grey is a real answer:

    green  Met         the council's own record shows it did what it planned
    amber  Close       nearly, or late, or partly
    red    Missed      the council's own record shows it did not
    grey   Can't tell  the published record does not answer the question

Grey is not a failure of the council and it is not a failure of ours. It is a
fact about what has been published, and saying so honestly beats guessing.

Three properties this module has to keep:

1. **Council-agnostic.** No council name, committee name, document or URL appears
   here. A rule that works for Norwich works unchanged for every other council.
2. **The docstring IS the published rule.** `methodology/scoring.md` is generated
   from these docstrings by the build, so the words on the site and the code that
   produced the colour can never drift apart. Edit the rule, and the published
   wording changes with it.
3. **Thresholds are named constants**, declared beside the rule that uses them,
   so a reader can see the number that decided a colour without reading code.

Adding a rule: write the function, give it a docstring whose first paragraph is
the rule in one sentence a 14-year-old could follow, register it in `RULES`, and
rebuild. `build_topic.py` refuses any measure whose `rule_id` is not in `RULES`,
so a typo cannot quietly publish an uncoloured measure.
"""
from __future__ import annotations

# The four statuses, and the word shown on the site next to each colour. The word
# is what a reader relies on: colour is reinforcement, never the only carrier.
GREEN, AMBER, RED, GREY = "green", "amber", "red", "grey"

STATUS_WORDS = {
    GREEN: "Met",
    AMBER: "Close",
    RED: "Missed",
    GREY: "Can't tell",
}

# Which way is good. Carried on every measure so a rule never has to guess.
DIRECTIONS = ("higher_is_better", "lower_is_better", "on_target")


# --------------------------------------------------------------------------
# Reading the numbers
# --------------------------------------------------------------------------

def _number(side):
    """The numeric value on one side of a comparison, or None if there isn't one.

    A measure's `target` and `actual` are small objects — {value, display, unit} —
    or null where the council has not published that side. Anything that is not a
    plain number reads as "not published", which is what makes grey automatic
    rather than something an author has to remember to set."""
    if not isinstance(side, dict):
        return None
    value = side.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _word(side):
    """The value on one side as a lowercase word, for rules that compare outcomes
    rather than quantities (a promise kept or not kept, say)."""
    if not isinstance(side, dict):
        return None
    value = side.get("value")
    if not isinstance(value, str):
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_") or None


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------

# Day-to-day spending. A council's revenue budget is a plan for one year, and no
# plan lands exactly: 2% either way is normal housekeeping, 5% starts to say the
# plan was not a good description of the year.
BUDGET_VARIANCE_GREEN_PCT = 2.0
BUDGET_VARIANCE_AMBER_PCT = 5.0


def budget_variance_v1(target, actual, direction=None, threshold=None):
    """Did the council spend what it planned on day-to-day services?

    Green if the year's actual spending came within 2% of the budget the council
    approved, amber if it came within 5%, red if it missed by more than 5%, and
    grey if the council has not published an outturn for that year yet.

    The comparison is the council's own: its approved budget against the outturn
    it reports in its own accounts. Over and under count the same. An underspend
    is not automatically good news — money not spent is a service not delivered
    or a plan that was wrong — and an overspend is not automatically bad. The
    measure is how close the plan came to the year, nothing more.

    `actual.value` is the variance as a percentage of the approved budget,
    negative for an underspend and positive for an overspend.
    """
    variance = _number(actual)
    if variance is None:
        return GREY
    size = abs(variance)
    if size <= BUDGET_VARIANCE_GREEN_PCT:
        return GREEN
    if size <= BUDGET_VARIANCE_AMBER_PCT:
        return AMBER
    return RED


# Building work. Capital programmes slip for real reasons — weather, contractors,
# planning — so nobody expects 100%. Below 70% the published programme has
# stopped being a useful description of what will actually be built.
CAPITAL_DELIVERY_GREEN_PCT = 90.0
CAPITAL_DELIVERY_AMBER_PCT = 70.0


def capital_delivery_v1(target, actual, direction=None, threshold=None):
    """Did the council build what it said it would build?

    Green if the council spent at least 90% of its approved building programme
    that year, amber if it spent at least 70%, red if it spent less than 70%, and
    grey if no outturn has been published.

    A council's capital programme is the list of buildings, roads, homes and
    repairs it has agreed to pay for. Money not spent is not money lost — most of
    it rolls into next year — but a programme that is only half delivered is a
    programme that was never a reliable statement of what would happen.

    `actual.value` is the money actually spent as a percentage of the approved
    programme.
    """
    delivered = _number(actual)
    if delivered is None:
        return GREY
    if delivered >= CAPITAL_DELIVERY_GREEN_PCT:
        return GREEN
    if delivered >= CAPITAL_DELIVERY_AMBER_PCT:
        return AMBER
    return RED


# How near a miss still counts as "close": a tenth of the target.
TARGET_CLOSE_FRACTION = 0.10


def target_met_v1(target, actual, direction="higher_is_better", threshold=None):
    """Did the council hit the target it set itself?

    Green if the council's own reported figure met or beat its own published
    target. Amber if it missed but came within 10% of the target. Red if it
    missed by more than 10%. Grey if the council publishes a figure but no
    target, or a target but no figure — which is the commonest case, and is worth
    saying out loud.

    Both numbers belong to the council. We do not invent targets, borrow another
    council's, or compare a council against an average. `direction` says which way
    is good: `higher_is_better` (homes let, calls answered), `lower_is_better`
    (days to process a claim, money borrowed against a limit) or `on_target`,
    where being under is as much of a miss as being over.
    """
    want = _number(target)
    got = _number(actual)
    if want is None or got is None:
        return GREY

    if direction == "lower_is_better":
        if got <= want:
            return GREEN
        margin = abs(want) * TARGET_CLOSE_FRACTION
        return AMBER if got <= want + margin else RED

    if direction == "on_target":
        if got == want:
            return GREEN
        margin = abs(want) * TARGET_CLOSE_FRACTION
        return AMBER if abs(got - want) <= margin else RED

    # higher_is_better, and the default when nothing is stated.
    if got >= want:
        return GREEN
    margin = abs(want) * TARGET_CLOSE_FRACTION
    return AMBER if got >= want - margin else RED


def council_threshold_v1(target, actual, direction="higher_is_better", threshold=None):
    """Did the council hit its own target, and if it missed, did it cross its own warning line?

    Green if the council's reported figure met or beat the target it set itself. Amber if it
    missed the target but stayed on the safe side of the council's own intervention level —
    the point at which the council says it will step in and act. Red if it crossed that line.
    Grey if the council has not published a target, an intervention level, or the figure.

    This is the strictest form of "the council's own rule": both the pass mark and the alarm
    line are the council's, published beside the figure in its own performance report, so the
    colour here should be the colour on the council's own dashboard. Where a council publishes
    a target but no alarm line, target-met-v1 is used instead.

    `threshold.value` is the council's published intervention level.
    """
    want = _number(target)
    got = _number(actual)
    alarm = _number(threshold)
    if want is None or got is None or alarm is None:
        return GREY

    if direction == "lower_is_better":
        if got <= want:
            return GREEN
        return AMBER if got <= alarm else RED

    if direction == "on_target":
        if got == want:
            return GREEN
        return AMBER if abs(got - want) <= abs(alarm - want) else RED

    if got >= want:
        return GREEN
    return AMBER if got >= alarm else RED


# The four things a later council record can say about a dated promise.
PROMISE_DONE_ON_TIME = "done_on_time"
PROMISE_DONE_LATE = "done_late"
PROMISE_PARTLY_DONE = "partly_done"
PROMISE_NOT_DONE = "not_done"

PROMISE_OUTCOMES = {
    PROMISE_DONE_ON_TIME: GREEN,
    PROMISE_DONE_LATE: AMBER,
    PROMISE_PARTLY_DONE: AMBER,
    PROMISE_NOT_DONE: RED,
}


def promise_kept_v1(target, actual, direction=None, threshold=None):
    """Did the council do the thing it put in writing, by the date it gave?

    Green if a later council record confirms it was done by that date. Amber if a
    later record shows it was done late, or only partly. Red if a later record
    says it was not done. Grey if no later council record mentions it — which
    means the promise cannot be checked, not that it was broken.

    A promise here is narrow on purpose: a dated commitment the council made in
    one of its own published papers ("a final policy will come to Council in
    November 2026", "£3.2m of savings in 2025/26"). Manifestos, speeches and
    press quotes are not promises for this purpose, because the council as an
    organisation did not write them down. `target` carries the commitment in the
    council's own words with the date it gave; `actual` carries what the later
    record says.

    `actual.value` is one of: done_on_time, done_late, partly_done, not_done.
    """
    outcome = _word(actual)
    if outcome is None:
        return GREY
    return PROMISE_OUTCOMES.get(outcome, GREY)


# Savings are a plan to spend less. Delivering 95% of them is a plan that worked;
# below 80% the gap has to be filled from somewhere else, usually reserves.
SAVINGS_GREEN_PCT = 95.0
SAVINGS_AMBER_PCT = 80.0


def savings_delivered_v1(target, actual, direction=None, threshold=None):
    """Did the council actually make the savings it said it would?

    Green if at least 95% of the savings target was delivered, amber if at least
    80% was, red if less than 80% was, and grey if the council does not report
    what it delivered — which is common, and is itself worth knowing.

    Councils set a savings target when they set the budget, then report against it
    afterwards, or don't. Where a council only publishes the savings it *found*
    when writing the budget, and never says how much actually arrived, this
    measure stays grey and says so.

    `actual.value` is the savings delivered as a percentage of the savings target.
    """
    delivered = _number(actual)
    if delivered is None:
        return GREY
    if delivered >= SAVINGS_GREEN_PCT:
        return GREEN
    if delivered >= SAVINGS_AMBER_PCT:
        return AMBER
    return RED


# Reserves against the council's own floor. At or above the floor is fine; within
# a tenth below it is a warning; further below is the finance officer's own line
# being crossed.
RESERVES_AMBER_FRACTION = 0.10


def reserves_vs_policy_v1(target, actual, direction=None, threshold=None):
    """Does the council hold as much in reserve as its own policy says it should?

    Green if the money set aside for emergencies is at or above the minimum the
    council's own finance officer sets and publishes. Amber if it is below that
    minimum but by less than a tenth of it. Red if it is further below. Grey if
    the council does not publish a minimum, or has not published the balance.

    The floor is the council's, not ours. Every council's chief finance officer
    has to state a prudent minimum for the general reserve and say whether the
    balance is adequate, so this compares the council against the line it drew
    itself. Holding much more than the minimum is not scored: reserves that look
    large are usually ring-fenced for things like council housing, and calling
    that "hoarding" would be an opinion.

    `target.value` is the published minimum and `actual.value` the balance held,
    both in the same units.
    """
    minimum = _number(target)
    held = _number(actual)
    if minimum is None or held is None:
        return GREY
    if held >= minimum:
        return GREEN
    return AMBER if held >= minimum * (1 - RESERVES_AMBER_FRACTION) else RED


# --------------------------------------------------------------------------
# The register
# --------------------------------------------------------------------------

RULES = {
    "budget-variance-v1": budget_variance_v1,
    "capital-delivery-v1": capital_delivery_v1,
    "target-met-v1": target_met_v1,
    "council-threshold-v1": council_threshold_v1,
    "promise-kept-v1": promise_kept_v1,
    "savings-delivered-v1": savings_delivered_v1,
    "reserves-vs-policy-v1": reserves_vs_policy_v1,
}


def is_known(rule_id):
    return rule_id in RULES


def apply_rule(rule_id, target, actual, direction=None, threshold=None):
    """Run one rule. Returns (status, status_word).

    An unknown rule_id is a programming error, not a data problem: the caller
    checks `is_known` first and records a gap, so nothing reaches here unchecked.
    """
    rule = RULES[rule_id]
    status = rule(target, actual, direction, threshold)
    return status, STATUS_WORDS[status]


def summary_line(rule_id):
    """The rule in one sentence — the first paragraph of its docstring, minus the
    question that opens it. This is what the site prints beside a status."""
    doc = (RULES[rule_id].__doc__ or "").strip()
    paragraphs = [" ".join(p.split()) for p in doc.split("\n\n") if p.strip()]
    return paragraphs[1] if len(paragraphs) > 1 else (paragraphs[0] if paragraphs else "")


def question_line(rule_id):
    """The plain-English question a rule answers — the first line of its
    docstring."""
    doc = (RULES[rule_id].__doc__ or "").strip()
    return " ".join(doc.split("\n\n")[0].split())


def full_text(rule_id):
    """Every paragraph of a rule's docstring, tidied into a list of paragraphs."""
    doc = (RULES[rule_id].__doc__ or "").strip()
    return [" ".join(p.split()) for p in doc.split("\n\n") if p.strip()]


def thresholds(rule_id):
    """The named constants a rule uses, in the order they are declared, so the
    methodology page can print the numbers that decide a colour."""
    named = {
        "budget-variance-v1": [
            ("Within this much of budget is green", f"{BUDGET_VARIANCE_GREEN_PCT:g}%"),
            ("Within this much of budget is amber", f"{BUDGET_VARIANCE_AMBER_PCT:g}%"),
        ],
        "capital-delivery-v1": [
            ("Delivered at least this share is green", f"{CAPITAL_DELIVERY_GREEN_PCT:g}%"),
            ("Delivered at least this share is amber", f"{CAPITAL_DELIVERY_AMBER_PCT:g}%"),
        ],
        "council-threshold-v1": [
            ("Met or beat the council's own target", "green"),
            ("Missed the target, stayed the safe side of the council's own intervention level", "amber"),
            ("Crossed the council's own intervention level", "red"),
        ],
        "target-met-v1": [
            ("Missing by no more than this share of the target is amber",
             f"{TARGET_CLOSE_FRACTION * 100:g}%"),
        ],
        "promise-kept-v1": [
            ("Done by the promised date", "green"),
            ("Done late, or only partly done", "amber"),
            ("A later record says it was not done", "red"),
            ("No later record mentions it", "grey"),
        ],
        "savings-delivered-v1": [
            ("Delivered at least this share of the target is green", f"{SAVINGS_GREEN_PCT:g}%"),
            ("Delivered at least this share of the target is amber", f"{SAVINGS_AMBER_PCT:g}%"),
        ],
        "reserves-vs-policy-v1": [
            ("At or above the council's own minimum", "green"),
            ("Below the minimum by less than this share of it",
             f"{RESERVES_AMBER_FRACTION * 100:g}%"),
        ],
    }
    return named.get(rule_id, [])
