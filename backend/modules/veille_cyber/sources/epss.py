"""FIRST EPSS scores: probability that a CVE is exploited in the next 30 days."""

from dataclasses import dataclass

import httpx2

EPSS_URL = "https://api.first.org/data/v1/epss"
BATCH_SIZE = 100  # keeps the URL short and matches the API's default page size


@dataclass(frozen=True)
class EpssScore:
    epss: float
    percentile: float


def parse_epss(data: dict) -> dict[str, EpssScore]:
    return {
        item["cve"]: EpssScore(epss=float(item["epss"]), percentile=float(item["percentile"]))
        for item in data.get("data", [])
    }


def fetch_epss(http: httpx2.Client, cve_ids: list[str]) -> dict[str, EpssScore]:
    scores: dict[str, EpssScore] = {}
    for start in range(0, len(cve_ids), BATCH_SIZE):
        batch = cve_ids[start : start + BATCH_SIZE]
        response = http.get(EPSS_URL, params={"cve": ",".join(batch), "limit": BATCH_SIZE})
        response.raise_for_status()
        scores.update(parse_epss(response.json()))
    return scores
