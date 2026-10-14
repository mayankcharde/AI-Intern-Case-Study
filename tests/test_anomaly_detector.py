"""Tests for the anomaly detector."""

from __future__ import annotations

import pandas as pd
import pytest

from src.anomaly_detector import detect_anomalies


def _df(hist, peer):
    return pd.DataFrame({
        "route": ["R1"],
        "week_of": ["2024-01-01"],
        "cost_per_tonne_km": [1.0],
        "vs_own_history_pct": [hist],
        "vs_similar_routes_pct": [peer],
    })


def test_flagged_when_historical_above_threshold():
    df = _df(20.0, 5.0)
    out = detect_anomalies(df, historical_threshold_pct=15.0, peer_threshold_pct=15.0)
    assert bool(out.loc[0, "flagged"]) is True
    assert bool(out.loc[0, "historical_anomaly"]) is True
    assert bool(out.loc[0, "peer_anomaly"]) is False


def test_flagged_when_peer_above_threshold():
    df = _df(5.0, 20.0)
    out = detect_anomalies(df)
    assert bool(out.loc[0, "flagged"]) is True
    assert bool(out.loc[0, "peer_anomaly"]) is True


def test_not_flagged_when_both_below_threshold():
    df = _df(10.0, 10.0)
    out = detect_anomalies(df)
    assert bool(out.loc[0, "flagged"]) is False


def test_not_flagged_when_exactly_at_threshold():
    df = _df(15.0, 15.0)
    out = detect_anomalies(df)
    assert bool(out.loc[0, "flagged"]) is False


def test_negative_changes_not_flagged():
    df = _df(-30.0, -20.0)
    out = detect_anomalies(df)
    assert bool(out.loc[0, "flagged"]) is False


def test_missing_baseline_not_treated_as_anomaly():
    df = _df(None, None)
    out = detect_anomalies(df)
    assert bool(out.loc[0, "flagged"]) is False
    df2 = _df(None, 20.0)
    out2 = detect_anomalies(df2)
    assert bool(out2.loc[0, "flagged"]) is True


def test_configurable_thresholds():
    df = _df(10.0, 10.0)
    out = detect_anomalies(df, historical_threshold_pct=5.0, peer_threshold_pct=5.0)
    assert bool(out.loc[0, "flagged"]) is True
