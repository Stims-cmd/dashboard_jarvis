"""CISA Known Exploited Vulnerabilities catalog (public JSON feed)."""

from dataclasses import dataclass
from datetime import date

import httpx2

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


@dataclass(frozen=True)
class KevEntry:
    cve_id: str
    vendor: str
    product: str
    name: str
    description: str
    date_added: date
    due_date: date | None
    ransomware: bool


def parse_kev(data: dict) -> list[KevEntry]:
    entries = []
    for item in data["vulnerabilities"]:
        due = item.get("dueDate")
        entries.append(
            KevEntry(
                cve_id=item["cveID"].strip(),
                vendor=item.get("vendorProject", "").strip(),
                product=item.get("product", "").strip(),
                name=item.get("vulnerabilityName", "").strip(),
                description=item.get("shortDescription", "").strip(),
                date_added=date.fromisoformat(item["dateAdded"]),
                due_date=date.fromisoformat(due) if due else None,
                ransomware=item.get("knownRansomwareCampaignUse") == "Known",
            )
        )
    return entries


def fetch_kev(http: httpx2.Client) -> list[KevEntry]:
    response = http.get(KEV_URL)
    response.raise_for_status()
    return parse_kev(response.json())
