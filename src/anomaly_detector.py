"""Anomaly detection with configurable thresholds."""

from __future__ import annotations

import pandas as pd

from src.config import (
    HISTORICAL_ANOMALY_THRESHOLD_PCT,
    PEER_ANOMALY_THRESHOLD_PCT,
)


def detect_anomalies(
    df: pd.DataFrame,
    historical_threshold_pct: float = HISTORICAL_ANOMALY_THRESHOLD_PCT,
    peer_threshold_pct: float = PEER_ANOMALY_THRESHOLD_PCT,
) -> pd.DataFrame:
    """Flag route-weeks whose cost increase crosses a configured threshold.

    A route-week is flagged if at least one *valid* comparison crosses its
    threshold. An unavailable baseline is NOT treated as an anomaly.

    Engineering assumption (not a FreightTiger requirement): both thresholds
    default to 15%. This is documented in the README.
    """
    out = df.copy()

    hist = out["vs_own_history_pct"]
    peer = out["vs_similar_routes_pct"]

    out["historical_anomaly"] = hist.notna() & (hist > historical_threshold_pct)
    out["peer_anomaly"] = peer.notna() & (peer > peer_threshold_pct)

    out["flagged"] = out["historical_anomaly"] | out["peer_anomaly"]
    return out
