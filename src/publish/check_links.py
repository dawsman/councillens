#!/usr/bin/env python3
"""Check that every internal link and asset in the built site resolves to a file.

The site is published under a base path (``/councillens/``) so every internal
link has to be relative. This walks the built HTML, resolves each relative href
and src against the file it appears in, and reports anything that would 404.

External links (http/https/mailto) are listed but not fetched. In-page anchors
are checked against the ids present in the same file.

Usage::

    python src/publish/check_links.py            # checks pages/
    python src/publish/check_links.py --out _site
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

REF_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]*)"', re.I)
ID_RE = re.compile(r'\sid\s*=\s*"([^"]+)"', re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check internal links in the built site.")
    parser.add_argument("--out", default="pages", help="built site directory (default: pages)")
    args = parser.parse_args()

    root = Path(args.out).resolve()
    if not root.is_dir():
        print(f"No built site at {root}. Run the build first.")
        return 1

    html_files = sorted(root.rglob("*.html"))
    if not html_files:
        print(f"No HTML files under {root}.")
        return 1

    broken: list[str] = []
    external: set[str] = set()
    checked = 0

    for page in html_files:
        text = page.read_text(encoding="utf-8")
        ids = set(ID_RE.findall(text))
        rel_page = page.relative_to(root)
        for raw in REF_RE.findall(text):
            ref = raw.strip()
            if not ref:
                continue
            parsed = urlparse(ref)
            if parsed.scheme in ("http", "https", "mailto", "tel", "data"):
                external.add(ref)
                continue
            checked += 1
            if ref.startswith("#"):
                if ref[1:] not in ids:
                    broken.append(f"{rel_page}: no element with id \"{ref[1:]}\"")
                continue
            if ref.startswith("/"):
                # Absolute paths only belong on 404.html, which is served from
                # arbitrary URLs and so cannot use relative links.
                if page.name != "404.html":
                    broken.append(f"{rel_page}: absolute path \"{ref}\" will break under the base path")
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.exists():
                broken.append(f"{rel_page}: \"{ref}\" -> missing {target.relative_to(root) if target.is_relative_to(root) else target}")
            elif parsed.fragment:
                frag_ids = set(ID_RE.findall(target.read_text(encoding="utf-8")))
                if parsed.fragment not in frag_ids:
                    broken.append(f"{rel_page}: \"{ref}\" -> no id \"{parsed.fragment}\" in target")

    print(f"Checked {checked} internal reference(s) across {len(html_files)} page(s).")
    print(f"Found {len(external)} external link target(s) (not fetched).")
    if broken:
        print(f"\n{len(broken)} broken reference(s):")
        for b in broken:
            print(f"  {b}")
        return 1
    print("\nAll internal links and assets resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
