"""Reproducibility check: run the pipeline three times and compare outputs.

Writes run_1.csv, run_2.csv, run_3.csv to outputs/ and a human-readable
reproducibility_report.txt. Exits nonzero if any deterministic field differs.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OUTPUT_DIR, REPORTS_DIR
from src.pipeline import run_pipeline

NUMERIC_TOL = 1e-6
DETERMINISTIC_COLUMNS = [
    "route",
    "week_of",
    "cost_per_tonne_km",
    "vs_own_history",
    "vs_similar_routes",
    "flagged",
    "matched_note_id",
]


def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    paths = []
    summaries = []
    for i in range(1, 4):
        out_path = OUTPUT_DIR / f"run_{i}.csv"
        summary = run_pipeline(output_path=str(out_path))
        paths.append(out_path)
        summaries.append(summary)
        print(f"Run {i}: {summary['output_rows']} rows -> {out_path}")

    frames = [pd.read_csv(p) for p in paths]
    hashes = [file_hash(str(p)) for p in paths]

    identical_bytes = len(set(hashes)) == 1

    report_lines = []
    report_lines.append("FREIGHTTIGER REPRODUCIBILITY REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Number of runs: 3")
    report_lines.append("")

    for i, (p, h, s) in enumerate(zip(paths, hashes, summaries), 1):
        report_lines.append(f"Run {i}: {p}")
        report_lines.append(f"  SHA-256: {h}")
        report_lines.append(f"  rows: {s['output_rows']}, flagged: {s['flagged_routes']}, "
                            f"justified: {s['justified_routes']}, unexplained: {s['unexplained_routes']}")
    report_lines.append("")

    report_lines.append(f"Byte-identical outputs: {identical_bytes}")

    all_match = True
    if not identical_bytes:
        report_lines.append("")
        report_lines.append("DETERMINISTIC FIELD COMPARISON")
        report_lines.append("-" * 60)
        base = frames[0]
        for i in range(1, 3):
            other = frames[i]
            for col in DETERMINISTIC_COLUMNS:
                if col not in base.columns or col not in other.columns:
                    report_lines.append(f"  Run 1 vs Run {i+1}: column {col} missing")
                    all_match = False
                    continue
                if pd.api.types.is_numeric_dtype(base[col]):
                    diff = (base[col].fillna(-999) - other[col].fillna(-999)).abs()
                    mismatches = (diff > NUMERIC_TOL).sum()
                else:
                    mismatches = (base[col].fillna("") != other[col].fillna("")).sum()
                if mismatches > 0:
                    report_lines.append(f"  Run 1 vs Run {i+1}, col '{col}': {mismatches} mismatches")
                    all_match = False
        if all_match:
            report_lines.append("  All deterministic fields match across runs.")
    else:
        report_lines.append("  All deterministic fields match (files are byte-identical).")

    report_lines.append("")
    report_lines.append(f"Overall deterministic match: {all_match or identical_bytes}")

    report_text = "\n".join(report_lines)
    report_path = REPORTS_DIR / "reproducibility_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print()
    print(report_text)
    print(f"\nReport written to: {report_path}")

    return 0 if (all_match or identical_bytes) else 1


if __name__ == "__main__":
    sys.exit(main())
