"""Generate deterministic explanations and map verdicts to the output schema."""

from __future__ import annotations

import pandas as pd

from src.config import (
    COST_PER_TONNE_KM_DECIMALS,
    PERCENTAGE_DECIMALS,
    FLAG_YES,
    FLAG_NO,
    FLAG_JUSTIFIED,
    VERDICT_JUSTIFIED,
    VERDICT_UNEXPLAINED,
    VERDICT_NOT_FLAGGED,
)


def format_pct(value: float | None) -> str:
    """Format a percentage change for the vs_* columns.

    Example: +35.5% or -12.3%. Unavailable -> "N/A".
    """
    if value is None or pd.isna(value):
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{PERCENTAGE_DECIMALS}f}%"


def format_vs_own_history(pct: float | None) -> str:
    if pct is None or pd.isna(pct):
        return "N/A"
    return f"{format_pct(pct)} vs this route's past average"


def format_vs_similar_routes(pct: float | None) -> str:
    if pct is None or pd.isna(pct):
        return "N/A"
    return f"{format_pct(pct)} vs similar-length routes this week"


def build_reason(
    route: str,
    week_of: str,
    flagged: bool,
    verdict: str,
    matched_note: pd.Series | None,
    vs_own: float | None,
    vs_peer: float | None,
) -> str:
    """Build a deterministic, evidence-grounded reason string."""
    if not flagged:
        return (
            "Cost is within expected range relative to this route's history and "
            "similar-length routes; not flagged."
        )

    if verdict == VERDICT_JUSTIFIED and matched_note is not None:
        nid = matched_note["note_id"]
        ndate = pd.to_datetime(matched_note["date"]).strftime("%Y-%m-%d")
        content = str(matched_note["note"]).strip()
        return (
            f"Matches note {nid} dated {ndate}: {content} "
            "The cost rise has a clear explanation."
        )

    if verdict == VERDICT_UNEXPLAINED:
        parts = []
        if vs_own is not None and not pd.isna(vs_own):
            parts.append(f"{format_pct(vs_own)} vs own history")
        if vs_peer is not None and not pd.isna(vs_peer):
            parts.append(f"{format_pct(vs_peer)} vs similar routes")
        comparison = " and ".join(parts) if parts else "above thresholds"
        return (
            f"No matching note found for this route or date range. "
            f"Cost rise ({comparison}) looks unexplained and worth a human review."
        )

    return "Not flagged."


def map_flagged(flagged: bool, verdict: str) -> str:
    """Map the internal flag/verdict to the output 'flagged' column."""
    if not flagged:
        return FLAG_NO
    if verdict == VERDICT_JUSTIFIED:
        return FLAG_JUSTIFIED
    return FLAG_YES
