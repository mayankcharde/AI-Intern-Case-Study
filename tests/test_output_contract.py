"""Tests for output CSV contract validation."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from src.config import (
    FINAL_OUTPUT_FILE,
    OUTPUT_COLUMNS,
    SAMPLE_OUTPUT_FILE,
)
from src.output_writer import validate_output_schema, write_final_output
from src.pipeline import run_pipeline


def test_sample_header_columns():
    with open(SAMPLE_OUTPUT_FILE, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    expected = header.split(",")
    assert expected == OUTPUT_COLUMNS


def test_output_has_exact_columns_and_order(tmp_path):
    df = pd.DataFrame({
        "route": ["R1"],
        "week_of": ["2024-01-01"],
        "cost_per_tonne_km": [1.23],
        "vs_own_history": ["+5.0% vs this route's past average"],
        "vs_similar_routes": ["+3.0% vs similar-length routes this week"],
        "flagged": ["No"],
        "matched_note_id": [""],
        "reason": ["Not flagged."],
        "extra": ["should be dropped"],
    })
    out = tmp_path / "out.csv"
    write_final_output(df, str(out))
    written = pd.read_csv(out)
    assert list(written.columns) == OUTPUT_COLUMNS
    assert "extra" not in written.columns


def test_no_extra_index_column(tmp_path):
    df = pd.DataFrame({
        "route": ["R1"],
        "week_of": ["2024-01-01"],
        "cost_per_tonne_km": [1.23],
        "vs_own_history": ["+5.0% vs this route's past average"],
        "vs_similar_routes": ["+3.0% vs similar-length routes this week"],
        "flagged": ["No"],
        "matched_note_id": [""],
        "reason": ["Not flagged."],
    })
    out = tmp_path / "out.csv"
    write_final_output(df, str(out))
    with open(out, "r") as f:
        first_line = f.readline().strip()
    cols = first_line.split(",")
    assert cols[0] == "route"
    assert "Unnamed" not in cols[0]


def test_final_output_schema_matches_sample():
    with open(FINAL_OUTPUT_FILE, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    assert header.split(",") == OUTPUT_COLUMNS


def test_final_output_exists():
    assert os.path.exists(FINAL_OUTPUT_FILE)


def test_cited_note_ids_are_real():
    from src.data_loader import load_notes
    notes = load_notes(r"data/context_notes.csv")
    valid_ids = set(notes["note_id"].tolist())
    df = pd.read_csv(FINAL_OUTPUT_FILE)
    cited = set(df["matched_note_id"].dropna().astype(str)) - {""}
    assert cited.issubset(valid_ids), f"Invalid note IDs: {cited - valid_ids}"


def test_unexplained_have_blank_note_id():
    df = pd.read_csv(FINAL_OUTPUT_FILE)
    unexplained = df[df["flagged"] == "Yes"]
    assert (unexplained["matched_note_id"].fillna("") == "").all()


def test_justified_have_note_id():
    df = pd.read_csv(FINAL_OUTPUT_FILE)
    justified = df[df["flagged"] == "No (justified)"]
    assert (justified["matched_note_id"].fillna("") != "").all()


def test_stable_sorting():
    df = pd.read_csv(FINAL_OUTPUT_FILE)
    sorted_df = df.sort_values(["route", "week_of"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(df.reset_index(drop=True), sorted_df)
