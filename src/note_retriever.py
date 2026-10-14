"""Retrieve candidate context notes for a given route and week."""

from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

from src.config import ALL_ROUTES_TOKEN, EVENT_IMPACT_WINDOW_DAYS

_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_MONTH_DAY_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})",
    re.IGNORECASE,
)
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _note_applies_to_route(note_applies_to: str, route: str) -> bool:
    """Return True if the note's applies_to field covers the given route."""
    if pd.isna(note_applies_to):
        return False
    applies = str(note_applies_to).strip()
    if applies.upper() == ALL_ROUTES_TOKEN.upper():
        return True
    return applies == route


def _extract_date_range_from_text(text: str, note_date: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Try to extract an event date range from the note text.

    Falls back to [note_date - window, note_date + window] when no explicit
    range can be parsed.
    """
    if pd.isna(text):
        return (note_date, note_date)

    iso_matches = _DATE_RE.findall(str(text))
    parsed_iso = []
    for y, m, d in iso_matches:
        try:
            parsed_iso.append(pd.Timestamp(int(y), int(m), int(d)))
        except (ValueError, TypeError):
            continue

    md_matches = _MONTH_DAY_RE.findall(str(text))
    parsed_md = []
    for mon, day in md_matches:
        month = _MONTH_MAP.get(mon.lower())
        if month is None:
            continue
        try:
            parsed_md.append(pd.Timestamp(note_date.year, month, int(day)))
        except (ValueError, TypeError):
            continue

    all_dates = parsed_iso + parsed_md
    if len(all_dates) >= 2:
        all_dates = sorted(set(all_dates))
        return (all_dates[0], all_dates[-1])
    if len(all_dates) == 1:
        return (all_dates[0], all_dates[0])
    return (note_date, note_date)


def _week_overlaps(
    week_monday: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> bool:
    """Check whether the Mon-Sun week overlaps the [start, end] range."""
    week_sunday = week_monday + timedelta(days=6)
    return not (week_sunday < start or week_monday > end)


def retrieve_candidate_notes(
    notes: pd.DataFrame,
    route: str,
    week_of: str,
) -> pd.DataFrame:
    """Return notes that potentially apply to this route and week.

    Filters:
    - applies_to matches the route or is "All Routes"
    - the note's event date range (or its date +/- impact window) overlaps
      the shipment week
    """
    week_monday = pd.to_datetime(week_of)
    candidates = []

    for _, note in notes.iterrows():
        note_date = note["date"]
        if pd.isna(note_date):
            continue
        if not _note_applies_to_route(note["applies_to"], route):
            continue

        start, end = _extract_date_range_from_text(note["note"], note_date)
        window_start = min(start, note_date) - timedelta(days=EVENT_IMPACT_WINDOW_DAYS)
        window_end = max(end, note_date) + timedelta(days=EVENT_IMPACT_WINDOW_DAYS)

        if _week_overlaps(week_monday, window_start, window_end):
            candidates.append(note)

    if not candidates:
        return notes.iloc[0:0].copy()
    return pd.DataFrame(candidates).reset_index(drop=True)
