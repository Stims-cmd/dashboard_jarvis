"""Hourly collection of the Leboncoin alerts received in the dedicated mailbox.

Logs never contain the address, subjects nor ad content: only counters and error types.
"""

import hashlib
import logging
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.collect import CollectContext
from modules.leboncoin.mailbox import ImapConfig, ImapMailbox, Mailbox
from modules.leboncoin.models import Ad, Message
from modules.leboncoin.parser import Alert, parse_alert

logger = logging.getLogger(__name__)

LOOKBACK = timedelta(days=14)
# Emails with these statuses are never processed again. A parse error is retried,
# so that a fixed parser catches up on the emails it missed.
DONE = ("ok", "ignored")

OpenMailbox = Callable[[ImapConfig], AbstractContextManager[Mailbox]]


def message_key(message_id: str) -> str:
    return hashlib.sha256(message_id.encode()).hexdigest()


def collect(ctx: CollectContext, open_mailbox: OpenMailbox = ImapMailbox) -> dict[str, int]:
    config = ImapConfig.from_settings(ctx.settings)
    if config is None:
        return {"skipped": 1}

    counts: Counter[str] = Counter()
    with open_mailbox(config) as box:
        for uid, message_id in box.list_since((ctx.now - LOOKBACK).date()):
            key = message_key(message_id)
            known = ctx.db.get(Message, key)
            if known is not None and known.status in DONE:
                continue
            raw = box.fetch(uid)
            try:
                alert = parse_alert(raw)
            except Exception as error:  # noqa: BLE001 - one bad email must not stop the others
                logger.warning("leboncoin: alert not parsed: %s", type(error).__name__)
                _mark(ctx, key, "parse_error", None, 0)
                counts["parse_errors"] += 1
                continue
            if alert is None:
                _mark(ctx, key, "ignored", None, 0)
                counts["ignored"] += 1
                continue
            counts["new_ads"] += _store_ads(ctx, alert)
            _mark(ctx, key, "ok", _utc(alert.received_at), len(alert.ads))
            counts["emails"] += 1

    result = {name: counts[name] for name in ("emails", "new_ads", "ignored", "parse_errors")}
    logger.info("leboncoin: %s", ", ".join(f"{k}={v}" for k, v in result.items()))
    return result


def _mark(
    ctx: CollectContext, key: str, status: str, received_at: datetime | None, ads_count: int
) -> None:
    message = ctx.db.get(Message, key) or Message(key=key)
    message.status = status
    message.received_at = received_at
    message.processed_at = ctx.now
    message.ads_count = ads_count
    ctx.db.add(message)
    ctx.db.commit()  # one commit per email: an interrupted run keeps its progress


def _store_ads(ctx: CollectContext, alert: Alert) -> int:
    seen_at = _utc(alert.received_at) or ctx.now
    new = 0
    for item in alert.ads:
        ad = ctx.db.scalar(select(Ad).where(Ad.ad_id == item.ad_id))
        if ad is None:
            ad = Ad(
                ad_id=item.ad_id,
                search_name=alert.search_name,
                price_history=[[seen_at.isoformat(), item.price_cents]],
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            )
            ctx.db.add(ad)
            new += 1
        elif item.price_cents != ad.price_cents:
            # A new list is assigned: SQLAlchemy does not see in-place JSON changes.
            ad.price_history = [*ad.price_history, [seen_at.isoformat(), item.price_cents]]
        ad.title = item.title
        ad.price_cents = item.price_cents
        ad.location = item.location
        ad.url = item.url
        ad.last_seen_at = max(_naive(ad.last_seen_at), _naive(seen_at))
        ctx.db.flush()
    return new


def _utc(value: datetime | None) -> datetime | None:
    # SQLite stores datetimes without their offset: everything is converted to UTC first.
    return value.astimezone(UTC) if value and value.tzinfo else value


def _naive(value: datetime) -> datetime:
    # SQLite gives back naive datetimes (UTC): compare everything as naive UTC.
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
