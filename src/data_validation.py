"""Validate shipment records and produce a data-quality report."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd


def validate_shipments(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate shipment records.

    Rules (do not silently replace invalid values with zero:
    - quantity_tonnes must be positive
    - distance_km must be positive
    - freight_cost_inr must be non-negative
    - shipment_date must be parseable

    Returns the valid rows and a quality report describing dropped/invalid records.
    """
    report: dict[str, Any] = {
        "total_records": int(len(df)),
        "invalid_records": [],
        "dropped_count": 0,
    }

    valid_mask = (
        df["quantity_tonnes"].notna()
        & (df["quantity_tonnes"] > 0)
        & df["distance_km"].notna()
        & (df["distance_km"] > 0)
        & df["freight_cost_inr"].notna()
        & (df["freight_cost_inr"] >= 0)
        & df["shipment_date"].notna()
        & df["origin"].notna()
        & df["destination"].notna()
        & df["route_type"].notna()
    )

    invalid = df.loc[~valid_mask].copy()
    for _, row in invalid.iterrows():
        reasons = []
        if pd.isna(row["quantity_tonnes"]) or row["quantity_tonnes"] <= 0:
            reasons.append("invalid quantity_tonnes")
        if pd.isna(row["distance_km"]) or row["distance_km"] <= 0:
            reasons.append("invalid distance_km")
        if pd.isna(row["freight_cost_inr"]) or row["freight_cost_inr"] < 0:
            reasons.append("invalid freight_cost_inr")
        if pd.isna(row["shipment_date"]):
            reasons.append("invalid shipment_date")
        if pd.isna(row["origin"]) or pd.isna(row["destination"]):
            reasons.append("missing origin/destination")
        if pd.isna(row["route_type"]):
            reasons.append("missing route_type")
        report["invalid_records"].append({
            "shipment_id": str(row.get("shipment_id", "")),
            "reasons": reasons,
        })

    report["dropped_count"] = int(len(invalid))
    valid_df = df.loc[valid_mask].copy().reset_index(drop=True)
    return valid_df, report


def save_quality_report(report: dict[str, Any], path: str) -> None:
    """Save the data quality report as JSON."""
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
