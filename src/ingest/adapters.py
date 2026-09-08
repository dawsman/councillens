#!/usr/bin/env python3
"""Adapters: one per publishing PLATFORM, never one per council.

A single CMIS adapter serves every council on CMIS; a single LocalGov Drupal
adapter serves every council on that platform. All platform-specific quirks are
absorbed here, so everything downstream sees only canonical records.

Adding a council or a topic is a config change (config/sources/). You only add
code here when a council uses a PLATFORM no adapter supports yet.

Config keys every adapter understands (all optional, all in the topic config file —
never hard-coded here, because WHICH documents matter is a topic question, not a
platform question):

    match:        list of case-insensitive substrings. A linked document is kept
                  only if its link text or URL contains one of them. Omit to keep
                  every linked document the adapter finds.
    exclude:      list of case-insensitive substrings that veto a document even
                  when `match` accepted it.
    documents:    explicit list of {title, url} to fetch in addition to (or
                  instead of) anything discovered on the page.
    include_page: emit a record for the page itself (default true). Keep it on
                  for pages that are themselves evidence — an agenda listing, a
                  consultation landing page, a meeting with no papers yet.
    follow_links: discover linked documents on the page (default true).
    max_bytes:    skip any single document larger than this, and say so.
    follow_pages: discover linked PAGES rather than documents. Some of what a
                  council publishes is a list that points at other pages: a
                  councillor directory pointing at one page per councillor, a
                  committee index pointing at one page per committee. `match`
                  and `follow_links` are about documents attached to a page, so
                  they cannot express that. `follow_pages` takes:

                      href_contains: substrings a link's href must contain
                                     (required; this is what picks out the
                                     detail pages among a page's other links)
                      match/exclude: the same keyword filters, applied to the
                                     link text and href of a candidate page
                      type/stage:    what to record the followed pages as
                      max:           safety cap on how many to follow (default 500)
                      paginate:      how to follow a list split across several
                                     pages — see below

                  A bare list is shorthand for `href_contains`. Every followed
                  page becomes its own canonical record, so each one keeps its
                  own URL, hash and fetch time.
    paginate:     (inside `follow_pages`) follow a list that the platform splits
                  across several addresses. A committee system that shows five
                  rows and then a "2" link is publishing one list at several
                  URLs, and keeping only the first page silently understates the
                  record — a councillor on ten committees reads as a councillor
                  on five. Takes the same `href_contains` (a bare list is
                  shorthand) plus `max`, a cap on the extra pages taken per list
                  (default 20). Each further page is fetched as its own
                  canonical record, so nothing is stitched together in the dark.
    redact:       list of redaction rules applied to what was downloaded BEFORE
                  it is saved or hashed — see REDACTORS below for the rules that
                  exist. This is the only thing in the pipeline that changes a
                  document. The file on disk, the sha256 in the manifest and
                  every later stage all see the redacted bytes; no unredacted
                  copy is written anywhere, including in the archive.
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"

# Councils' publishing platforms routinely reject the stock requests User-Agent.
# A normal browser string is the difference between a 200 and a 403; nothing here
# depends on pretending to be a person.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 CouncilLens-ingest/0.3"
)
TIMEOUT = 30

# Content types we know how to store and, later, extract text from.
_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/html": ".html",
    "application/json": ".json",
    "text/plain": ".txt",
    "application/rtf": ".rtf",
    "text/csv": ".csv",
}

# Councils' own pages mix quoting styles inside one document — CMIS writes its
# committee document links with double quotes and its councillor links with
# single ones — so both are accepted here. A pattern that only understood double
# quotes silently found no councillors at all, which is the worst kind of bug:
# a clean run that fetched nothing.
_ANCHOR_RE = re.compile(
    r"""<a\b[^>]*?href=(?P<q>["'])(?P<href>[^"'>]*)(?P=q)[^>]*>(?P<text>.*?)</a>""",
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SIZE_SUFFIX_RE = re.compile(r"\s*\((?:PDF,?\s*)?[\d.,]+\s*[KMG]?B\)\s*$", re.I)


def _http_get(url, headers=None, allow_redirects=True):
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    resp = requests.get(url, timeout=TIMEOUT, headers=hdrs, allow_redirects=allow_redirects)
    resp.raise_for_status()
    return resp


def _strip_tags(fragment):
    import html as _html

    return " ".join(_html.unescape(_TAG_RE.sub(" ", fragment)).split())


def _slug(text, fallback="document"):
    """Stable, readable slug. Same title in, same slug out — record ids must not
    move between runs, or provenance and the AI cache both break."""
    text = _SIZE_SUFFIX_RE.sub("", text or "")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return (slug or fallback)[:80].strip("-") or fallback


def _extension_for(resp, url):
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype in _EXTENSIONS:
        return _EXTENSIONS[ctype]
    suffix = Path(unquote(urlparse(url).path)).suffix.lower()
    return suffix if suffix in set(_EXTENSIONS.values()) else ".bin"


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------
# Some of what a council publishes about a person is not something a mirror of
# the council's record should keep. A councillor's mobile number is the clearest
# case: the council prints it, but it is that person's phone, not a contact route
# the council chose to staff — and one greppable file holding all of them is a
# different thing from thirty-nine pages behind a committee system.
#
# So a source can name redaction rules with `redact:`, and they are applied to
# the downloaded bytes before anything saves or hashes them. There is no
# unredacted copy: the record's sha256 is the sha256 of the file as stored, and
# the manifest, the extracted text and the site all follow from that.
#
# Rules are generic and live here, never in a council's config. Which rules a
# source needs is a question about what that council publishes, and is answered
# in config.

REDACTION_MARKER = "[phone number removed]"

# UK numbers as people and councils actually write them: 07xxx xxxxxx, 01603
# xxxxxx, +44 7xxx xxxxxx, with or without spaces, dots, hyphens or a bracketed
# trunk zero. Anchored so a run of digits inside a longer number, an id or a date
# cannot match.
_UK_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+44\s?\(?0?\)?\s?|0)"
    r"(?:7\d{3}|1\d{2,3}|2\d{2}|3\d{2}|8\d{2})"
    r"[\s.\-]?\d{3}[\s.\-]?\d{3,4}(?!\d)"
)


def _redact_uk_phone_numbers(text):
    """Replace every UK telephone number with a marker that says so.

    Deliberately blunt: it takes the council's own switchboard number out of an
    archived page as well as a councillor's mobile. A missing switchboard number
    costs a reader nothing — the council's website has it — and the alternative
    is a rule that has to judge whose phone each number is.
    """
    return _UK_PHONE_RE.sub(REDACTION_MARKER, text)


REDACTORS = {
    "uk_phone_numbers": _redact_uk_phone_numbers,
}


def redact(source, content):
    """Apply a source's `redact:` rules to downloaded bytes.

    Only text is redacted, and "text" means bytes that decode as UTF-8. A PDF or
    a Word file is left exactly as the council served it: a blind substitution
    inside a compressed stream would corrupt the document rather than clean it.
    Where a council publishes personal data inside a PDF, the answer is to not
    bank that PDF, which is a config decision, not a job for a regular
    expression.
    """
    rules = source.get("redact") or []
    if not rules:
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        print(f"        redact: {source.get('id')} is not text, left as published")
        return content
    for name in rules:
        rule = REDACTORS.get(str(name))
        if rule is None:
            print(f"        redact: no rule called {name!r} — nothing applied")
            continue
        text = rule(text)
    return text.encode("utf-8")


def _matches(source, *candidates):
    """Config decides which documents matter. Code only applies the rule."""
    haystack = " ".join(c for c in candidates if c).lower()
    excludes = [str(x).lower() for x in (source.get("exclude") or [])]
    if any(x in haystack for x in excludes):
        return False
    keywords = [str(x).lower() for x in (source.get("match") or [])]
    if not keywords:
        return True
    return any(k in haystack for k in keywords)


class Adapter(ABC):
    """Base adapter. Subclasses MUST return canonical records (see canonical.py)."""

    platform = "base"

    # ---- shared plumbing -------------------------------------------------

    def _body(self, source, resp):
        """What this project keeps of a response: the bytes, redacted as the
        source asks, and the same bytes as text. Everything that saves, hashes or
        reads a page goes through here, so there is one place where a redaction
        can be missed and it is this one."""
        content = redact(source, resp.content)
        encoding = resp.encoding or resp.apparent_encoding or "utf-8"
        try:
            text = content.decode(encoding, errors="replace")
        except LookupError:
            text = content.decode("utf-8", errors="replace")
        return content, text

    def _save(self, source_id, filename, content):
        out_dir = RAW_DIR / source_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename
        out_path.write_bytes(content)
        return out_path

    def _record(self, source, council, topic, *, record_id, title, url, content,
                saved_to, doc_type=None, stage=None):
        return {
            "id": record_id,
            "council": council,
            "topic": topic,
            "body": source.get("body"),
            "stage": stage if stage is not None else source.get("stage"),
            "type": doc_type or source.get("type", "unknown"),
            "platform": source.get("platform", self.platform),
            "title": title,
            "text": "",
            "source_url": url,
            "saved_to": str(saved_to.relative_to(ROOT)),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def _fetch_document(self, source, council, topic, **kwargs):
        """Download one linked document and return a canonical record (or None)."""
        return self._fetch_document_with_text(source, council, topic, **kwargs)[0]

    def _fetch_document_with_text(self, source, council, topic, *, url, title,
                                  suffix_hint=None, doc_type=None, seen_ids=None,
                                  stage=None):
        """As `_fetch_document`, and also hands back the page's text.

        A page that is one of several in a list carries the links to the rest, so
        whatever followed it needs to read it. Returns (record, text), either of
        which may be None."""
        max_bytes = source.get("max_bytes")
        try:
            resp = _http_get(url)
        except Exception as exc:
            print(f"        skip {title!r}: {exc}")
            return None, None
        content, text = self._body(source, resp)
        if max_bytes and len(content) > int(max_bytes):
            print(f"        skip {title!r}: {len(content)} bytes over max_bytes")
            return None, None

        record_id = f"{source['id']}--{_slug(title)}"
        if seen_ids is not None:
            base = record_id
            n = 2
            while record_id in seen_ids:
                record_id = f"{base}-{n}"
                n += 1
            seen_ids.add(record_id)

        ext = suffix_hint or _extension_for(resp, resp.url or url)
        saved = self._save(source["id"], f"{_slug(title)}{ext}", content)
        record = self._record(
            source, council, topic,
            record_id=record_id,
            title=_SIZE_SUFFIX_RE.sub("", title).strip() or record_id,
            url=url,
            content=content,
            saved_to=saved,
            doc_type=doc_type,
            stage=stage,
        )
        return record, text

    def _followed_pages(self, source, council, topic, html, base_url, seen_ids):
        """Fetch the pages a list page points at, if the config asks for it.

        A councillor directory is a list of links to one page per councillor; a
        committee index is a list of links to one page per committee. The page
        that lists them is not the evidence — the pages it points at are. Which
        links those are is a question about the council's own site, so it is
        answered in config (`follow_pages`), never here.
        """
        spec = source.get("follow_pages")
        if not spec:
            return []
        if isinstance(spec, (list, tuple)):
            spec = {"href_contains": list(spec)}
        needles = [str(x).lower() for x in (spec.get("href_contains") or [])]
        if not needles:
            print(f"        follow_pages on {source.get('id')} has no href_contains — nothing followed")
            return []
        limit = int(spec.get("max", 500))

        out = []
        seen_urls = set()
        for match in _ANCHOR_RE.finditer(html or ""):
            if len(out) >= limit:
                print(f"        follow_pages: stopped at the cap of {limit} pages")
                break
            href = match.group("href")
            if not any(n in href.lower() for n in needles):
                continue
            title = _strip_tags(match.group("text"))
            if not title:
                # A thumbnail wrapped in the same link as the name. The name link
                # carries the words, so nothing is lost by skipping this one.
                continue
            if not _matches(spec, title, href):
                continue
            page_url = urljoin(base_url, href.replace("&amp;", "&"))
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            rec, page_html = self._fetch_document_with_text(
                source, council, topic,
                url=page_url,
                title=title,
                doc_type=spec.get("type"),
                stage=spec.get("stage", source.get("stage")),
                seen_ids=seen_ids,
            )
            if rec:
                out.append(rec)
                out.extend(self._paginated_pages(
                    source, council, topic, spec,
                    base_url=page_url, html=page_html, title=title, seen_ids=seen_ids))
        return out

    def _paginated_pages(self, source, council, topic, spec, *, base_url, html,
                         title, seen_ids):
        """Follow the rest of a list the platform split across several pages.

        A committee system that shows five rows and then a link to page two is
        publishing one list at several addresses. Keeping only the first page
        does not merely lose rows: it presents a shortened list as though it were
        the whole one. Which links are pager links is a question about the
        platform's own markup, so `paginate.href_contains` answers it in config.

        Each further page becomes its own canonical record, with its own URL,
        hash and fetch time. Nothing is stitched together here — the analyse
        stage reads the pages and decides what they add up to.
        """
        rules = spec.get("paginate")
        if not rules:
            return []
        if isinstance(rules, (list, tuple)):
            rules = {"href_contains": list(rules)}
        needles = [str(x).lower() for x in (rules.get("href_contains") or [])]
        if not needles:
            print(f"        paginate on {source.get('id')} has no href_contains — nothing followed")
            return []
        limit = int(rules.get("max", 20))

        out = []
        queue = [(base_url, html or "")]
        seen_urls = {base_url}
        capped = False
        while queue and not capped:
            page_url, page_html = queue.pop(0)
            for match in _ANCHOR_RE.finditer(page_html):
                if len(out) >= limit:
                    print(f"        paginate: stopped at the cap of {limit} more pages")
                    capped = True
                    break
                href = match.group("href")
                if not any(n in href.lower() for n in needles):
                    continue
                next_url = urljoin(page_url, href.replace("&amp;", "&"))
                if next_url in seen_urls:
                    continue
                seen_urls.add(next_url)
                label = _strip_tags(match.group("text")) or str(len(out) + 2)
                rec, next_html = self._fetch_document_with_text(
                    source, council, topic,
                    url=next_url,
                    title=f"{title} (list continued, {label})",
                    doc_type=spec.get("type"),
                    stage=spec.get("stage", source.get("stage")),
                    seen_ids=seen_ids,
                )
                if rec:
                    out.append(rec)
                    queue.append((next_url, next_html or ""))
        return out

    def _explicit_documents(self, source, council, topic, seen_ids):
        """Fetch the `documents:` list from config, if there is one."""
        out = []
        for entry in source.get("documents") or []:
            if isinstance(entry, str):
                entry = {"url": entry, "title": entry}
            rec = self._fetch_document(
                source, council, topic,
                url=entry["url"],
                title=entry.get("title") or entry["url"],
                doc_type=entry.get("type"),
                stage=entry.get("stage"),
                seen_ids=seen_ids,
            )
            if rec:
                out.append(rec)
        return out

    @abstractmethod
    def fetch(self, source, council, topic):
        """Return a list of canonical-record dicts for one configured source."""
        raise NotImplementedError


class GenericAdapter(Adapter):
    """Fallback: archive whatever is at the URL and emit one provenance record.

    Text extraction is left to the transform stage; this adapter only fetches and
    records provenance. It works for any URL, which is why it is the default when a
    platform has no dedicated adapter yet.
    """

    platform = "generic"

    def fetch(self, source, council, topic):
        url = source["url"]
        resp = _http_get(url)
        content, text = self._body(source, resp)
        name = Path(unquote(urlparse(url).path)).name
        if not Path(name).suffix:
            name = (name or "index") + _extension_for(resp, url)
        saved = self._save(source["id"], name, content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        records.extend(self._followed_pages(
            source, council, topic, text, resp.url or url, seen_ids))
        records.extend(self._explicit_documents(source, council, topic, seen_ids))
        return records


class CmisAdapter(Adapter):
    """CMIS (Modern.gov's rival; used by Norwich and many other councils).

    Parses a CMIS committee page or meeting page and emits one canonical record
    per document the config asks for — agenda reports, appendices, minutes — plus,
    optionally, the page itself. A meeting with no papers published yet produces
    just the page record, which is exactly the evidence needed to say "still
    waiting" honestly rather than silently dropping the meeting.

    CMIS serves documents from /Live/Document.ashx with an opaque signed query
    string and no filename, so the file extension comes from the response's
    content type and the record id comes from the link text.
    """

    platform = "cmis"

    # CMIS document links; also tolerate councils that expose plain PDFs.
    _DOC_HREF_RE = re.compile(r"(?i)(document\.ashx|\.pdf($|\?)|\.docx?($|\?))")

    def fetch(self, source, council, topic):
        url = source["url"]
        resp = _http_get(url)
        content, text = self._body(source, resp)
        html = html_text = text
        saved = self._save(source["id"], "page.html", content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=content,
            saved_to=saved,
        )

        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        seen_urls = set()

        if source.get("follow_links", True):
            for match in _ANCHOR_RE.finditer(html):
                href = match.group("href")
                if not self._DOC_HREF_RE.search(href):
                    continue
                title = _strip_tags(match.group("text"))
                if not title:
                    continue
                if not _matches(source, title, href):
                    continue
                doc_url = urljoin(resp.url or url, href.replace("&amp;", "&"))
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)
                rec = self._fetch_document(
                    source, council, topic,
                    url=doc_url,
                    title=title,
                    doc_type=self._infer_type(title, source),
                    seen_ids=seen_ids,
                )
                if rec:
                    records.append(rec)

        records.extend(self._followed_pages(
            source, council, topic, html_text, resp.url or url, seen_ids))
        records.extend(self._explicit_documents(source, council, topic, seen_ids))
        return records

    @staticmethod
    def _infer_type(title, source):
        """CMIS labels its own documents in a standard vocabulary. Reading that
        vocabulary is platform knowledge, not council knowledge."""
        low = title.lower()
        if "minutes" in low:
            return "minutes"
        if "agenda" in low:
            return "agenda"
        return source.get("type", "unknown")


class LocalGovDrupalAdapter(Adapter):
    """LocalGov Drupal — the shared Drupal distribution many UK councils run.

    Fetches the page and any documents linked from it that match the config's
    `match` keywords. If the configured URL is itself a document (councils publish
    adopted policies as bare PDFs), it is archived directly.
    """

    platform = "localgov_drupal"

    _DOC_HREF_RE = re.compile(r"(?i)(\.pdf($|\?)|\.docx?($|\?)|/downloads?/(file|download)/)")

    def fetch(self, source, council, topic):
        url = source["url"]
        resp = _http_get(url)
        content, text = self._body(source, resp)
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = _extension_for(resp, resp.url or url)

        # The URL is the document itself — archive it and stop.
        if ctype != "text/html":
            saved = self._save(source["id"], f"{_slug(source.get('title', source['id']))}{ext}", content)
            return [self._record(
                source, council, topic,
                record_id=source["id"],
                title=source.get("title", source["id"]),
                url=url,
                content=content,
                saved_to=saved,
            )]

        html_text = text
        saved = self._save(source["id"], "page.html", content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        seen_urls = set()

        if source.get("follow_links", True):
            for match in _ANCHOR_RE.finditer(text):
                href = match.group("href")
                if not self._DOC_HREF_RE.search(href):
                    continue
                title = _strip_tags(match.group("text"))
                if not title or not _matches(source, title, href):
                    continue
                doc_url = urljoin(resp.url or url, href.replace("&amp;", "&"))
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)
                rec = self._fetch_document(
                    source, council, topic,
                    url=doc_url, title=title, seen_ids=seen_ids,
                )
                if rec:
                    records.append(rec)

        records.extend(self._followed_pages(
            source, council, topic, html_text, resp.url or url, seen_ids))
        records.extend(self._explicit_documents(source, council, topic, seen_ids))
        return records


class EngagementAdapter(Adapter):
    """Engagement platforms (EngagementHQ / Granicus and friends).

    Fetches the consultation page plus the documents attached to it — draft
    policies, summaries of changes, and, once a consultation closes, the published
    response report. On EngagementHQ the visible document link is a JavaScript
    viewer shell; the real file sits behind the same path with `/download`, and
    `.json` alongside it gives the document's real name. Both are handled here so
    nothing downstream ever sees a cookie banner where a policy should be.
    """

    platform = "engagement"

    _DOC_HREF_RE = re.compile(r"/widgets/\d+/documents/(\d+)(?:$|[?#])")

    def fetch(self, source, council, topic):
        url = source["url"]
        resp = _http_get(url)
        content, text = self._body(source, resp)
        html_text = text
        saved = self._save(source["id"], "page.html", content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        seen_urls = set()

        if source.get("follow_links", True):
            for match in _ANCHOR_RE.finditer(text):
                href = match.group("href")
                if not self._DOC_HREF_RE.search(href):
                    continue
                doc_url = urljoin(resp.url or url, href.replace("&amp;", "&"))
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)

                title = _strip_tags(match.group("text"))
                suffix = None
                # Ask the platform for the document's real name and extension.
                try:
                    meta = _http_get(doc_url + ".json").json().get("document", {})
                    title = meta.get("name") or title
                    filename = meta.get("filename") or ""
                    if Path(filename).suffix:
                        suffix = Path(filename).suffix.lower()
                except Exception:
                    pass
                if not title or not _matches(source, title, href):
                    continue

                rec = self._fetch_document(
                    source, council, topic,
                    url=doc_url + "/download",
                    title=title,
                    suffix_hint=suffix,
                    seen_ids=seen_ids,
                )
                if rec:
                    records.append(rec)

        records.extend(self._followed_pages(
            source, council, topic, html_text, resp.url or url, seen_ids))
        records.extend(self._explicit_documents(source, council, topic, seen_ids))
        return records


# Map a platform name (from config) to its adapter. Unknown platforms fall back to
# the generic adapter, so the pipeline never breaks on an unsupported council.
_ADAPTERS = {
    "generic": GenericAdapter,
    "cmis": CmisAdapter,
    "localgov_drupal": LocalGovDrupalAdapter,
    "engagement": EngagementAdapter,
    # TODO: "modern_gov", "citizen_space", "commonplace", "engagement_hq"
}


def get_adapter(platform):
    return _ADAPTERS.get(platform or "generic", GenericAdapter)()
