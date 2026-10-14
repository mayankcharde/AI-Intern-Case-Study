"""Compute historical and peer baselines for weekly route costs."""

from __future__ import annotations

import pandas as pd

from src.config import HISTORICAL_WINDOW


def add_historical_baseline(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add vs_own_history for each (route, week).

    Uses the trailing HISTORICAL_WINDOW prior weekly cost observations for the
    same route, strictly before the current week. If fewer are available, use
    all available prior observations. Never pad, extrapolate, or include the
    current week.

    vs_own_history = ((current - historical_avg) / historical_avg) * 100
    """
    df = weekly.copy().sort_values(["route", "week_of"]).reset_index(drop=True)
    df["week_of_dt"] = pd.to_datetime(df["week_of"])

    hist_avgs: list[float | None] = []
    hist_counts: list[int] = []

    for route, group in df.groupby("route", sort=False):
        costs = group["cost_per_tonne_km"].tolist()
        n = len(costs)
        for i in range(n):
            prior = costs[max(0, i - HISTORICAL_WINDOW):i]
            if not prior:
                hist_avgs.append(None)
                hist_counts.append(0)
            else:
                hist_avgs.append(sum(prior) / len(prior))
                hist_counts.append(len(prior))

    df["historical_avg"] = hist_avgs
    df["historical_count"] = hist_counts

    def calc_pct(row):
        avg = row["historical_avg"]
        if avg is None or pd.isna(avg) or avg == 0:
            return None
        cur = row["cost_per_tonne_km"]
        return ((cur - avg) / avg) * 100.0

    df["vs_own_history_pct"] = df.apply(calc_pct, axis=1)
    df = df.drop(columns=["week_of_dt"])
    return df


def add_peer_baseline(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add vs_similar_routes for each (route, week).

    Uses the same-week cost per tonne-km across all OTHER routes that share the
    same route_type. Excludes the current route and any invalid/unavailable
    peer costs.

    vs_similar_routes = ((current - peer_avg) / peer_avg) * 100
    """
    df = weekly.copy()

    peer_avgs: list[float | None] = []
    for _, row in df.iterrows():
        week = row["week_of"]
        rtype = row["route_type"]
        route = row["route"]
        peers = df[
            (df["week_of"] == week)
            & (df["route_type"] == rtype)
            & (df["route"] != route)
        ]
        peer_costs = peers["cost_per_tonne_km"].dropna()
        if peer_costs.empty:
            peer_avgs.append(None)
        else:
            peer_avgs.append(peer_costs.mean())

    df["peer_avg"] = peer_avgs

    def calc_pct(row):
        avg = row["peer_avg"]
        if avg is None or pd.isna(avg) or avg == 0:
            return None
        cur = row["cost_per_tonne_km"]
        return ((cur - avg) / avg) * 100.0

    df["vs_similar_routes_pct"] = df.apply(calc_pct, axis=1)
    return df
