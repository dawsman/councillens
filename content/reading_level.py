#!/usr/bin/env python3
"""Measure reading level of CouncilLens copy.

Usage:
  reading_level.py html <file.html> [...]   # strip a built page down to its prose
  reading_level.py text <file.md|yaml> [...]
Falls back to a local Flesch implementation if textstat is missing.
"""
from __future__ import annotations
import re, sys, json, pathlib

try:
    import textstat
    HAVE_TS = True
except Exception:
    HAVE_TS = False

VOWELS = "aeiouy"

def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    n = len(re.findall(r"[aeiouy]{1,2}", w))
    return max(1, n)

def flesch(text: str) -> dict:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if s.strip()]
    words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", text)
    if not sentences or not words:
        return {}
    syl = sum(syllables(w) for w in words)
    W, S = len(words), len(sentences)
    ease = 206.835 - 1.015 * (W / S) - 84.6 * (syl / W)
    fk = 0.39 * (W / S) + 11.8 * (syl / W) - 15.59
    return {"words": W, "sentences": S, "words_per_sentence": round(W / S, 1),
            "syllables_per_word": round(syl / W, 2),
            "flesch_reading_ease": round(ease, 1),
            "flesch_kincaid_grade": round(fk, 1),
            "reading_age_years": round(fk + 5, 1)}

def score(text: str) -> dict:
    out = flesch(text)
    if HAVE_TS and out:
        out["textstat_flesch_reading_ease"] = round(textstat.flesch_reading_ease(text), 1)
        out["textstat_fk_grade"] = round(textstat.flesch_kincaid_grade(text), 1)
        out["textstat_reading_age"] = round(textstat.flesch_kincaid_grade(text) + 5, 1)
    return out

DROP_BLOCKS = re.compile(
    r"<(script|style|svg|nav|footer|header class=\"masthead\")\b.*?</\1>", re.S | re.I)
# The council's own words are quoted verbatim and must not be rewritten, so
# they are excluded from "our copy" scores. Same for document titles.
QUOTED = re.compile(r"<(blockquote|h3 class=\"source-title\"|p class=\"change-text\")\b.*?</(blockquote|h3|p)>", re.S | re.I)

def html_text(path: pathlib.Path, drop_quoted: bool = True) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<main\b.*?>(.*)</main>", raw, re.S | re.I)
    body = m.group(1) if m else raw
    body = DROP_BLOCKS.sub(" ", body)
    if drop_quoted:
        body = QUOTED.sub(" ", body)
    body = re.sub(r"(?<=[.!?])<", ". <", body)
    body = re.sub(r"</(p|li|h1|h2|h3|h4|dd|dt|figcaption)>", ". ", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = (body.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&ldquo;", '"').replace("&rdquo;", '"')
                .replace("&#39;", "'").replace("&quot;", '"').replace("&mdash;", "—"))
    body = re.sub(r"\.\s*(\.\s*)+", ". ", body)
    return re.sub(r"\s+", " ", body).strip()

def plain_text(path: pathlib.Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix in (".yaml", ".yml"):
        keep = []
        for line in raw.splitlines():
            m = re.match(r"\s*(short|long|example|body|text|title|question|answer):\s*(?:>-|\|)?\s*(.*)", line)
            if m and m.group(2):
                keep.append(m.group(2).strip().strip('"'))
            elif re.match(r"^\s{4,}\S", line) and not re.match(r"^\s*[a-z_]+:", line):
                keep.append(line.strip())
        raw = "\n".join(keep)
    else:
        raw = re.sub(r"^---.*?^---", "", raw, flags=re.S | re.M)
        raw = re.sub(r"```.*?```", " ", raw, flags=re.S)
        raw = re.sub(r"^\|.*$", "", raw, flags=re.M)          # tables
        raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)     # links
        raw = re.sub(r"[#*_>`]", "", raw)
    return re.sub(r"[ \t]+", " ", raw).strip()

if __name__ == "__main__":
    mode, files = sys.argv[1], sys.argv[2:]
    rows = {}
    for f in files:
        p = pathlib.Path(f)
        t = html_text(p) if mode == "html" else plain_text(p)
        rows[p.name] = score(t)
    print(json.dumps(rows, indent=1))
