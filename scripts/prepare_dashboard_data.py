"""Prepare a JSON snapshot of pipeline artifacts for the dashboard.

Reads the actual generated files (final_output.csv, context_notes.csv,
shipment_records.csv, reports/*) and writes a single dashboard_data.json
that the static HTML/CSS/JS dashboard loads.

This keeps the dashboard driven entirely by real pipeline output -- no
hardcoded metrics, routes, anomalies, notes, or costs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    FINAL_OUTPUT_FILE,
    NOTES_FILE,
    REPORTS_DIR,
    SHIPMENTS_FILE,
)

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_OUT = DASHBOARD_DIR / "data" / "dashboard_data.json"


def parse_pct(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or s.upper() == "N/A":
        return None
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def main() -> int:
    final_output = pd.read_csv(FINAL_OUTPUT_FILE)

    shipments = pd.read_csv(SHIPMENTS_FILE)
    route_type_map = (
        shipments.groupby(["origin", "destination", "route_type"])
        .size()
        .reset_index()
        .assign(route=lambda d: d["origin"] + "-" + d["destination"])
        .set_index("route")["route_type"]
        .to_dict()
    )

    notes_df = pd.read_csv(NOTES_FILE)
    notes = notes_df.to_dict(orient="records")
    for n in notes:
        n["date"] = str(n["date"])

    final_output["route_type"] = final_output["route"].map(route_type_map)
    final_output["vs_own_history_pct"] = final_output["vs_own_history"].apply(parse_pct)
    final_output["vs_similar_routes_pct"] = final_output["vs_similar_routes"].apply(parse_pct)

    flagged = final_output["flagged"].astype(str)
    justified_count = int((flagged == "No (justified)").sum())
    unexplained_count = int((flagged == "Yes").sum())
    not_flagged_count = int((flagged == "No").sum())
    total_rows = int(len(final_output))

    records = final_output.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and pd.isna(v):
                r[k] = None
        r["matched_note_id"] = "" if pd.isna(r.get("matched_note_id")) else str(r["matched_note_id"])

    routes = sorted(final_output["route"].unique().tolist())
    route_types = sorted(final_output["route_type"].dropna().unique().tolist())
    weeks = sorted(final_output["week_of"].unique().tolist())
    verdicts = ["All", "Not flagged", "Justified", "Unexplained"]

    route_stats = []
    for route in routes:
        sub = final_output[final_output["route"] == route]
        route_stats.append({
            "route": route,
            "route_type": route_type_map.get(route, ""),
            "weeks": int(len(sub)),
            "flagged": int(((sub["flagged"] == "Yes") | (sub["flagged"] == "No (justified)")).sum()),
            "justified": int((sub["flagged"] == "No (justified)").sum()),
            "unexplained": int((sub["flagged"] == "Yes").sum()),
            "avg_cost": round(float(sub["cost_per_tonne_km"].mean()), 4),
            "min_cost": round(float(sub["cost_per_tonne_km"].min()), 4),
            "max_cost": round(float(sub["cost_per_tonne_km"].max()), 4),
        })

    repro_path = REPORTS_DIR / "reproducibility_report.txt"
    reproducibility = None
    if repro_path.exists():
        txt = repro_path.read_text(encoding="utf-8")
        byte_identical = "Byte-identical outputs: True" in txt
        deterministic_match = "Overall deterministic match: True" in txt
        shas = re.findall(r"SHA-256:\s*([0-9a-f]+)", txt)
        run_counts = re.findall(r"rows:\s*(\d+),\s*flagged:\s*(\d+),\s*justified:\s*(\d+),\s*unexplained:\s*(\d+)", txt)
        reproducibility = {
            "report_text": txt,
            "byte_identical": byte_identical,
            "deterministic_match": deterministic_match,
            "sha256": shas[0] if shas else None,
            "runs": [
                {"rows": int(rc[0]), "flagged": int(rc[1]), "justified": int(rc[2]), "unexplained": int(rc[3])}
                for rc in run_counts
            ],
        }

    token_path = REPORTS_DIR / "token_cost_log.json"
    token_cost = None
    if token_path.exists():
        token_cost = json.loads(token_path.read_text(encoding="utf-8"))

    quality_path = REPORTS_DIR / "data_quality_report.json"
    data_quality = None
    if quality_path.exists():
        data_quality = json.loads(quality_path.read_text(encoding="utf-8"))

    payload = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "source_files": {
            "final_output": str(FINAL_OUTPUT_FILE.relative_to(PROJECT_ROOT)),
            "context_notes": str(NOTES_FILE.relative_to(PROJECT_ROOT)),
        },
        "summary": {
            "total_route_weeks": total_rows,
            "total_routes": len(routes),
            "flagged": justified_count + unexplained_count,
            "justified": justified_count,
            "unexplained": unexplained_count,
            "not_flagged": not_flagged_count,
        },
        "filters": {
            "routes": ["All"] + routes,
            "route_types": ["All"] + route_types,
            "weeks": ["All"] + weeks,
            "verdicts": verdicts,
        },
        "route_type_map": route_type_map,
        "route_stats": route_stats,
        "records": records,
        "notes": notes,
        "reproducibility": reproducibility,
        "token_cost": token_cost,
        "data_quality": data_quality,
    }

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dashboard data written to: {DATA_OUT}")
    print(f"  total route-weeks: {total_rows}")
    print(f"  flagged: {justified_count + unexplained_count} (justified={justified_count}, unexplained={unexplained_count})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
