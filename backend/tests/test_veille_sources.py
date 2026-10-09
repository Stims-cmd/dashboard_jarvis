import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx2
import pytest

from app.http import make_http_client
from modules.veille_cyber.sources.epss import fetch_epss, parse_epss
from modules.veille_cyber.sources.kev import parse_kev
from modules.veille_cyber.sources.nvd import NvdClient, parse_nvd

FIXTURES = Path(__file__).parent / "fixtures" / "veille_cyber"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_kev():
    entries = parse_kev(load("kev.json"))
    assert len(entries) == 4
    log4shell = next(e for e in entries if e.cve_id == "CVE-2021-44228")
    assert log4shell.vendor == "Apache"
    assert log4shell.date_added == date(2021, 12, 10)
    assert log4shell.ransomware is True
    assert all(e.description for e in entries)


def test_parse_nvd_prefers_newest_cvss_version():
    cves = {c.cve_id: c for c in parse_nvd(load("nvd_critical.json"))}
    assert len(cves) == 3
    both = cves["CVE-2026-107699"]  # has CVSS 4.0 and 3.1
    assert (both.cvss_version, both.cvss_score, both.cvss_severity) == ("4.0", 9.3, "CRITICAL")
    assert both.published.tzinfo is UTC
    assert both.product is None  # not yet analysed by NVD: no CPE


def test_parse_nvd_product_from_cpe():
    (cve,) = parse_nvd(load("nvd_cve.json"))
    assert cve.cve_id == "CVE-2015-5477"
    assert (cve.vendor, cve.product) == ("isc", "bind")
    assert cve.description.startswith("named in ISC BIND")


def test_parse_epss():
    scores = parse_epss(load("epss.json"))
    assert scores["CVE-2021-44228"].epss > 0.9
    assert 0 <= scores["CVE-2026-17609"].percentile <= 1


def test_nvd_client_respects_rate_limit_and_paginates():
    page = load("nvd_critical.json")
    seen_params, sleeps = [], []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_params.append(dict(request.url.params))
        assert "apiKey" not in request.headers
        return httpx2.Response(200, json=page | {"resultsPerPage": 3, "totalResults": 3})

    with make_http_client(httpx2.MockTransport(handler)) as http:
        nvd = NvdClient(http, sleep=sleeps.append)
        start = datetime(2026, 10, 8, tzinfo=UTC)
        found = nvd.critical_published(start, datetime(2026, 10, 9, tzinfo=UTC))

    assert len(found) == 3  # same CVEs from the v3 and v4 queries are merged
    assert [p.get("cvssV3Severity") or p.get("cvssV4Severity") for p in seen_params] == [
        "CRITICAL",
        "CRITICAL",
    ]
    assert seen_params[0]["pubStartDate"] == "2026-10-08T00:00:00.000Z"
    assert sleeps == [6.0]  # one pause between the two requests, none before the first


def test_nvd_api_key_sent_as_header():
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["apiKey"] == "secret"
        assert "secret" not in str(request.url)
        return httpx2.Response(200, json=load("nvd_cve.json"))

    with make_http_client(httpx2.MockTransport(handler)) as http:
        assert NvdClient(http, api_key="secret").get_cve("CVE-2015-5477") is not None


def test_fetch_epss_batches():
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.params["cve"].split(","))
        return httpx2.Response(200, json=load("epss.json"))

    ids = [f"CVE-2026-{n}" for n in range(150)]
    with make_http_client(httpx2.MockTransport(handler)) as http:
        fetch_epss(http, ids)
    assert [len(batch) for batch in calls] == [100, 50]


def test_http_error_raises():
    with (
        make_http_client(httpx2.MockTransport(lambda r: httpx2.Response(503))) as http,
        pytest.raises(httpx2.HTTPStatusError),
    ):
        NvdClient(http).get_cve("CVE-2015-5477")
