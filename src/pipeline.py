"""Main pipeline orchestrating all processing stages."""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

from src.config import (
    FINAL_OUTPUT_FILE,
    NOTES_FILE,
    OUTPUT_COLUMNS,
    REPORTS_DIR,
    SHIPMENTS_FILE,
    VERDICT_JUSTIFIED,
    VERDICT_NOT_FLAGGED,
    VERDICT_UNEXPLAINED,
    LLM_USED,
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_INPUT_TOKEN_PRICE,
    LLM_OUTPUT_TOKEN_PRICE,
)
from src.data_loader import load_notes, load_shipments
from src.data_validation import save_quality_report, validate_shipments
from src.weekly_aggregation import aggregate_weekly
from src.baseline_calculator import add_historical_baseline, add_peer_baseline
from src.anomaly_detector import detect_anomalies
from src.note_retriever import retrieve_candidate_notes
from src.evidence_validator import select_best_note
from src.explanation_generator import (
    build_reason,
    format_vs_own_history,
    format_vs_similar_routes,
    map_flagged,
)
from src.output_writer import write_final_output


def run_pipeline(
    shipments_path: str | None = None,
    notes_path: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Execute the full pipeline and return a summary of results."""
    shipments_path = shipments_path or str(SHIPMENTS_FILE)
    notes_path = notes_path or str(NOTES_FILE)

    shipments = load_shipments(shipments_path)
    notes = load_notes(notes_path)

    valid_shipments, quality_report = validate_shipments(shipments)
    quality_report_path = REPORTS_DIR / "data_quality_report.json"
    save_quality_report(quality_report, str(quality_report_path))

    weekly = aggregate_weekly(valid_shipments)
    weekly = add_historical_baseline(weekly)
    weekly = add_peer_baseline(weekly)
    weekly = detect_anomalies(weekly)

    notes_by_id = {n["note_id"]: n for _, n in notes.iterrows()}

    matched_note_ids = []
    verdicts = []
    reasons = []

    for _, row in weekly.iterrows():
        route = row["route"]
        week_of = row["week_of"]
        flagged = row["flagged"]
        vs_own = row["vs_own_history_pct"]
        vs_peer = row["vs_similar_routes_pct"]

        if not flagged:
            verdict = VERDICT_NOT_FLAGGED
            matched_note = None
            matched_note_ids.append("")
            verdicts.append(verdict)
            reasons.append(build_reason(route, week_of, flagged, verdict, None, vs_own, vs_peer))
            continue

        candidates = retrieve_candidate_notes(notes, route, week_of)
        best_note, _ = select_best_note(candidates, route, week_of, vs_own, vs_peer)

        if best_note is not None:
            verdict = VERDICT_JUSTIFIED
            matched_note_ids.append(best_note["note_id"])
        else:
            verdict = VERDICT_UNEXPLAINED
            matched_note_ids.append("")

        verdicts.append(verdict)
        reasons.append(build_reason(route, week_of, flagged, verdict, best_note, vs_own, vs_peer))

    weekly["matched_note_id"] = matched_note_ids
    weekly["verdict"] = verdicts
    weekly["reason"] = reasons

    weekly["vs_own_history"] = weekly["vs_own_history_pct"].apply(format_vs_own_history)
    weekly["vs_similar_routes"] = weekly["vs_similar_routes_pct"].apply(format_vs_similar_routes)
    weekly["flagged"] = weekly.apply(
        lambda r: map_flagged(r["flagged"], r["verdict"]), axis=1
    )

    output_path = write_final_output(weekly, output_path)

    summary = {
        "total_input_records": int(len(shipments)),
        "valid_records": int(len(valid_shipments)),
        "dropped_records": int(quality_report["dropped_count"]),
        "output_rows": int(len(weekly)),
        "flagged_routes": int((weekly["flagged"] != "No").sum()),
        "justified_routes": int((weekly["verdict"] == VERDICT_JUSTIFIED).sum()),
        "unexplained_routes": int((weekly["verdict"] == VERDICT_UNEXPLAINED).sum()),
        "not_flagged_routes": int((weekly["verdict"] == VERDICT_NOT_FLAGGED).sum()),
        "output_path": output_path,
    }

    _write_token_cost_log()
    return summary


def _write_token_cost_log() -> None:
    """Write the LLM token/cost log (all zeros since no LLM is used)."""
    log = {
        "llm_used": LLM_USED,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "input_cost_usd": 0.0,
        "output_cost_usd": 0.0,
        "total_cost_usd": 0.0,
        "input_token_price_per_1k": LLM_INPUT_TOKEN_PRICE,
        "output_token_price_per_1k": LLM_OUTPUT_TOKEN_PRICE,
        "failed_calls": 0,
        "retries": 0,
        "cache_hits": 0,
        "pricing_source": "N/A - no LLM used; explanations are deterministic templates",
        "note": "No LLM is used. All explanations are generated from deterministic, evidence-grounded templates. Token and cost statistics are zero by construction.",
    }
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(REPORTS_DIR / "token_cost_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    summary = run_pipeline()
    print(json.dumps(summary, indent=2))
