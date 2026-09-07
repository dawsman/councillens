#!/usr/bin/env python3
"""Publish stage: turn topic-model JSON into the static CouncilLens site.

Reads one JSON file per council+topic from ``data/analysed/**/*.json`` (the shape
is documented in the team brief and in ``docs/architecture.md``) and writes plain
static HTML plus a single stylesheet into ``pages/``.

The stage is deliberately council-agnostic: nothing here knows about Norwich, or
about any particular topic. Councils and topics are whatever the analysed files
contain, so N councils x N topics all render from the same templates.

Usage::

    python src/publish/build.py              # build from data/analysed/**/*.json
    python src/publish/build.py --fixture    # build from the example topic model
    python src/publish/build.py --out _site  # write somewhere other than pages/

If there are no analysed files and ``--fixture`` was not given, the site-wide
pages (home, methodology, corrections, 404) are still written, so the published
site never disappears just because the pipeline has not run yet.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - guarded for a clearer message
    markdown_lib = None

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TEMPLATE_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
FIXTURE_PATH = HERE / "fixtures" / "example-topic.json"
ANALYSED_DIR = REPO_ROOT / "data" / "analysed"
METHODOLOGY_MD = REPO_ROOT / "methodology" / "README.md"

REPO_URL = "https://github.com/dawsman/councillens"
DEFAULT_CORRECTIONS_URL = f"{REPO_URL}/issues/new?template=correction.yml"
DEFAULT_BASE_PATH = "/councillens/"

STAGES = ("feedback", "decision", "outcome")

# Plain-English labels. The pipeline speaks in feedback/decision/outcome; a
# resident reading the page should see the three questions instead.
STAGE_LABEL = {
    "feedback": "Asked",
    "decision": "Decided",
    "outcome": "Done",
}
# On a card the outcome stage is labelled "Outcome", not "Done": an outcome
# card can perfectly well be an outcome that has not happened, and a chip
# reading "Done" next to one reading "Still waiting" contradicts itself.
STAGE_CHIP = {
    "feedback": "Asked",
    "decision": "Decided",
    "outcome": "Outcome",
}
STAGE_HEADING = {
    "feedback": "What people asked for",
    "decision": "What the council decided",
    "outcome": "What actually happened",
}
STAGE_QUESTION = {
    "feedback": "What did people ask for?",
    "decision": "What did the council decide?",
    "outcome": "What actually got done?",
}

TIER = {
    "confirmed": {
        "emoji": "\U0001F7E2",
        "label": "Confirmed link",
        "blurb": "The council's own record says this feedback shaped the decision.",
    },
    "possible": {
        "emoji": "\U0001F7E1",
        "label": "Possible link",
        "blurb": "The feedback came first, but nothing on record proves it caused the decision.",
    },
    "none": {
        "emoji": "⚪",
        "label": "No link found",
        "blurb": "We found nothing connecting this feedback to the decision.",
    },
}

STATUS = {
    "done": {"label": "Done", "note": None},
    "in_progress": {"label": "Under way", "note": "This has started but is not finished."},
    "still_waiting": {
        "label": "Still waiting",
        "note": "This has not happened yet, or has not been published.",
    },
    "unknown": {
        "label": "Not known",
        "note": "The public record does not tell us where this stands.",
    },
}

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def human_date(value: Any, precision: str | None = None) -> str:
    """Render a full, partial, or missing date the way a person would say it."""
    if not value:
        return "Date not known"
    text = str(value).strip()
    parts = text.split("-")
    try:
        if precision == "day" or len(parts) == 3:
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
        if precision == "month" or len(parts) == 2:
            return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"
        if precision == "year" or len(parts) == 1:
            return f"Some time in {parts[0]}"
    except (ValueError, IndexError):
        return text
    return text


def sort_key(event: dict) -> tuple:
    """Order events by date, pushing unknown dates to the end of their stage."""
    raw = event.get("date")
    if not raw:
        return (1, "9999-99-99", event.get("title", ""))
    padded = str(raw)
    # 2024 -> 2024-99-99 so a year-only event sorts after dated ones that year.
    bits = padded.split("-")
    while len(bits) < 3:
        bits.append("99")
    return (0, "-".join(b.zfill(2) if i else b.zfill(4) for i, b in enumerate(bits)),
            event.get("title", ""))


def is_waiting(event: dict) -> bool:
    return event.get("status") in ("still_waiting", "unknown")


def provenance(ai: dict | None) -> dict | None:
    """Flatten an AI provenance block into what the page needs to show."""
    if not ai:
        return None
    status = ai.get("review_status")
    reviewed = status == "reviewed"
    ai_reviewed = status == "ai_reviewed"
    return {
        "model": ai.get("model") or "unknown model",
        "generated_at": (ai.get("generated_at") or "")[:10],
        "prompt_version": ai.get("prompt_version"),
        "confidence": ai.get("confidence"),
        "reviewed": reviewed,
        "ai_reviewed": ai_reviewed,
        "review_text": (
            f"checked by {ai['reviewed_by']}" if reviewed and ai.get("reviewed_by")
            else "checked by a person" if reviewed
            else "checked against the source documents by a second, independent AI review; not yet by a person" if ai_reviewed
            else "not yet reviewed by a person"
        ),
    }


# --------------------------------------------------------------------------
# Loading and shaping the topic models
# --------------------------------------------------------------------------

def load_models(use_fixture: bool) -> tuple[list[dict], list[str]]:
    """Return (topic models, notes to print)."""
    notes: list[str] = []
    if use_fixture:
        if not FIXTURE_PATH.exists():
            sys.exit(f"Fixture not found: {FIXTURE_PATH}")
        notes.append(f"Building from the example topic model ({FIXTURE_PATH.name}).")
        return [json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))], notes

    files = sorted(ANALYSED_DIR.glob("**/*.json")) if ANALYSED_DIR.exists() else []
    if not files:
        notes.append(
            "No analysed topic models found in data/analysed/. Building the site-wide "
            "pages only (home, methodology, corrections, 404).\n"
            "  Run the pipeline first, or use --fixture to preview with example data."
        )
        return [], notes

    models = []
    for path in files:
        try:
            models.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            notes.append(f"Skipped {path.relative_to(REPO_ROOT)}: not valid JSON ({exc}).")
    notes.append(f"Loaded {len(models)} topic model(s) from data/analysed/.")
    return models, notes


# Fields the contract allows to be absent or null. The templates read them as
# plain attributes, so they are filled in here once rather than guarded in a
# dozen places. A missing field must never take the whole build down.
EVENT_OPTIONAL = {
    "stage": None, "date": None, "date_precision": "unknown", "title": "Untitled record",
    "summary": "", "detail": None, "source_ids": [], "source_url": None,
    "status": None, "ai": None,
}
SOURCE_OPTIONAL = {
    "title": "Untitled document", "type": None, "stage": None, "body": None,
    "platform": None, "source_url": None, "summary": None, "ai": None,
}
LINK_OPTIONAL = {
    "from_event": None, "to_event": None, "tier": "none", "evidence": None,
    "evidence_url": None, "explanation": None, "ai": None,
}
COUNCIL_OPTIONAL = {
    "name": "Council name not recorded", "slug": "council", "website": None,
    "tier": None, "remit_note": None, "platforms": {},
}
TOPIC_OPTIONAL = {
    "name": "Topic name not recorded", "slug": "topic",
    "plain_english": "We have not written a plain-English summary of this topic yet.",
    "questions": {},
}


def fill(item: dict, defaults: dict) -> dict:
    for key, value in defaults.items():
        if item.get(key) is None:
            item[key] = value
    return item


def prepare(model: dict) -> dict:
    """Add the derived, presentation-ready bits the templates rely on."""
    events = [fill(dict(e), EVENT_OPTIONAL) for e in (model.get("events") or [])]
    for i, e in enumerate(events):
        e.setdefault("id", f"event-{i + 1}")
        if not e["id"]:
            e["id"] = f"event-{i + 1}"
    model["events"] = events
    by_id = {e["id"]: e for e in events if e.get("id")}

    for e in events:
        e["_date_human"] = human_date(e.get("date"), e.get("date_precision"))
        e["_waiting"] = is_waiting(e)
        e["_status"] = STATUS.get(e.get("status") or "", None)
        e["_ai"] = provenance(e.get("ai"))

    # Group by stage, in date order.
    stages = {s: sorted([e for e in events if e.get("stage") == s], key=sort_key)
              for s in STAGES}
    # Anything with an unrecognised stage still needs to appear somewhere.
    stages["other"] = sorted(
        [e for e in events if e.get("stage") not in STAGES], key=sort_key
    )

    # Linkages, resolved to their events and hung off the decision they explain.
    linkages = []
    for link in model.get("linkages") or []:
        resolved = fill(dict(link), LINK_OPTIONAL)
        tier = TIER.get(resolved["tier"], TIER["none"])
        resolved["_tier"] = tier
        resolved["_tier_key"] = resolved["tier"] if resolved["tier"] in TIER else "none"
        resolved["_from"] = by_id.get(resolved["from_event"])
        resolved["_to"] = by_id.get(resolved["to_event"])
        resolved["_ai"] = provenance(resolved["ai"])
        linkages.append(resolved)

    links_by_decision: dict[str, list[dict]] = {}
    for link in linkages:
        links_by_decision.setdefault(link["to_event"] or "", []).append(link)
    # Show the strongest evidence first.
    order = {"confirmed": 0, "possible": 1, "none": 2}
    for group in links_by_decision.values():
        group.sort(key=lambda l: order.get(l["_tier_key"], 3))

    sources = [fill(dict(s), SOURCE_OPTIONAL) for s in (model.get("sources") or [])]
    for i, s in enumerate(sources):
        if not s.get("id"):
            s["id"] = f"source-{i + 1}"
        # The number the document carries in the numbered list further down the
        # page. The documents strip reuses it, so a tile and a list entry are
        # visibly the same document.
        s["_n"] = i + 1
        s["_ai"] = provenance(s["ai"])
    model["sources"] = sources

    timeline = sorted([e for e in events if not e["_waiting"]], key=sort_key)
    waiting = sorted([e for e in events if e["_waiting"]], key=sort_key)

    council = fill(dict(model.get("council") or {}), COUNCIL_OPTIONAL)
    topic = fill(dict(model.get("topic") or {}), TOPIC_OPTIONAL)
    model["council"] = council
    model["topic"] = topic
    model["_council_slug"] = council["slug"]
    model["_topic_slug"] = topic["slug"]
    model["_events"] = events
    model["_stages"] = stages
    model["_linkages"] = linkages
    model["_links_by_decision"] = links_by_decision
    model["_sources"] = sources
    model["_timeline"] = timeline
    model["_waiting"] = waiting
    model["_gaps"] = model.get("gaps") or []
    model["_corrections_url"] = model.get("corrections_url") or DEFAULT_CORRECTIONS_URL

    # One-line status per topic, for the council page.
    done = len([e for e in stages["outcome"] if e.get("status") == "done"])
    still = len([e for e in stages["outcome"] if is_waiting(e)])
    if still and done:
        status_line = f"Partly done — {done} finished, {still} still waiting."
    elif still:
        status_line = f"{still} thing{'s' if still > 1 else ''} still waiting."
    elif done:
        status_line = "The council did what it decided, as far as the record shows."
    elif stages["decision"]:
        status_line = "Decided, but we have found nothing yet on what happened next."
    else:
        status_line = "We are still gathering the record for this topic."
    model["_status_line"] = status_line
    model["_counts"] = {s: len(stages[s]) for s in STAGES}

    # The at-a-glance layer, all derived from what is already above.
    today = build_date(model)
    model["_today"] = today
    model["_figures"] = prepare_figures(model)
    model["_progress"] = prepare_progress(model, today)

    # The one-line status is written above from raw counts, which cannot tell a
    # result of this process from the state it started in. Now that the tracker
    # has worked that out, the sentence has to agree with it.
    outcome_step = model["_progress"]["steps"][2]
    if outcome_step["state"] == "superseded":
        still = len([e for e in stages["outcome"] if is_waiting(e)])
        model["_status_line"] = (
            f"Nothing new yet — what was already in place stays in force, "
            f"with {still} thing{'s' if still != 1 else ''} still waiting."
        )
    model["_ribbon"] = prepare_ribbon(model, today)
    model["_changes"] = prepare_changes(model, today)
    model["_linkage_summary"] = prepare_linkage_summary(model)
    model["_documents"] = prepare_document_strip(model)
    return model



# ==========================================================================
# The at-a-glance layer
#
# Everything below turns the topic model into small, honest pictures: a
# progress tracker, a strip of key numbers, a time ribbon, a "what would
# change" comparison, a linkage tally and a documents strip.
#
# Three rules hold throughout:
#   1. Nothing is invented. Every number, date and phrase is read out of the
#      model; if the model does not have it, the visual says so or disappears.
#   2. Nothing is drawn as finished that is not finished. Anything dated after
#      the build date, or flagged still_waiting, is dashed and hatched.
#   3. "Today" is the model's generated_at date, never the clock, so two
#      builds of the same data produce byte-identical pages.
# ==========================================================================

FIGURE_OPTIONAL = {
    "label": "Unlabelled figure", "kind": "count", "value": None, "unit": None,
    "display": None, "as_of": None, "period": None, "source_ids": [],
    "source_url": None, "note": None, "ai": None,
}

# Wording for each step of the tracker. The key is (stage, state).
STEP_STATE = {
    "done": "On record",
    "active": "Under way",
    "upcoming": "Coming up",
    "undated": "Date not known",
    "none": "Nothing found yet",
    "finished": "Done",
    "partly": "Partly done",
    "waiting": "Still waiting",
    "superseded": "Nothing new yet",
}


def as_date(value: Any) -> date | None:
    """Turn a full or partial date string into a real date for comparisons.

    A month-only date counts from the first of that month, a year-only date
    from 1 January. That is only ever used for ordering and for working out
    what is past or future; the text on the page still says "December 2021".
    """
    if not value:
        return None
    bits = str(value).strip().split("-")
    try:
        year = int(bits[0])
        month = int(bits[1]) if len(bits) > 1 else 1
        day = int(bits[2]) if len(bits) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def build_date(model: dict) -> date:
    """The "today" the page is drawn against: the model's own generated_at."""
    stamp = str(model.get("generated_at") or "")[:10]
    return as_date(stamp) or date.today()


def in_days(today: date, when: date | None) -> int | None:
    if not when:
        return None
    return (when - today).days


def countdown(days: int | None) -> str | None:
    """Plain English for a number of days away. Residents, not developers."""
    if days is None:
        return None
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    if days < 0:
        return f"{abs(days)} days ago"
    if days < 21:
        return f"in {days} days"
    weeks = round(days / 7)
    if days < 60:
        return f"in about {weeks} weeks"
    months = round(days / 30.4)
    if days < 350:
        return f"in about {months} months"
    years = days / 365.25
    return f"in about {years:.0f} years" if years >= 1.5 else "in about a year"


def gap_words(a: date, b: date) -> str | None:
    """How long between two dates, said the way a person would say it."""
    days = (b - a).days
    if days < 25:
        return None if days < 8 else f"{days} days later"
    months = round(days / 30.4)
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} later"
    years, rem = divmod(months, 12)
    if rem == 0:
        return f"{years} year{'s' if years != 1 else ''} later"
    return f"{years} year{'s' if years != 1 else ''}, {rem} month{'s' if rem != 1 else ''} later"


def money(value: Any, display: str | None) -> str | None:
    """Format a money figure as a person reads it. display wins if given."""
    if display:
        return display
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if abs(n) >= 1_000_000:
        return f"\u00a3{n / 1_000_000:.1f}m".replace(".0m", "m")
    if abs(n) >= 1_000:
        return f"\u00a3{n / 1_000:,.0f}k"
    return f"\u00a3{n:,.0f}"


def prepare_figures(model: dict) -> list[dict]:
    """Key numbers, ready to render. Absent or malformed figures cost nothing."""
    out = []
    for i, raw in enumerate(model.get("figures") or []):
        if not isinstance(raw, dict):
            continue
        f = fill(dict(raw), FIGURE_OPTIONAL)
        f.setdefault("id", f"fig-{i + 1}")
        if not f.get("id"):
            f["id"] = f"fig-{i + 1}"
        kind = f.get("kind") or "count"
        value = f.get("value")
        if kind == "money":
            shown = money(value, f.get("display"))
        elif f.get("display"):
            shown = str(f["display"])
        elif isinstance(value, (int, float)):
            shown = f"{value:,g}" + ("%" if kind == "share" else "")
        elif value is not None:
            shown = str(value)
        else:
            shown = None
        if shown is None:
            # A figure with no readable value is not a figure. Drop it rather
            # than print an empty tile.
            continue
        f["_display"] = shown
        f["_kind"] = kind if kind in ("count", "money", "duration", "share", "date") else "count"
        # Only a money or count figure carries a unit worth repeating; a share
        # already has its % in the number.
        f["_unit"] = f.get("unit") if kind in ("count", "duration") else None
        if f["_unit"] and str(f["_unit"]).upper() == "GBP":
            f["_unit"] = None
        when = f.get("period") or f.get("as_of")
        f["_when"] = (
            f"{f['period']}" if f.get("period")
            else (f"as at {human_date(f['as_of'])}" if f.get("as_of") else None)
        )
        f["_ai"] = provenance(f.get("ai"))
        out.append(f)
    return out


def step_for(stage: str, events: list[dict], today: date,
             first_decision: date | None = None) -> dict:
    """One step of the asked -> decided -> done tracker, read from the events."""
    dated = [(as_date(e.get("date")), e) for e in events if as_date(e.get("date"))]
    dated.sort(key=lambda pair: pair[0])
    past = [pair for pair in dated if pair[0] <= today]
    future = [pair for pair in dated if pair[0] > today]
    waiting = [e for e in events if is_waiting(e)]
    finished = [e for e in events if e.get("status") == "done"]

    step: dict[str, Any] = {
        "stage": stage,
        "label": STAGE_LABEL[stage],
        "question": STAGE_QUESTION[stage],
        "count": len(events),
        "headline": None,
        "when": None,
        "anchor": None,
        "extra": None,
        "next": None,
    }

    if stage == "outcome":
        # A "done" outcome that predates every decision on the record is not a
        # result of this process at all: it is the state of play the process is
        # trying to change. Calling that "partly done" beside a decision still
        # waiting to be made would tell the reader something happened when
        # nothing has. So it gets its own state, and says what still applies.
        finished_dates = [as_date(e.get("date")) for e in finished]
        superseding = bool(
            finished
            and waiting
            and first_decision
            and all(d and d < first_decision for d in finished_dates)
        )
        if superseding:
            state = "superseded"
        elif finished and waiting:
            state = "partly"
        elif finished:
            state = "finished"
        elif waiting:
            state = "waiting"
        elif past:
            state = "done"
        elif events:
            state = "undated"
        else:
            state = "none"
        anchor_event = (finished or [e for _, e in reversed(past)] or events or [None])[0]
        waiting_words = f"{len(waiting)} still waiting"
        if superseding:
            step["extra"] = (
                f"Current policy from {anchor_event['_date_human']} still applies"
                f" \u00b7 {waiting_words}"
            )
        elif finished and waiting:
            step["extra"] = f"{len(finished)} done \u00b7 {waiting_words}"
        elif waiting and not finished:
            step["extra"] = (
                f"{len(waiting)} thing{'s' if len(waiting) != 1 else ''} we are still waiting on"
            )
    else:
        if past and future:
            state = "active"
        elif past:
            state = "done"
        elif future:
            state = "upcoming"
        elif events:
            state = "undated"
        else:
            state = "none"
        anchor_event = past[-1][1] if past else (future[0][1] if future else (events[0] if events else None))

    if anchor_event:
        step["headline"] = anchor_event.get("title")
        step["when"] = anchor_event.get("_date_human")
        step["anchor"] = anchor_event.get("id")

    if future:
        when, event = future[0]
        step["next"] = {
            "title": event.get("title"),
            "when": event.get("_date_human"),
            "anchor": event.get("id"),
            "countdown": countdown(in_days(today, when)),
            "date": when,
        }

    step["state"] = state
    step["state_word"] = STEP_STATE[state]
    # Reached means: there is something real on the record at this stage.
    step["reached"] = state in ("done", "active", "finished", "partly", "undated")
    step["open"] = state in ("active", "waiting", "partly", "upcoming", "superseded")
    return step


def prepare_progress(model: dict, today: date) -> dict:
    decision_dates = [d for d in (as_date(e.get("date")) for e in model["_stages"]["decision"]) if d]
    first_decision = min(decision_dates) if decision_dates else None
    steps = [step_for(s, model["_stages"][s], today, first_decision) for s in STAGES]
    upcoming = [s["next"] for s in steps if s["next"]]
    upcoming.sort(key=lambda n: n["date"])
    nxt = upcoming[0] if upcoming else None
    for i, step in enumerate(steps):
        step["highlight"] = bool(nxt and step["next"] and step["next"]["date"] == nxt["date"])
        # The connector to the step on its right is only drawn solid when there
        # is something real at that next step. A dashed rail says "we have not
        # got there yet" without any wording having to.
        step["connector"] = (
            "solid" if i + 1 < len(steps) and steps[i + 1]["reached"] else "pending"
        )
    return {"steps": steps, "next": nxt, "today_human": human_date(today.isoformat(), "day")}


def prepare_ribbon(model: dict, today: date) -> dict | None:
    """Geometry for the horizontal time ribbon drawn at desktop widths.

    Milestones sit at even spacing, not on a proportional axis: with a gap of
    years between two events and three more a fortnight apart, a true axis
    puts four labels on top of each other and tells the reader nothing. The
    real elapsed time is written out between the nodes instead, which is both
    legible and impossible to misread.
    """
    dated = [(as_date(e.get("date")), e) for e in model["_events"] if as_date(e.get("date"))]
    dated.sort(key=lambda pair: pair[0])
    if len(dated) < 2:
        return None

    width, pad = 1000.0, 92.0
    rail_y = 96.0
    span = width - pad * 2
    n = len(dated)
    nodes = []
    for i, (when, event) in enumerate(dated):
        x = pad + (span * i / (n - 1))
        future = when > today
        nodes.append({
            "x": round(x, 1),
            "y": rail_y,
            "stage": event.get("stage") or "other",
            "future": future,
            "title": event.get("title") or "",
            "when": event.get("_date_human"),
            "short": short_date(event.get("date"), event.get("date_precision")),
            "anchor": event.get("id"),
            "lines": wrap_label(event.get("title") or "", 24, 2),
            "up": i % 2 == 0,
        })

    gaps = []
    for i in range(n - 1):
        words = gap_words(dated[i][0], dated[i + 1][0])
        if words:
            gaps.append({
                "x": round((nodes[i]["x"] + nodes[i + 1]["x"]) / 2, 1),
                "text": words,
                "future": dated[i + 1][0] > today,
            })

    # Where does "today" fall along the rail? Interpolate inside the segment
    # it lands in, so the marker sits honestly between the right two nodes.
    today_x = None
    if dated[0][0] <= today <= dated[-1][0]:
        for i in range(n - 1):
            a, b = dated[i][0], dated[i + 1][0]
            if a <= today <= b:
                frac = 0 if b == a else (today - a).days / (b - a).days
                today_x = round(nodes[i]["x"] + frac * (nodes[i + 1]["x"] - nodes[i]["x"]), 1)
                break
    elif today > dated[-1][0]:
        today_x = round(nodes[-1]["x"], 1)

    # Keep the "Today" flag from sitting on top of a node label.
    for node in nodes:
        if today_x is not None and abs(node["x"] - today_x) < 34:
            today_x = round(node["x"] + (38 if node["x"] < width / 2 else -38), 1)
            break

    undated = [e for e in model["_events"] if not as_date(e.get("date")) and e["_waiting"]]
    return {
        "width": width,
        "height": 176,
        "rail_y": rail_y,
        "start_x": pad - 44,
        "end_x": width - pad + 44,
        "nodes": nodes,
        "gaps": gaps,
        "today_x": today_x,
        "today_human": human_date(today.isoformat(), "day"),
        "today_short": short_date(today.isoformat(), "day"),
        "open_x": round(nodes[-1]["x"], 1),
        "undated": undated,
    }


def short_date(value: Any, precision: str | None = None) -> str:
    """A date short enough to sit under a marker: '5 Mar 26', 'Dec 21'."""
    if not value:
        return "no date"
    bits = str(value).split("-")
    try:
        year = bits[0][2:]
        if len(bits) >= 3 and precision != "month" and precision != "year":
            return f"{int(bits[2])} {MONTHS[int(bits[1]) - 1][:3]} {year}"
        if len(bits) >= 2:
            return f"{MONTHS[int(bits[1]) - 1][:3]} {year}"
        return bits[0]
    except (ValueError, IndexError):
        return str(value)


def wrap_label(text: str, width: int, max_lines: int) -> list[str]:
    """Greedy wrap for SVG text, which will not wrap itself."""
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
            if len(lines) == max_lines:
                break
    if line and len(lines) < max_lines:
        lines.append(line)
    if len(lines) == max_lines and len(" ".join(lines)) < len(text.strip()):
        lines[-1] = lines[-1].rstrip(" ,;:.") + "\u2026"
    return lines


CHANGE_QUOTED = re.compile(
    r"from\s+[\u2018\u201c'\"](?P<now>[^\u2019\u201d'\"]{2,90})[\u2019\u201d'\"]"
    r"\s+to\s+[\u2018\u201c'\"](?P<proposed>[^\u2019\u201d'\"]{2,90})[\u2019\u201d'\"]",
    re.I,
)
CHANGE_LABELLED = re.compile(r"^(?P<label>[^:]{3,58}):\s+(?P<value>.{2,})$")


def parse_change(bullet: str) -> dict:
    """Read a committee-paper bullet as a before/after pair where it is one.

    Council papers write changes two ways: "from 'x' to 'y'", and
    "Thing: what happened to it". Both become two columns. Anything else stays
    a single plain sentence rather than being forced into a shape it is not.
    """
    text = (bullet or "").strip()
    quoted = CHANGE_QUOTED.search(text)
    if quoted:
        return {
            "kind": "pair",
            "now": quoted.group("now").strip(),
            "proposed": quoted.group("proposed").strip(),
            "context": text,
        }
    labelled = CHANGE_LABELLED.match(text)
    if labelled and "http" not in text:
        return {
            "kind": "labelled",
            "now": labelled.group("label").strip(),
            "proposed": labelled.group("value").strip(),
            "context": None,
        }
    return {"kind": "plain", "now": None, "proposed": text, "context": None}


def prepare_changes(model: dict, today: date) -> dict | None:
    """The "what would change" comparison, built entirely from event detail."""
    proposals = []
    for event in model["_stages"]["decision"]:
        when = as_date(event.get("date"))
        # Only meetings that have actually happened can have changed anything.
        # A meeting still to come contributes nothing to this comparison.
        if when and when > today:
            continue
        for bullet in (event.get("detail") or []):
            item = parse_change(bullet)
            item["anchor"] = event.get("id")
            item["title"] = event.get("title")
            item["when"] = event.get("_date_human")
            item["source_url"] = event.get("source_url")
            proposals.append(item)
    if not proposals:
        return None

    in_force = None
    for event in model["_stages"]["outcome"]:
        if event.get("status") == "done":
            in_force = event
            break

    # "Adopted" means the decisions have actually landed in something in force:
    # every decision meeting has happened, and the policy in force is dated at
    # or after the last of them. An outstanding review elsewhere does not make
    # an adopted policy un-adopted, and a policy that predates the decisions is
    # not the thing those decisions produced.
    decision_dates = [d for d in (as_date(e.get("date")) for e in model["_stages"]["decision"]) if d]
    in_force_date = as_date(in_force.get("date")) if in_force else None
    adopted = bool(
        in_force_date
        and decision_dates
        and max(decision_dates) <= today
        and in_force_date >= max(decision_dates)
    )
    return {
        "items": proposals,
        "paired": [p for p in proposals if p["kind"] != "plain"],
        "plain": [p for p in proposals if p["kind"] == "plain"],
        "in_force": in_force,
        "adopted": adopted,
    }


def prepare_linkage_summary(model: dict) -> dict | None:
    order = ("confirmed", "possible", "none")
    counts = {tier: 0 for tier in order}
    for link in model["_linkages"]:
        counts[link["_tier_key"]] = counts.get(link["_tier_key"], 0) + 1
    total = sum(counts.values())
    if not total:
        return None
    rows = []
    for tier in order:
        count = counts[tier]
        rows.append({
            "tier": tier,
            "count": count,
            "share": round(100 * count / total, 1),
            "emoji": TIER[tier]["emoji"],
            "label": TIER[tier]["label"],
            "blurb": TIER[tier]["blurb"],
        })
    strongest = "confirmed" if counts["confirmed"] else ("possible" if counts["possible"] else "none")
    return {"rows": rows, "total": total, "counts": counts, "strongest": strongest}


def prepare_document_strip(model: dict) -> dict | None:
    """Every document we used, grouped by the stage it speaks to."""
    if not model["_sources"]:
        return None
    groups = []
    for stage in STAGES:
        docs = [s for s in model["_sources"] if s.get("stage") == stage]
        groups.append({
            "stage": stage,
            "label": STAGE_LABEL[stage],
            "heading": STAGE_HEADING[stage],
            "docs": docs,
            "count": len(docs),
        })
    loose = [s for s in model["_sources"] if s.get("stage") not in STAGES]
    if loose:
        groups.append({
            "stage": "other", "label": "Background", "heading": "Background documents",
            "docs": loose, "count": len(loose),
        })
    return {"groups": [g for g in groups if g["count"]], "total": len(model["_sources"])}


def group_councils(models: Iterable[dict]) -> list[dict]:
    """Collapse topic models into one entry per council, topics nested."""
    councils: dict[str, dict] = {}
    for m in models:
        slug = m["_council_slug"]
        entry = councils.setdefault(slug, {"council": m.get("council") or {}, "topics": []})
        entry["topics"].append(m)
    out = []
    for slug, entry in councils.items():
        entry["slug"] = slug
        entry["topics"].sort(key=lambda m: (m.get("topic") or {}).get("name", ""))
        entry["fixture"] = any(m.get("_fixture") for m in entry["topics"])
        out.append(entry)
    out.sort(key=lambda c: c["council"].get("name", c["slug"]))
    return out


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["human_date"] = human_date
    env.globals.update(
        STAGE_LABEL=STAGE_LABEL,
        STAGE_CHIP=STAGE_CHIP,
        STAGE_HEADING=STAGE_HEADING,
        STAGE_QUESTION=STAGE_QUESTION,
        STAGES=STAGES,
        TIER=TIER,
        REPO_URL=REPO_URL,
    )
    return env


def write(out_root: Path, rel_path: str, html: str, written: list[str]) -> None:
    target = out_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    written.append(rel_path)


def methodology_html() -> str:
    if not METHODOLOGY_MD.exists():
        return "<p>The methodology document is missing from the repository.</p>"
    if markdown_lib is None:
        sys.exit("The 'markdown' package is required. Run: pip install -r requirements.txt")
    # baselevel=2 demotes the document's own "# Methodology" to an <h2>, so the
    # rendered page keeps exactly one <h1> (the page title).
    return markdown_lib.markdown(
        METHODOLOGY_MD.read_text(encoding="utf-8"),
        extensions=["extra", "toc"],
        extension_configs={"toc": {"baselevel": 2}},
    )


def build(out_root: Path, use_fixture: bool, base_path: str) -> int:
    models_raw, notes = load_models(use_fixture)
    for note in notes:
        print(f"  {note}")

    models = [prepare(m) for m in models_raw]
    councils = group_councils(models)
    env = make_env()
    written: list[str] = []

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    now = datetime.now()
    built_at = f"{now.day} {MONTHS[now.month - 1]} {now.year}"
    common = dict(
        councils=councils,
        corrections_url=(models[0]["_corrections_url"] if models else DEFAULT_CORRECTIONS_URL),
        built_at=built_at,
        any_fixture=any(m.get("_fixture") for m in models),
    )

    write(out_root, "index.html",
          env.get_template("home.html").render(root="", page_id="home", **common), written)
    write(out_root, "methodology/index.html",
          env.get_template("methodology.html").render(
              root="../", page_id="methodology", body=methodology_html(), **common), written)
    write(out_root, "corrections/index.html",
          env.get_template("corrections.html").render(
              root="../", page_id="corrections", **common), written)
    # 404 is served for any missing path, so relative links would resolve against
    # the URL the visitor typed. This one page uses the absolute base path.
    write(out_root, "404.html",
          env.get_template("404.html").render(root=base_path, page_id="404", **common), written)

    for council in councils:
        base = f"councils/{council['slug']}"
        write(out_root, f"{base}/index.html",
              env.get_template("council.html").render(
                  root="../../", page_id="council", council=council, **common), written)
        for model in council["topics"]:
            tdir = f"{base}/{model['_topic_slug']}"
            write(out_root, f"{tdir}/index.html",
                  env.get_template("topic.html").render(
                      root="../../../", page_id="topic", m=model,
                      council=council, **common), written)
            write(out_root, f"{tdir}/timeline/index.html",
                  env.get_template("timeline.html").render(
                      root="../../../../", page_id="timeline", m=model,
                      council=council, **common), written)

    assets = out_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for asset in sorted(STATIC_DIR.glob("*")):
        if asset.is_file():
            shutil.copy2(asset, assets / asset.name)
            written.append(f"assets/{asset.name}")

    # GitHub Pages would otherwise run the output through Jekyll.
    (out_root / ".nojekyll").write_text("", encoding="utf-8")

    print(f"\n  Built {len(written)} file(s) into {out_root.relative_to(REPO_ROOT) if out_root.is_relative_to(REPO_ROOT) else out_root}/")
    for rel in written:
        print(f"    {rel}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the CouncilLens static site.")
    parser.add_argument("--fixture", action="store_true",
                        help="build from the example topic model instead of data/analysed/")
    parser.add_argument("--out", default=str(REPO_ROOT / "pages"),
                        help="output directory (default: pages/)")
    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH,
                        help="site base path, used by 404.html only (default: /councillens/)")
    args = parser.parse_args()
    print("CouncilLens — publish stage")
    return build(Path(args.out).resolve(), args.fixture, args.base_path)


if __name__ == "__main__":
    raise SystemExit(main())
