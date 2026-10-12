"""Pure helpers of the sale assistant (no database, easy to test).

Jarvis never publishes nor sends anything: it prepares texts and suggestions,
the owner decides, copies and publishes.
"""

import re
import statistics
from dataclasses import dataclass
from datetime import date

CONDITION_LABELS = {
    "neuf": "Neuf",
    "tres_bon": "Très bon état",
    "bon": "Bon état",
    "correct": "État correct",
    "pieces": "Pour pièces",
}
PRICE_DROP_RATIO = 0.9  # suggested drop: 10 %

# Contact details must never reach the Claude API, even if typed in the notes.
# IBAN first: it contains digit groups that would otherwise look like phone numbers.
_REDACTIONS = (
    re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b"),
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"(?:\+33\s?|0033\s?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b"),
)
REDACTED = "[retiré]"


def redact(text: str) -> str:
    for pattern in _REDACTIONS:
        text = pattern.sub(REDACTED, text)
    return text


@dataclass(frozen=True)
class PriceReminder:
    due: bool
    since: date  # listing date or last price change, whichever is later
    suggested_cents: int | None  # None: already at the floor price
    at_floor: bool


def suggested_price_cents(asking_cents: int, floor_cents: int | None) -> int | None:
    """10 % less, rounded down to the euro, never under the floor. None if no drop left."""
    suggested = int(asking_cents * PRICE_DROP_RATIO) // 100 * 100
    suggested = max(suggested, floor_cents or 0)
    return suggested if suggested < asking_cents else None


def last_price_change(price_history: list) -> date | None:
    """Date of the last change. The first entry is the initial price, not a change."""
    return date.fromisoformat(price_history[-1][0][:10]) if len(price_history) > 1 else None


def price_reminder(
    *,
    status: str,
    listed_on: date | None,
    asking_cents: int,
    floor_cents: int | None,
    lower_after_days: int,
    price_history: list,
    today: date,
) -> PriceReminder | None:
    """Reminder to lower the price of an item listed for a while without selling."""
    if status != "listed" or listed_on is None:
        return None
    changed = last_price_change(price_history)
    since = max(listed_on, changed) if changed else listed_on
    suggested = suggested_price_cents(asking_cents, floor_cents)
    return PriceReminder(
        due=(today - since).days >= lower_after_days,
        since=since,
        suggested_cents=suggested,
        at_floor=suggested is None,
    )


@dataclass(frozen=True)
class PriceStats:
    count: int
    min_cents: int | None
    median_cents: int | None
    max_cents: int | None


def comparables_stats(prices_cents: list[int]) -> PriceStats:
    if not prices_cents:
        return PriceStats(0, None, None, None)
    return PriceStats(
        count=len(prices_cents),
        min_cents=min(prices_cents),
        median_cents=round(statistics.median(prices_cents)),
        max_cents=max(prices_cents),
    )


def euros(cents: int) -> str:
    """French price without decimals when round: 1 250 € / 12,50 €."""
    whole, rest = divmod(cents, 100)
    text = f"{whole:,}".replace(",", " ")
    return f"{text},{rest:02d} €" if rest else f"{text} €"


def template_draft(title: str, condition: str, notes: str, asking_cents: int) -> tuple[str, str]:
    """Plain draft used without Claude: (title, body)."""
    label = CONDITION_LABELS.get(condition, condition)
    lines = [f"{title} – {label.lower()}.", ""]
    if notes.strip():
        lines += [notes.strip(), ""]
    lines += [
        f"Prix : {euros(asking_cents)}.",
        "N'hésitez pas à me poser vos questions.",
    ]
    return title[:100], "\n".join(lines)
