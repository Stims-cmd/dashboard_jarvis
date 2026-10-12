"""OSINT sources, all through official public APIs (no scraping).

Each source returns RawFinding objects; the collector stores and compares them.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawFinding:
    kind: str
    subject: str
    source: str
    key: str
    title: str
    details: dict = field(default_factory=dict)
