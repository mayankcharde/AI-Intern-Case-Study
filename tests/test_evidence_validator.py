"""Tests for note retrieval and evidence validation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.evidence_validator import (
    select_best_note,
    validate_note,
    _extract_impact_pct,
)
from src.note_retriever import retrieve_candidate_notes


@pytest.fixture
def notes():
    return pd.DataFrame([
        {"note_id": "N001", "date": pd.Timestamp("2025-02-24"),
         "applies_to": "Chennai-Bangalore",
         "note": "Heavy flooding from Feb 24 to Mar 8 forced longer detours and higher trip costs."},
        {"note_id": "N002", "date": pd.Timestamp("2025-01-20"),
         "applies_to": "Ahmedabad-Mumbai",
         "note": "A regional festival week saw a temporary surcharge applied by transporters."},
        {"note_id": "N003", "date": pd.Timestamp("2025-05-05"),
         "applies_to": "All Routes",
         "note": "Diesel prices rose nationwide, pushing up transportation costs by roughly 5-7%."},
        {"note_id": "N004", "date": pd.Timestamp("2024-03-11"),
         "applies_to": "All Routes",
         "note": "A new toll plaza was commissioned, but the affected routes are not part of this dataset."},
        {"note_id": "N005", "date": pd.Timestamp("2024-07-29"),
         "applies_to": "Mumbai-Delhi",
         "note": "Scheduled maintenance caused minor delays; costs were not significantly affected."},
        {"note_id": "N006", "date": pd.Timestamp("2025-09-22"),
         "applies_to": "All Routes",
         "note": "A logistics report noted demand remained stable with no major disruptions reported."},
        {"note_id": "N007", "date": pd.Timestamp("2024-05-20"),
         "applies_to": "Delhi-Jaipur",
         "note": "Local authorities announced improved road conditions after resurfacing work."},
        {"note_id": "N008", "date": pd.Timestamp("2025-06-09"),
         "applies_to": "Kolkata-Bhubaneswar",
         "note": "No significant disruptions were reported; freight movement remained normal."},
        {"note_id": "N009", "date": pd.Timestamp("2025-03-17"),
         "applies_to": "Chennai-Bangalore",
         "note": "Highway authorities confirmed the route returned to normal conditions after flood repairs."},
    ])


def test_route_specific_note_matches_date(notes):
    cands = retrieve_candidate_notes(notes, "Chennai-Bangalore", "2025-02-24")
    assert len(cands) >= 1
    nids = cands["note_id"].tolist()
    assert "N001" in nids


def test_route_specific_note_outside_time_window(notes):
    cands = retrieve_candidate_notes(notes, "Chennai-Bangalore", "2024-06-01")
    nids = cands["note_id"].tolist()
    assert "N001" not in nids


def test_broad_note_applies_to_all_routes(notes):
    cands = retrieve_candidate_notes(notes, "Mumbai-Pune", "2025-05-05")
    nids = cands["note_id"].tolist()
    assert "N003" in nids


def test_note_explicitly_excluding_route(notes):
    n = notes[notes["note_id"] == "N004"].iloc[0]
    ok, reason = validate_note(n, "Mumbai-Pune", "2024-03-11", 20.0, 20.0)
    assert ok is False


def test_note_stating_costs_not_affected(notes):
    n = notes[notes["note_id"] == "N005"].iloc[0]
    ok, reason = validate_note(n, "Mumbai-Delhi", "2024-07-29", 20.0, 20.0)
    assert ok is False


def test_note_with_contradictory_impact(notes):
    n = notes[notes["note_id"] == "N003"].iloc[0]
    ok, reason = validate_note(n, "Mumbai-Pune", "2025-05-05", 50.0, 50.0)
    assert ok is False
    assert "smaller" in reason


def test_note_with_sufficient_impact(notes):
    n = notes[notes["note_id"] == "N003"].iloc[0]
    ok, reason = validate_note(n, "Mumbai-Pune", "2025-05-05", 8.0, 8.0)
    assert ok is True


def test_flagged_route_with_no_matching_note(notes):
    cands = retrieve_candidate_notes(notes, "Delhi-Jaipur", "2024-11-11")
    best, reason = select_best_note(cands, "Delhi-Jaipur", "2024-11-11", 35.0, 21.0)
    assert best is None


def test_semantically_similar_but_wrong_route(notes):
    cands = retrieve_candidate_notes(notes, "Mumbai-Pune", "2025-02-24")
    nids = cands["note_id"].tolist()
    assert "N001" not in nids


def test_note_returned_to_normal_not_justifying(notes):
    cands = retrieve_candidate_notes(notes, "Chennai-Bangalore", "2025-03-17")
    nids = cands["note_id"].tolist()
    assert "N009" in nids
    n = notes[notes["note_id"] == "N009"].iloc[0]
    ok, _ = validate_note(n, "Chennai-Bangalore", "2025-03-17", 20.0, 20.0)
    assert ok is False


def test_extract_impact_pct_range():
    text = "pushing up costs by roughly 5-7%"
    assert abs(_extract_impact_pct(text) - 6.0) < 1e-9


def test_extract_impact_pct_single():
    text = "costs rose by 10%"
    assert abs(_extract_impact_pct(text) - 10.0) < 1e-9


def test_extract_impact_pct_none():
    text = "no percentage mentioned here"
    assert _extract_impact_pct(text) is None


def test_invalid_or_nonexistent_note_id():
    empty = pd.DataFrame(columns=["note_id", "date", "applies_to", "note"])
    best, reason = select_best_note(empty, "R1", "2024-01-01", 20.0, 20.0)
    assert best is None
