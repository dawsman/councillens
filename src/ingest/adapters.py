#!/usr/bin/env python3
"""Adapters: one per publishing PLATFORM, never one per council.

A single CMIS adapter serves every council on CMIS; a single LocalGov Drupal
adapter serves every council on that platform. All platform-specific quirks are
absorbed here, so everything downstream sees only canonical records.

Adding a council is a config change (config/sources.yaml). You only add code here
when a council uses a PLATFORM no adapter supports yet.

Config keys every adapter understands (all optional, all in config/sources.yaml —
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

_ANCHOR_RE = re.compile(r"<a\b[^>]*?href=\"(?P<href>[^\"]+)\"[^>]*>(?P<text>.*?)</a>", re.I | re.S)
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

    def _fetch_document(self, source, council, topic, *, url, title, suffix_hint=None,
                        doc_type=None, seen_ids=None, stage=None):
        """Download one linked document and return a canonical record (or None)."""
        max_bytes = source.get("max_bytes")
        try:
            resp = _http_get(url)
        except Exception as exc:
            print(f"        skip {title!r}: {exc}")
            return None
        if max_bytes and len(resp.content) > int(max_bytes):
            print(f"        skip {title!r}: {len(resp.content)} bytes over max_bytes")
            return None

        record_id = f"{source['id']}--{_slug(title)}"
        if seen_ids is not None:
            base = record_id
            n = 2
            while record_id in seen_ids:
                record_id = f"{base}-{n}"
                n += 1
            seen_ids.add(record_id)

        ext = suffix_hint or _extension_for(resp, resp.url or url)
        saved = self._save(source["id"], f"{_slug(title)}{ext}", resp.content)
        return self._record(
            source, council, topic,
            record_id=record_id,
            title=_SIZE_SUFFIX_RE.sub("", title).strip() or record_id,
            url=url,
            content=resp.content,
            saved_to=saved,
            doc_type=doc_type,
            stage=stage,
        )

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
        name = Path(unquote(urlparse(url).path)).name
        if not Path(name).suffix:
            name = (name or "index") + _extension_for(resp, url)
        saved = self._save(source["id"], name, resp.content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=resp.content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        records.extend(self._explicit_documents(source, council, topic, {page["id"]}))
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
        html = resp.text
        saved = self._save(source["id"], "page.html", resp.content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=resp.content,
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
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = _extension_for(resp, resp.url or url)

        # The URL is the document itself — archive it and stop.
        if ctype != "text/html":
            saved = self._save(source["id"], f"{_slug(source.get('title', source['id']))}{ext}", resp.content)
            return [self._record(
                source, council, topic,
                record_id=source["id"],
                title=source.get("title", source["id"]),
                url=url,
                content=resp.content,
                saved_to=saved,
            )]

        saved = self._save(source["id"], "page.html", resp.content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=resp.content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        seen_urls = set()

        if source.get("follow_links", True):
            for match in _ANCHOR_RE.finditer(resp.text):
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
        saved = self._save(source["id"], "page.html", resp.content)
        page = self._record(
            source, council, topic,
            record_id=source["id"],
            title=source.get("title", source["id"]),
            url=url,
            content=resp.content,
            saved_to=saved,
        )
        records = [page] if source.get("include_page", True) else []
        seen_ids = {page["id"]}
        seen_urls = set()

        if source.get("follow_links", True):
            for match in _ANCHOR_RE.finditer(resp.text):
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
