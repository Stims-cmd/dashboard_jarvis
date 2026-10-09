"""NIST National Vulnerability Database, CVE API 2.0."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx2

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
# NVD limit: 5 requests per rolling 30 s without a key, 50 with a key.
DELAY_WITHOUT_KEY = 6.0
DELAY_WITH_KEY = 0.6
# Most recent CVSS version first.
CVSS_KEYS = ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30")


@dataclass(frozen=True)
class NvdCve:
    cve_id: str
    description: str
    published: datetime
    cvss_score: float | None
    cvss_severity: str | None
    cvss_version: str | None
    vendor: str | None
    product: str | None


def _pick_cvss(metrics: dict) -> tuple[float | None, str | None, str | None]:
    for key in CVSS_KEYS:
        candidates = metrics.get(key) or []
        if candidates:
            # Prefer NVD's own ("Primary") score when there are several.
            metric = next((m for m in candidates if m.get("type") == "Primary"), candidates[0])
            data = metric["cvssData"]
            return data.get("baseScore"), data.get("baseSeverity"), data.get("version")
    return None, None, None


def _pick_product(cve: dict) -> tuple[str | None, str | None]:
    # cpe:2.3:<part>:<vendor>:<product>:... - missing while NVD has not analysed the CVE.
    for config in cve.get("configurations", []):
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                if match.get("vulnerable"):
                    parts = match["criteria"].split(":")
                    if len(parts) > 4:
                        return parts[3].replace("_", " "), parts[4].replace("_", " ")
    return None, None


def parse_nvd(data: dict) -> list[NvdCve]:
    results = []
    for item in data.get("vulnerabilities", []):
        cve = item["cve"]
        description = next(
            (d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), ""
        )
        score, severity, version = _pick_cvss(cve.get("metrics", {}))
        vendor, product = _pick_product(cve)
        results.append(
            NvdCve(
                cve_id=cve["id"],
                description=description.strip(),
                published=datetime.fromisoformat(cve["published"]).replace(tzinfo=UTC),
                cvss_score=score,
                cvss_severity=severity,
                cvss_version=version,
                vendor=vendor,
                product=product,
            )
        )
    return results


def _nvd_date(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class NvdClient:
    """Calls the NVD API while respecting its rate limit."""

    def __init__(
        self,
        http: httpx2.Client,
        api_key: str | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self._http = http
        self._headers = {"apiKey": api_key} if api_key else {}
        self._delay = DELAY_WITH_KEY if api_key else DELAY_WITHOUT_KEY
        self._sleep = sleep or time.sleep
        self._requests = 0

    def _get(self, params: dict) -> dict:
        if self._requests:
            self._sleep(self._delay)
        self._requests += 1
        response = self._http.get(NVD_URL, params=params, headers=self._headers)
        response.raise_for_status()
        return response.json()

    def get_cve(self, cve_id: str) -> NvdCve | None:
        found = parse_nvd(self._get({"cveId": cve_id}))
        return found[0] if found else None

    def critical_published(self, start: datetime, end: datetime) -> list[NvdCve]:
        """CVEs published in [start, end] rated CRITICAL in CVSS 3.x or 4.0."""
        by_id: dict[str, NvdCve] = {}
        for severity_param in ("cvssV3Severity", "cvssV4Severity"):
            start_index = 0
            while True:
                data = self._get(
                    {
                        "pubStartDate": _nvd_date(start),
                        "pubEndDate": _nvd_date(end),
                        severity_param: "CRITICAL",
                        "startIndex": start_index,
                    }
                )
                for cve in parse_nvd(data):
                    by_id[cve.cve_id] = cve
                start_index += data.get("resultsPerPage", 0)
                if not data.get("resultsPerPage") or start_index >= data.get("totalResults", 0):
                    break
        return list(by_id.values())
