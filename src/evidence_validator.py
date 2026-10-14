"""Validate whether a retrieved note actually justifies a cost increase."""

from __future__ import annotations

import re

import pandas as pd

_COST_INCREASE_KEYWORDS = [
    "higher", "rise", "rose", "surcharge", "increase", "increased",
    "pushing up", "up", "expensive", "costs rose", "disrupt",
    "detour", "limited", "demand", "flood", "maintenance",
    "toll", "fuel", "diesel", "festival", "disruption",
]


_NEGATIVE_OR_NEUTRAL_PATTERNS = [
    r"not\s+(significantly\s+)?affected",
    r"no\s+(significant\s+)?(major\s+)?disrupt",
    r"without\s+a\s+rate\s+change",
    r"returned\s+to\s+normal",
    r"no\s+rate\s+change",
    r"stable\s+(demand|conditions)",
    r"not\s+part\s+of\s+this\s+dataset",
    r"not\s+significantly\s+affected",
    r"improved\s+road\s+conditions",
    r"absorbed\s+by",
    r"normal\s+conditions",
    r"remained\s+normal",
    r"remained\s+stable",
]


def _has_negative_or_neutral_statement(text: str) -> bool:
    """Detect statements that mean costs were not affected / improved."""
    if pd.isna(text):
        return True
    t = str(text).lower()
    for pat in _NEGATIVE_OR_NEUTRAL_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def _describes_cost_increase(text: str) -> bool:
    """Detect language indicating the note describes upward cost-increasing event."""
    if pd.isna(text):
        return False
    t = str(text).lower()
    return any(kw in t for kw in _COST_INCREASE_KEYWORDS)


def _extract_impact_pct(text: str) -> float | None:
    """Extract a rough percentage impact from the note text, if stated."""
    if pd.isna(text):
        return None
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%", str(text))
    if matches:
        try:
            lo, hi = matches[0]
            return (float(lo) + float(hi)) / 2.0
        except (ValueError, TypeError):
            pass
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(text))
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            pass
    return None


def validate_note(
    note: pd.Series,
    route: str,
    week_of: str,
    vs_own_history_pct: float | None,
    vs_similar_routes_pct: float | None,
) -> tuple[bool, str]:
    """Validate whether a note justifies the observed cost increase.

    Returns (is_valid, reason). A note is valid only if ALL of:
    - it applies to the route (checked by retriever)
    - its event window overlaps the shipment week (checked by retriever)
    - it does not explicitly exclude the route or state costs were unaffected
    - it describes an event capable of increasing costs
    - any stated impact percentage is consistent with the observed increase
      (not automatically claim a larger increase than the note supports)
    """
    text = note["note"]

    if _has_negative_or_neutral_statement(text):
        return False, (
            "note states costs were not significantly affected or conditions are normal"
        )

    if not _describes_cost_increase(text):
        return False, "note does not describe a cost-increasing event"

    observed = max(
        vs_own_history_pct if vs_own_history_pct is not None else -1,
        vs_similar_routes_pct if vs_similar_routes_pct is not None else -1,
    )

    impact = _extract_impact_pct(text)
    if impact is not None and observed > 0:
        if impact * 1.5 < observed:
            return False, (
                f"note's stated impact (~{impact:.1f}%) is much smaller than "
                f"the observed increase ({observed:.1f}%)"
            )

    return True, "valid"


def select_best_note(
    candidates: pd.DataFrame,
    route: str,
    week_of: str,
    vs_own_history_pct: float | None,
    vs_similar_routes_pct: float | None,
) -> tuple[pd.Series | None, str]:
    """From candidate notes, select the best validating note.

    Route-specific notes are preferred over "All Routes" notes. Among valid notes,
    the one closest to the shipment week is preferred.
    """
    if candidates.empty:
        return None, "no candidate notes for route/week"

    valid_notes = []
    for _, note in candidates.iterrows():
        ok, reason = validate_note(
            note, route, week_of, vs_own_history_pct, vs_similar_routes_pct
        )
        if ok:
            valid_notes.append(note)

    if not valid_notes:
        return None, "no candidate note passes evidence validation"

    def sort_key(note):
        is_route_specific = 0 if note["applies_to"] == route else 1
        date_distance = abs((note["date"] - pd.to_datetime(week_of)).days)
        return (is_route_specific, date_distance)

    valid_notes.sort(key=sort_key)
    return valid_notes[0], "ok"
