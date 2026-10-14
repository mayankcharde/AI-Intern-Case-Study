"""Weekly aggregation of shipment costs per route."""

from __future__ import annotations

import pandas as pd

from src.config import ROUTE_KEY_COLUMNS


def monday_of_week(dates: pd.Series) -> pd.Series:
    """Return the Monday date (as a timestamp) for each date.

    Weeks run Monday through Sunday. The returned value is that week's Monday.
    """
    dt = pd.to_datetime(dates)
    return dt - pd.to_timedelta(dt.dt.weekday, unit="D")


def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate shipments into weekly route cost-per-tonne-km.

    cost_per_tonne_km = sum(freight_cost_inr) / sum(quantity_tonnes * distance_km)

    The denominator is computed per record then summed across the week; the
    numerator is summed freight cost. The ratio is taken after aggregation
    (weighted by tonne-km), never an unweighted average of per-shipment ratios.
    """
    work = df.copy()
    work["week_of"] = monday_of_week(work["shipment_date"])
    work["tonne_km"] = work["quantity_tonnes"] * work["distance_km"]

    grouped = work.groupby(ROUTE_KEY_COLUMNS + ["week_of"], as_index=False).agg(
        total_cost=("freight_cost_inr", "sum"),
        total_tonne_km=("tonne_km", "sum"),
        shipment_count=("shipment_id", "count"),
    )

    grouped = grouped.loc[grouped["total_tonne_km"] > 0]
    grouped["cost_per_tonne_km"] = (
        grouped["total_cost"] / grouped["total_tonne_km"]
    )

    grouped["route"] = (
        grouped["origin"] + "-" + grouped["destination"]
    )

    grouped["week_of"] = grouped["week_of"].dt.strftime("%Y-%m-%d")
    return grouped.sort_values(
        ["route", "week_of"]
    ).reset_index(drop=True)
