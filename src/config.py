"""Configuration constants for the FreightTiger pipeline.

All thresholds, paths, and output schema definitions live here so they can be
reviewed and changed in one place. Values that are *engineering assumptions*
(rather than explicit FreightTiger requirements) are clearly marked.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = PROJECT_ROOT / "reports"

SHIPMENTS_FILE = DATA_DIR / "shipment_records.csv"
NOTES_FILE = DATA_DIR / "context_notes.csv"
SAMPLE_OUTPUT_FILE = DATA_DIR / "sample_output_format_v2.csv"
FINAL_OUTPUT_FILE = OUTPUT_DIR / "final_output.csv"

REQUIRED_SHIPMENT_COLUMNS = [
    "shipment_id",
    "origin",
    "destination",
    "route_type",
    "material",
    "quantity_tonnes",
    "distance_km",
    "freight_cost_inr",
    "shipment_date",
    "transporter",
]

REQUIRED_NOTE_COLUMNS = ["note_id", "date", "applies_to", "note"]

ROUTE_KEY_COLUMNS = ["origin", "destination", "route_type"]

OUTPUT_COLUMNS = [
    "route",
    "week_of",
    "cost_per_tonne_km",
    "vs_own_history",
    "vs_similar_routes",
    "flagged",
    "matched_note_id",
    "reason",
]

HISTORICAL_WINDOW = 8

HISTORICAL_ANOMALY_THRESHOLD_PCT = 15.0
PEER_ANOMALY_THRESHOLD_PCT = 15.0

COST_PER_TONNE_KM_DECIMALS = 2
PERCENTAGE_DECIMALS = 1

EVENT_IMPACT_WINDOW_DAYS = 14

ALL_ROUTES_TOKEN = "All Routes"

FLAG_YES = "Yes"
FLAG_NO = "No"
FLAG_JUSTIFIED = "No (justified)"

VERDICT_JUSTIFIED = "JUSTIFIED"
VERDICT_UNEXPLAINED = "UNEXPLAINED"
VERDICT_NOT_FLAGGED = "NOT_FLAGGED"

LLM_USED = False
LLM_PROVIDER = "none"
LLM_MODEL = "none"
LLM_INPUT_TOKEN_PRICE = 0.0
LLM_OUTPUT_TOKEN_PRICE = 0.0
