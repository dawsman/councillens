#!/usr/bin/env python3
"""Where CouncilLens keeps its configuration, and the one place that reads it.

Two kinds of file, both plain YAML, both reviewed by a person before anything is
fetched:

    config/councils/<council-slug>.yaml        who the council is: website, tier,
                                               remit note, which platforms it uses
    config/sources/<council-slug>/<topic-slug>.yaml
                                               one council + one topic: the list of
                                               public documents that make up the
                                               feedback -> decision -> outcome trail

A source file may also set `model:` to say which analyse stage assembles what it
gathers. It defaults to `topic`. Anything else (`people`, say) is still fetched,
extracted and validated by exactly the same pipeline; only the assembly differs.

The council file is deliberately separate from the topic files. A council's remit
note is a fact about the council, not about licensing or housing, so two topics can
never end up disagreeing about what the council does.

The slug in a path is not decoration: `slugify(council)` must equal the directory
name and `slugify(topic)` must equal the file stem. That is what lets `--only
norwich-city-council/licensing-policy` mean exactly one config file, and what keeps
the analysed output path predictable. A mismatch is an error, not a warning.

Nothing council-specific lives in this module — only the rules for finding config.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
SOURCES_DIR = CONFIG_DIR / "sources"
COUNCILS_DIR = CONFIG_DIR / "councils"
PLACEHOLDER = "REPLACE_ME"


def slugify(value):
    """Lowercase hyphen slug. Anything in brackets is dropped first, so
    'Licensing policy (alcohol, entertainment and late-night venues)' becomes
    'licensing-policy' — the short name a URL wants."""
    value = re.sub(r"\(.*?\)", " ", value or "")
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return value.strip("-")


def short_name(value):
    """The part of a configured name before any bracketed qualifier."""
    return re.sub(r"\(.*?\)", " ", value or "").strip(" -,")


class TopicConfig:
    """One council + one topic: everything one config file says.

    `model` says which analyse stage owns the documents this file gathers, and so
    which shape they are assembled into. It defaults to `topic`, the
    feedback -> decision -> outcome trail that most of the site is made of. A file
    that gathers a different KIND of public record — the council's own directory
    of who sits on it, say — sets `model:` to the name of that model instead, and
    the topic build leaves it alone. Ingest, transform and validation are
    identical either way: one pipeline, one contract, several ways of reading the
    result.
    """

    __slots__ = ("path", "council", "topic", "council_slug", "topic_slug", "sources", "model")

    DEFAULT_MODEL = "topic"

    def __init__(self, path, council, topic, sources, model=None):
        self.path = path
        self.council = council
        self.topic = topic
        self.council_slug = slugify(council)
        self.topic_slug = slugify(topic)
        self.sources = sources
        self.model = model or self.DEFAULT_MODEL

    @property
    def key(self):
        return f"{self.council_slug}/{self.topic_slug}"

    @property
    def rel_path(self):
        return self.path.relative_to(ROOT)

    def enabled_sources(self):
        return [
            s for s in self.sources
            if s.get("enabled") and PLACEHOLDER not in str(s.get("url", ""))
        ]

    def has_placeholders(self):
        return PLACEHOLDER in str(self.council) or PLACEHOLDER in str(self.topic)

    def __repr__(self):
        return f"<TopicConfig {self.key}>"


def parse_only(value):
    """Turn '--only norwich-city-council/licensing-policy' into a pair of slugs."""
    if value is None:
        return None
    parts = str(value).strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(
            f"--only takes <council-slug>/<topic-slug>, e.g. "
            f"norwich-city-council/licensing-policy (got {value!r})"
        )
    return parts[0], parts[1]


def load_topics(only=None):
    """Every configured council + topic, oldest path first for a stable order.

    `only` is a '<council-slug>/<topic-slug>' string; pass it to narrow the list to
    one topic. An unknown slug pair is an error — silently doing nothing would look
    exactly like a successful run that fetched no documents.
    """
    if not SOURCES_DIR.is_dir():
        return []

    topics = []
    for path in sorted(SOURCES_DIR.glob("*/*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entry = TopicConfig(
            path=path,
            council=data.get("council"),
            topic=data.get("topic"),
            sources=data.get("sources") or [],
            model=data.get("model"),
        )
        if entry.has_placeholders():
            topics.append(entry)
            continue
        expected = f"{entry.council_slug}/{entry.topic_slug}.yaml"
        actual = f"{path.parent.name}/{path.name}"
        if expected != actual:
            raise ValueError(
                f"Config file {path.relative_to(ROOT)} is in the wrong place: "
                f"council {entry.council!r} and topic {entry.topic!r} belong at "
                f"config/sources/{expected}."
            )
        topics.append(entry)

    wanted = parse_only(only)
    if wanted is None:
        return topics
    chosen = [t for t in topics if (t.council_slug, t.topic_slug) == wanted]
    if not chosen:
        known = ", ".join(t.key for t in topics) or "none"
        raise ValueError(f"No config for {wanted[0]}/{wanted[1]}. Configured topics: {known}.")
    return chosen


def load_council(council_slug):
    """The council block for one council, or None if nobody has written it yet."""
    path = COUNCILS_DIR / f"{council_slug}.yaml"
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def topics_index(topics):
    """The small council/topic index written at the top of each manifest, so a
    reader can see what a manifest covers without reading every record."""
    return [
        {
            "council": t.council,
            "topic": t.topic,
            "council_slug": t.council_slug,
            "topic_slug": t.topic_slug,
        }
        for t in topics if not t.has_placeholders()
    ]
