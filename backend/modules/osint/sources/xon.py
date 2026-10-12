"""XposedOrNot: is an email address part of known data breaches? (free API, no key)"""

import httpx2

from modules.osint.sources import RawFinding

ANALYTICS_URL = "https://api.xposedornot.com/v1/breach-analytics"


def parse_breaches(data: dict, subject: str) -> list[RawFinding]:
    exposed = data.get("ExposedBreaches") or {}
    findings = []
    for breach in exposed.get("breaches_details") or []:
        exposed_data = [d for d in (breach.get("xposed_data") or "").split(";") if d]
        findings.append(
            RawFinding(
                kind="breach",
                subject=subject,
                source="xposedornot",
                key=breach["breach"],
                title=breach["breach"],
                details={
                    "domain": breach.get("domain") or None,
                    "year": breach.get("xposed_date") or None,
                    "records": breach.get("xposed_records"),
                    "data": exposed_data,
                    "password_risk": breach.get("password_risk"),
                    "description": breach.get("details") or "",
                },
            )
        )
    return findings


def fetch_breaches(http: httpx2.Client, email: str, subject: str) -> list[RawFinding]:
    response = http.get(ANALYTICS_URL, params={"email": email})
    if response.status_code == 404:  # also used by the API for "not found"
        return []
    response.raise_for_status()
    return parse_breaches(response.json(), subject)
