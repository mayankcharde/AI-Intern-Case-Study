"""Tests for weekly aggregation and cost-per-tonne-km calculation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.weekly_aggregation import aggregate_weekly, monday_of_week


@pytest.fixture
def sample_shipments():
    return pd.DataFrame({
        "shipment_id": ["S1", "S2", "S3", "S4", "S5", "S6"],
        "origin": ["Mumbai", "Mumbai", "Mumbai", "Delhi", "Mumbai", "Mumbai"],
        "destination": ["Pune", "Pune", "Pune", "Jaipur", "Pune", "Pune"],
        "route_type": ["Short", "Short", "Short", "Short", "Short", "Short"],
        "material": ["A", "B", "C", "A", "D", "E"],
        "quantity_tonnes": [10.0, 20.0, 5.0, 15.0, 8.0, 12.0],
        "distance_km": [100.0, 100.0, 100.0, 200.0, 100.0, 100.0],
        "freight_cost_inr": [1000, 4000, 500, 6000, 1600, 2400],
        "shipment_date": pd.to_datetime([
            "2024-01-01",  # Monday -> week 2024-01-01
            "2024-01-03",  # same week
            "2024-01-07",  # Sunday same week
            "2024-01-02",  # Delhi-Jaipur same week
            "2024-01-08",  # Monday -> week 2024-01-08
            "2024-01-10",  # same week as 2024-01-08
        ]),
        "transporter": ["T1", "T2", "T3", "T4", "T5", "T6"],
    })


def test_monday_of_week():
    dates = pd.Series(pd.to_datetime([
        "2024-01-01",  # Monday
        "2024-01-03",  # Wednesday
        "2024-01-07",  # Sunday
        "2024-01-08",  # Monday
    ]))
    mondays = monday_of_week(dates)
    assert mondays[0] == pd.Timestamp("2024-01-01")
    assert mondays[1] == pd.Timestamp("2024-01-01")
    assert mondays[2] == pd.Timestamp("2024-01-01")
    assert mondays[3] == pd.Timestamp("2024-01-08")


def test_cost_per_tonne_km_aggregation(sample_shipments):
    weekly = aggregate_weekly(sample_shipments)

    mp_w1 = weekly[(weekly["route"] == "Mumbai-Pune") & (weekly["week_of"] == "2024-01-01")]
    assert len(mp_w1) == 1
    total_cost = 1000 + 4000 + 500
    total_tkm = 10 * 100 + 20 * 100 + 5 * 100
    expected = total_cost / total_tkm
    assert abs(mp_w1["cost_per_tonne_km"].iloc[0] - expected) < 1e-9


def test_weekly_grouping_separates_weeks(sample_shipments):
    weekly = aggregate_weekly(sample_shipments)
    mp = weekly[weekly["route"] == "Mumbai-Pune"]
    weeks = sorted(mp["week_of"].tolist())
    assert weeks == ["2024-01-01", "2024-01-08"]


def test_route_separation(sample_shipments):
    weekly = aggregate_weekly(sample_shipments)
    routes = weekly["route"].unique()
    assert set(routes) == {"Mumbai-Pune", "Delhi-Jaipur"}


def test_no_unweighted_average_of_ratios():
    df = pd.DataFrame({
        "shipment_id": ["S1", "S2"],
        "origin": ["A", "A"],
        "destination": ["B", "B"],
        "route_type": ["Short", "Short"],
        "material": ["X", "Y"],
        "quantity_tonnes": [1.0, 100.0],
        "distance_km": [10.0, 10.0],
        "freight_cost_inr": [100, 100],
        "shipment_date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
        "transporter": ["T", "T"],
    })
    weekly = aggregate_weekly(df)
    cost = weekly["cost_per_tonne_km"].iloc[0]
    expected = (100 + 100) / (1 * 10 + 100 * 10)
    assert abs(cost - expected) < 1e-9
