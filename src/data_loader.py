"""Load shipment records and context notes from CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import (
    REQUIRED_NOTE_COLUMNS,
    REQUIRED_SHIPMENT_COLUMNS,
)


def load_shipments(path: str | Path) -> pd.DataFrame:
    """Load the shipment records CSV and validate required columns."""
    df = pd.read_csv(path, dtype={
        "shipment_id": str,
        "origin": str,
        "destination": str,
        "route_type": str,
        "material": str,
        "transporter": str,
    })
    missing = [c for c in REQUIRED_SHIPMENT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"shipment_records.csv missing required columns: {missing}"
        )
    df["shipment_date"] = pd.to_datetime(
        df["shipment_date"], errors="coerce"
    )
    for col in ("quantity_tonnes", "distance_km", "freight_cost_inr"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_notes(path: str | Path) -> pd.DataFrame:
    """Load the context notes CSV and validate required columns."""
    df = pd.read_csv(path, dtype={
        "note_id": str,
        "applies_to": str,
        "note": str,
    })
    missing = [c for c in REQUIRED_NOTE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"context_notes.csv missing required columns: {missing}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df
