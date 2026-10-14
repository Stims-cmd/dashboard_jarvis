"""Public news feeds (RSS 2.0 / Atom) about cyberattacks: CERT-FR and the French press.

Feeds are external data:
- XML is parsed with the standard library. Its Expat (>= 2.7.2) is protected against
  entity expansion attacks and never fetches external entities; documents declaring
  entities are refused anyway, since a news feed never needs them.
- Responses are capped in size (after decompression).
- Titles and summaries are reduced to plain text; only https links are kept.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx2


@dataclass(frozen=True)
class Feed:
    id: str
    label: str
    url: str


# CERT-FR "avis" (vulnerability advisories) are left out on purpose: news only.
FEEDS = (
    Feed("cert_fr_alerte", "CERT-FR · alerte", "https://cert.cyber.gouv.fr/alerte/feed/"),
    Feed("cert_fr_cti", "CERT-FR · menace", "https://cert.cyber.gouv.fr/cti/feed/"),
    Feed("cert_fr_actualite", "CERT-FR · bulletin", "https://cert.cyber.gouv.fr/actualite/feed/"),
    Feed("zataz", "Zataz", "https://www.zataz.com/feed/"),
)

MAX_BYTES = 5_000_000
MAX_ITEMS = 100
MAX_TITLE = 300
MAX_SUMMARY = 1000
_ATOM = "{http://www.w3.org/2005/Atom}"
_TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|xtor)$", re.IGNORECASE)


class FeedError(Exception):
    """The feed could not be read: too large, not XML, unknown format..."""


@dataclass(frozen=True)
class RawArticle:
    title: str
    link: str
    summary: str
    published_at: datetime | None


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str | None, limit: int) -> str:
    """HTML (or plain) text reduced to one line of plain text."""
    parser = _TextOnly()
    parser.feed(value or "")
    parser.close()
    text = " ".join("".join(parser.parts).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def clean_link(value: str | None) -> str | None:
    """https link without tracking parameters nor fragment, or None."""
    if not value:
        return None
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.netloc:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, ""))[:500]


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)  # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value)  # Atom: RFC 3339
        except ValueError:
            return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _article(title: str | None, link: str | None, summary: str | None, date: str | None):
    link = clean_link(link)
    title = plain_text(title, MAX_TITLE)
    if not link or not title:
        return None
    return RawArticle(title, link, plain_text(summary, MAX_SUMMARY), _date(date))


def _atom_link(entry: ET.Element) -> str | None:
    for link in entry.iterfind(f"{_ATOM}link"):
        if link.get("rel", "alternate") == "alternate":
            return link.get("href")
    return None


def parse_feed(data: bytes) -> list[RawArticle]:
    """Articles of an RSS 2.0 or Atom feed, most recent first."""
    if b"<!ENTITY" in data:
        raise FeedError("entity declarations are refused")
    try:
        root = ET.fromstring(data)  # noqa: S314 - see the module docstring
    except ET.ParseError as error:
        raise FeedError("invalid XML") from error

    if root.tag == "rss":
        found = (
            _article(
                item.findtext("title"),
                item.findtext("link"),
                item.findtext("description"),
                item.findtext("pubDate"),
            )
            for item in root.iterfind("channel/item")
        )
    elif root.tag == f"{_ATOM}feed":
        found = (
            _article(
                entry.findtext(f"{_ATOM}title"),
                _atom_link(entry),
                entry.findtext(f"{_ATOM}summary") or entry.findtext(f"{_ATOM}content"),
                entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated"),
            )
            for entry in root.iterfind(f"{_ATOM}entry")
        )
    else:
        raise FeedError("unknown feed format")

    articles = [a for a in found if a is not None]
    # Feeds are not always sorted (CERT-FR lists the oldest first).
    oldest = datetime.min.replace(tzinfo=UTC)
    articles.sort(key=lambda a: a.published_at or oldest, reverse=True)
    return articles[:MAX_ITEMS]


def fetch_feed(http: httpx2.Client, url: str) -> bytes:
    """Raw feed, read in chunks so that an oversized answer is cut short."""
    accept = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8"
    with http.stream("GET", url, headers={"Accept": accept}) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_bytes():  # decompressed bytes: a gzip bomb is cut too
            size += len(chunk)
            if size > MAX_BYTES:
                raise FeedError("feed too large")
            chunks.append(chunk)
    return b"".join(chunks)
