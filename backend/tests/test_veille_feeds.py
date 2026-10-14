"""News feed parsing (Veille cyber). No network: recorded feeds and fake answers."""

import pyexpat
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from app.http import make_http_client
from modules.veille_cyber.sources import feeds
from modules.veille_cyber.sources.feeds import (
    FeedError,
    clean_link,
    fetch_feed,
    parse_feed,
    plain_text,
)

FIXTURES = Path(__file__).parent / "fixtures" / "veille_cyber"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_expat_is_protected_against_entity_expansion():
    # Python's XML docs: Expat before 2.7.2 may be vulnerable to billion laughs & co.
    version = tuple(int(x) for x in pyexpat.EXPAT_VERSION.removeprefix("expat_").split("."))
    assert version >= (2, 7, 2)


@pytest.mark.parametrize(
    ("name", "first_title"),
    [
        ("cert_fr_alerte.xml", "Incident de sécurité ciblant les contrôleurs à distance"),
        ("cert_fr_cti.xml", "Vulnérabilités de produits du secteur santé"),
        ("cert_fr_actualite.xml", "Bulletin d'actualité CERTFR-2026-ACT-043"),
        ("zataz.xml", "Une cyberattaque dérègle le froid des supermarchés"),
    ],
)
def test_recorded_feeds(name, first_title):
    articles = parse_feed(fixture(name))
    assert len(articles) == 3
    assert articles[0].title.startswith(first_title)
    assert all(a.link.startswith("https://") for a in articles)
    assert all(a.published_at and a.published_at.tzinfo for a in articles)
    # Most recent first, whatever the order in the feed (CERT-FR lists the oldest first).
    dates = [a.published_at for a in articles]
    assert dates == sorted(dates, reverse=True)


def test_zataz_entities_and_cdata():
    articles = parse_feed(fixture("zataz.xml"))
    assert articles[0].summary.startswith("Une cyberattaque vise le froid des supermarchés")
    assert articles[0].published_at == datetime(2026, 10, 12, 11, 29, 45, tzinfo=UTC)


def test_atom_feed():
    atom = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Exemple</title>
      <entry>
        <title type="html">Fuite &lt;b&gt;massive&lt;/b&gt;</title>
        <link rel="alternate" href="https://example.org/fuite?utm_source=rss&amp;id=4#top"/>
        <summary type="html">&lt;p&gt;Un &lt;a href="x"&gt;texte&lt;/a&gt;.&lt;/p&gt;</summary>
        <updated>2026-10-13T08:00:00+02:00</updated>
      </entry>
    </feed>"""
    [article] = parse_feed(atom)
    assert article.title == "Fuite massive"
    assert article.link == "https://example.org/fuite?id=4"
    assert article.summary == "Un texte."
    assert article.published_at == datetime(2026, 10, 13, 6, 0, tzinfo=UTC)


def test_unsafe_or_useless_items_are_skipped():
    rss = b"""<rss version="2.0"><channel>
      <item><title>Lien http</title><link>http://example.org/a</link></item>
      <item><title>Script</title><link>javascript:alert(1)</link></item>
      <item><title></title><link>https://example.org/sans-titre</link></item>
      <item>
        <title>OK</title><link>https://example.org/ok</link><pubDate>n'importe quoi</pubDate>
      </item>
    </channel></rss>"""
    [article] = parse_feed(rss)
    assert article.title == "OK"
    assert article.published_at is None


@pytest.mark.parametrize(
    "payload",
    [
        # Billion laughs
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">'
        b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><rss><channel><item>'
        b"<title>&b;</title></item></channel></rss>",
        # XXE: read a local file
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<rss><channel><item><title>&x;</title></item></channel></rss>",
    ],
)
def test_malicious_xml_is_refused(payload):
    with pytest.raises(FeedError):
        parse_feed(payload)


@pytest.mark.parametrize("payload", [b"pas du xml", b"<html><body>Erreur</body></html>"])
def test_not_a_feed(payload):
    with pytest.raises(FeedError):
        parse_feed(payload)


def test_plain_text_and_links():
    assert plain_text("<p>Bonjour&nbsp;<b>à</b>\n  tous</p>", 100) == "Bonjour à tous"
    assert plain_text("x" * 20, 10) == "x" * 9 + "…"
    assert clean_link("https://Example.ORG/a?fbclid=1&p=2") == "https://example.org/a?p=2"
    assert clean_link("ftp://example.org/a") is None


def test_fetch_feed_caps_the_size(monkeypatch):
    monkeypatch.setattr(feeds, "MAX_BYTES", 1000)

    def internet(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/big":
            return httpx2.Response(200, content=b"x" * 5000)
        return httpx2.Response(200, content=fixture("zataz.xml")[:900])

    with make_http_client(httpx2.MockTransport(internet)) as http:
        assert len(fetch_feed(http, "https://example.org/small")) == 900
        with pytest.raises(FeedError):
            fetch_feed(http, "https://example.org/big")


def test_fetch_feed_raises_on_http_error():
    transport = httpx2.MockTransport(lambda r: httpx2.Response(503))
    with make_http_client(transport) as http, pytest.raises(httpx2.HTTPStatusError):
        fetch_feed(http, "https://example.org/feed")
