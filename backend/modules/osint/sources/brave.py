"""Brave Search API: exact-match web mentions of a name or phone number."""

import re

import httpx2

from modules.osint.sources import RawFinding

SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 20
_TAGS = re.compile(r"<[^>]+>")


def _plain(text: str) -> str:
    # Brave highlights matches with <strong>: keep plain text only.
    return _TAGS.sub("", text or "").strip()


def parse_results(data: dict, subject: str) -> list[RawFinding]:
    findings = []
    for result in (data.get("web") or {}).get("results") or []:
        url = result.get("url")
        if not url or not url.startswith(("https://", "http://")):
            continue
        findings.append(
            RawFinding(
                kind="mention",
                subject=subject,
                source="brave",
                key=url[:500],
                title=_plain(result.get("title"))[:500] or url[:500],
                details={"snippet": _plain(result.get("description"))[:500]},
            )
        )
    return findings


def search(http: httpx2.Client, api_key: str, query: str, subject: str) -> list[RawFinding]:
    response = http.get(
        SEARCH_URL,
        params={"q": f'"{query}"', "count": MAX_RESULTS},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
    )
    response.raise_for_status()
    return parse_results(response.json(), subject)
