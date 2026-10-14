"""Write the final output CSV matching the exact schema contract."""

from __future__ import annotations

import os

import pandas as pd

from src.config import (
    COST_PER_TONNE_KM_DECIMALS,
    OUTPUT_COLUMNS,
    OUTPUT_DIR,
    FINAL_OUTPUT_FILE,
    SAMPLE_OUTPUT_FILE,
)


def validate_output_schema(df: pd.DataFrame) -> None:
    """Verify the output DataFrame matches the sample contract exactly."""
    with open(SAMPLE_OUTPUT_FILE, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    expected = header.split(",")
    actual = list(df.columns)
    if actual != expected:
        raise ValueError(
            f"Output columns {actual} do not match expected {expected}"
        )
    if "Unnamed: 0" in actual or actual[0] == "":
        raise ValueError("Output contains an extra index column")


def write_final_output(df: pd.DataFrame, path: str | None = None) -> str:
    """Write the final output CSV and return the path."""
    out_path = str(path or FINAL_OUTPUT_FILE)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    out = df.copy()
    out["cost_per_tonne_km"] = out["cost_per_tonne_km"].round(COST_PER_TONNE_KM_DECIMALS)

    out = out[OUTPUT_COLUMNS]
    out.to_csv(out_path, index=False)

    written = pd.read_csv(out_path)
    validate_output_schema(written)
    return out_path
