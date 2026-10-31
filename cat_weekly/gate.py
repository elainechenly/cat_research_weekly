"""Decide whether a scheduled run should send now: any time on Tuesday, Pacific time."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config


def should_run_now(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:                       # treat naive datetimes as UTC
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ZoneInfo(config.SEND_TZ)).weekday() == config.SEND_WEEKDAY
