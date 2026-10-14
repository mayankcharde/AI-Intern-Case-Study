"""Tests for historical and peer baseline calculations."""

from __future__ import annotations

import pandas as pd
import pytest

from src.baseline_calculator import add_historical_baseline, add_peer_baseline
from src.config import HISTORICAL_WINDOW


def _make_weekly(costs, route="R1", route_type="Short"):
    weeks = pd.date_range("2024-01-01", periods=len(costs), freq="W-MON")
    return pd.DataFrame({
        "route": [route] * len(costs),
        "origin": ["A"] * len(costs),
        "destination": ["B"] * len(costs),
        "route_type": [route_type] * len(costs),
        "week_of": [w.strftime("%Y-%m-%d") for w in weeks],
        "cost_per_tonne_km": costs,
    })


def test_historical_uses_prior_weeks_only():
    costs = [1.0, 2.0, 3.0, 4.0]
    df = _make_weekly(costs)
    out = add_historical_baseline(df)

    assert pd.isna(out.loc[0, "vs_own_history_pct"])
    assert out.loc[0, "historical_count"] == 0

    assert out.loc[1, "historical_avg"] == 1.0
    assert out.loc[1, "historical_count"] == 1

    assert out.loc[2, "historical_avg"] == (1.0 + 2.0) / 2
    assert out.loc[2, "historical_count"] == 2


def test_historical_uses_at_most_eight_prior():
    costs = list(range(1, 15))
    df = _make_weekly(costs)
    out = add_historical_baseline(df)

    last = out.iloc[-1]
    assert last["historical_count"] == HISTORICAL_WINDOW
    expected_avg = sum(range(6, 14)) / 8
    assert abs(last["historical_avg"] - expected_avg) < 1e-9


def test_historical_fewer_than_eight():
    costs = [1.0, 2.0, 3.0]
    df = _make_weekly(costs)
    out = add_historical_baseline(df)
    assert out.loc[2, "historical_count"] == 2
    assert out.loc[2, "historical_avg"] == (1.0 + 2.0) / 2


def test_historical_percentage_calculation():
    costs = [10.0, 12.0]
    df = _make_weekly(costs)
    out = add_historical_baseline(df)
    pct = out.loc[1, "vs_own_history_pct"]
    assert abs(pct - 20.0) < 1e-9


def test_historical_negative_change():
    costs = [10.0, 8.0]
    df = _make_weekly(costs)
    out = add_historical_baseline(df)
    pct = out.loc[1, "vs_own_history_pct"]
    assert abs(pct - (-20.0)) < 1e-9


def test_historical_zero_baseline_unavailable():
    costs = [0.0, 5.0]
    df = _make_weekly(costs)
    out = add_historical_baseline(df)
    assert pd.isna(out.loc[1, "vs_own_history_pct"])


def test_peer_average_excludes_current_route():
    df = pd.DataFrame({
        "route": ["R1", "R2", "R3"],
        "origin": ["A", "C", "E"],
        "destination": ["B", "D", "F"],
        "route_type": ["Short", "Short", "Short"],
        "week_of": ["2024-01-01", "2024-01-01", "2024-01-01"],
        "cost_per_tonne_km": [10.0, 20.0, 30.0],
    })
    out = add_peer_baseline(df)
    r1 = out[out["route"] == "R1"].iloc[0]
    assert r1["peer_avg"] == (20.0 + 30.0) / 2
    r2 = out[out["route"] == "R2"].iloc[0]
    assert r2["peer_avg"] == (10.0 + 30.0) / 2


def test_peer_grouping_by_route_type():
    df = pd.DataFrame({
        "route": ["R1", "R2", "R3"],
        "origin": ["A", "C", "E"],
        "destination": ["B", "D", "F"],
        "route_type": ["Short", "Short", "Long"],
        "week_of": ["2024-01-01", "2024-01-01", "2024-01-01"],
        "cost_per_tonne_km": [10.0, 20.0, 100.0],
    })
    out = add_peer_baseline(df)
    r1 = out[out["route"] == "R1"].iloc[0]
    assert r1["peer_avg"] == 20.0
    r3 = out[out["route"] == "R3"].iloc[0]
    assert pd.isna(r3["vs_similar_routes_pct"])


def test_peer_no_peers_unavailable():
    df = pd.DataFrame({
        "route": ["R1"],
        "origin": ["A"],
        "destination": ["B"],
        "route_type": ["Short"],
        "week_of": ["2024-01-01"],
        "cost_per_tonne_km": [10.0],
    })
    out = add_peer_baseline(df)
    assert pd.isna(out.loc[0, "vs_similar_routes_pct"])


def test_peer_zero_average_unavailable():
    df = pd.DataFrame({
        "route": ["R1", "R2"],
        "origin": ["A", "C"],
        "destination": ["B", "D"],
        "route_type": ["Short", "Short"],
        "week_of": ["2024-01-01", "2024-01-01"],
        "cost_per_tonne_km": [10.0, 0.0],
    })
    out = add_peer_baseline(df)
    r1 = out[out["route"] == "R1"].iloc[0]
    assert r1["peer_avg"] == 0.0
    assert pd.isna(r1["vs_similar_routes_pct"])
