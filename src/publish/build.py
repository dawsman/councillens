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
import shutil
import sys
from datetime import date, datetime
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
    return model


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
