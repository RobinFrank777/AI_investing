"""Minimal completed-session boundary for US daily production bars."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


NEW_YORK = ZoneInfo("America/New_York")
DAILY_BAR_COMPLETION_TIME = time(16, 15)


def current_us_session_is_complete(now=None):
    """Return whether today's regular US daily bar is safe to consume.

    The 15-minute close buffer avoids treating a still-settling 16:00 daily bar
    as canonical. Weekends have no current trading session.
    """
    moment = datetime.now(tz=NEW_YORK) if now is None else now
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    eastern = moment.astimezone(NEW_YORK)
    return eastern.weekday() >= 5 or eastern.time() >= DAILY_BAR_COMPLETION_TIME


def completed_daily_bars(frame, now=None):
    """Exclude only a still-open current US session from a daily frame."""
    if frame.empty or current_us_session_is_complete(now):
        return frame.copy()
    moment = datetime.now(tz=NEW_YORK) if now is None else now.astimezone(NEW_YORK)
    dates = pd.to_datetime(frame.index, errors="coerce")
    current_session = dates.date == moment.date()
    return frame.loc[~current_session].copy()


def latest_completed_session_date(now=None):
    """Return the conservative latest completed US weekday session date."""
    moment = datetime.now(tz=NEW_YORK) if now is None else now
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    eastern = moment.astimezone(NEW_YORK)
    candidate = eastern.date()
    if eastern.weekday() < 5 and eastern.time() < DAILY_BAR_COMPLETION_TIME:
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate
