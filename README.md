# FreightTiger — Smart Shipping Cost Monitoring Assistant

A production-quality, evidence-grounded assistant that watches transportation
costs per route, flags unusual weekly increases against history and peers, and
explains each flag using supplied contextual notes — without inventing causes.

---

## 1. Project Overview

FreightTiger ingests shipment records, computes a weekly
**cost per tonne-kilometre** for every route, compares each week against:

- the route's own trailing historical average (up to the prior 8 weeks), and
- the same-week average of all other routes of the same `route_type` (Short /
  Medium / Long),

flags route-weeks whose increase crosses a configurable threshold, and then
checks the supplied `context_notes.csv` to see whether a real-world event
(fuel, toll, weather, festival, etc.) credibly explains the rise.

Every "justified" verdict cites an exact note ID that applies to the route and
overlaps the shipment week. Routes with no sufficient supporting note are
marked **unexplained** and left for human review.

---

## 2. Business Problem

Transportation costs can creep up on specific routes over time — sometimes for
a legitimate reason (fuel price, toll, monsoon disruption, festival surcharge)
and sometimes for no good reason. The assistant surfaces cost increases that
look out of the ordinary and backs each explanation with verifiable evidence
from the notes file, so that a human reviewer can trust the verdict.

---

## 3. Architecture & Workflow

```
shipment_records.csv  ──►  data_loader  ──►  data_validation
                                                    │
                                                    ▼
                                          weekly_aggregation
                                          (Mon–Sun weeks, cost/tonne-km)
                                                    │
                                                    ▼
                                          baseline_calculator
                                          (vs own history · vs similar routes)
                                                    │
                                                    ▼
                                          anomaly_detector
                                          (configurable thresholds)
                                                    │
                                                    ▼
                              note_retriever ◄── context_notes.csv
                                                    │
                                                    ▼
                                          evidence_validator
                                          (route · date · impact · exclusions)
                                                    │
                                                    ▼
                                          explanation_generator
                                          (deterministic, evidence-grounded)
                                                    │
                                                    ▼
                                          output_writer
                                          (outputs/final_output.csv)
```

All numerical stages are independent of any LLM. Explanations are produced by
deterministic templates that only reference validated evidence.

---

## 4. Technology Stack

- **Python 3.11+** (developed on 3.12)
- **pandas** — CSV ingestion, weekly aggregation, numerical operations
- **numpy** — numerical precision
- **pytest** — automated test suite (45 tests)
- **scikit-learn** — available (not required for the core pipeline)
- **No LLM** — all explanations are deterministic templates grounded in
  validated notes. Token/cost report is zero by construction.

---

## 5. Input Files

| File | Purpose |
|------|---------|
| `data/shipment_records.csv` | 2,940 shipment records (origin, destination, route_type, material, quantity_tonnes, distance_km, freight_cost_inr, shipment_date, transporter) |
| `data/context_notes.csv` | 10 contextual notes (note_id, date, applies_to, note) |
| `data/sample_output_format_v2.csv` | Output schema contract |

### 5.1 Route identification

Routes are grouped by the exact combination `origin`, `destination`,
`route_type` (Short / Medium / Long). `route_type` is taken as-is from the
data; it is **not** derived from distance.

---

## 6. Mathematical Formulas

### 6.1 Cost per tonne-kilometre (weekly, per route)

```
cost_per_tonne_km = Σ freight_cost_inr  /  Σ (quantity_tonnes × distance_km)
```

The ratio is computed **after** aggregating the week's shipments (a weighted
average by tonne-km), never as an unweighted average of per-shipment ratios.
Records with non-positive quantity or distance, or non-numeric cost, are
dropped and recorded in the data-quality report.

### 6.2 Weekly grouping

Weeks run **Monday through Sunday**. `week_of` is that week's Monday date in
`YYYY-MM-DD` format. Shipments are grouped into these weeks before any cost is
computed.

### 6.3 vs. own history

For each (route, week), take the route's **trailing 8 prior weekly
observations** (strictly before the current week). If fewer than 8 exist, use
all available prior observations. Never pad, extrapolate, or include the
current week.

```
vs_own_history = ((current_cost − historical_average) / historical_average) × 100
```

If no prior observation exists, or the historical average is zero/invalid, the
comparison is **unavailable** (`N/A` in the output).

### 6.4 vs. similar routes

For each (route, week), take the same-week cost per tonne-km of **all other
routes sharing the same `route_type`**, excluding the current route and any
invalid peer costs.

```
vs_similar_routes = ((current_cost − peer_average) / peer_average) × 100
```

If no valid peer average exists, the comparison is **unavailable** (`N/A`).

---

## 7. Anomaly Detection

A route-week is **flagged** if at least one **valid** comparison crosses its
configured threshold. An unavailable baseline is **not** treated as an anomaly.

| Comparison | Default threshold | Configurable in `src/config.py` |
|------------|-------------------|---------------------------------|
| vs. own history | **+15%** | `HISTORICAL_ANOMALY_THRESHOLD_PCT` |
| vs. similar routes | **+15%** | `PEER_ANOMALY_THRESHOLD_PCT` |

> **Engineering assumption (not a FreightTiger requirement):** both thresholds
> default to **15%**. The case study does not specify an exact numerical
> threshold. The flagging policy is deterministic and independently testable.

Edge cases handled: negative changes (not flagged), missing baselines (not
treated as anomaly), zero denominators (unavailable), first observations for a
route (no history → unavailable), tied/repeated values, routes with no
comparable peers.

---

## 8. Note Retrieval & Evidence Validation

### 8.1 Retrieval (`src/note_retriever.py`)

A note is a **candidate** for a (route, week) if:

1. `applies_to` equals the route **or** is `All Routes`.
2. The note's event date (or an explicit date range parsed from the note text,
   or the note date ± 14 days) **overlaps** the shipment week (Mon–Sun).

### 8.2 Evidence validation (`src/evidence_validator.py`)

A candidate note can justify an increase **only if all** of the following hold:

- It does **not** explicitly exclude the route (e.g. "affected routes are not
  part of this dataset").
- It does **not** state costs were unaffected / not significantly affected /
  conditions returned to normal / demand stable / no major disruptions.
- It describes an event capable of increasing costs (fuel, toll, flood,
  surcharge, detour, limited capacity, etc.).
- Any stated impact percentage is consistent with the observed increase. If the
  note says ~5–7% but the observed rise is much larger, the note is rejected
  (it cannot credibly explain the increase).

Semantic similarity alone never justifies an increase.

### 8.3 Verdicts

| Verdict | Output `flagged` | Meaning |
|---------|------------------|---------|
| `NOT_FLAGGED` | `No` | Cost within expected range |
| `JUSTIFIED` | `No (justified)` | Anomaly explained by a valid, applicable, time-relevant note |
| `UNEXPLAINED` | `Yes` | Anomaly with no sufficient supporting note |

---

## 9. Output CSV Contract

File: `outputs/final_output.csv`. Exact columns and order:

```
route, week_of, cost_per_tonne_km, vs_own_history, vs_similar_routes, flagged, matched_note_id, reason
```

- `route` — `origin-destination` (e.g. `Mumbai-Pune`)
- `week_of` — Monday of the shipment week, `YYYY-MM-DD`
- `cost_per_tonne_km` — numeric, rounded to 2 decimals
- `vs_own_history` — `+X.X% vs this route's past average` (or `N/A`)
- `vs_similar_routes` — `+X.X% vs similar-length routes this week` (or `N/A`)
- `flagged` — `Yes` | `No (justified)` | `No`
- `matched_note_id` — note ID when justified, otherwise **blank**
- `reason` — deterministic, evidence-grounded explanation

Rows are sorted deterministically by `route`, then `week_of`. No index column,
no extra fields.

---

## 10. Missing-Data Handling

| Situation | Behaviour |
|-----------|-----------|
| Shipment with non-positive quantity/distance | Dropped; recorded in data-quality report |
| Shipment with negative/missing cost | Dropped; recorded |
| Unparseable date | Dropped; recorded |
| No prior weekly observation for a route | `vs_own_history = N/A` |
| Historical average is zero | `vs_own_history = N/A` |
| No peer routes of same type in a week | `vs_similar_routes = N/A` |
| Peer average is zero | `vs_similar_routes = N/A` |
| Unavailable comparison | **Not** treated as an anomaly |
| Flagged route, no valid note | `flagged = Yes`, `matched_note_id = ""` |

---

## 11. Installation

```bash
# from the repository root
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 12. Execution

### Run the pipeline

```bash
python -m src.pipeline
# or
python scripts/run_pipeline.py
```

Produces `outputs/final_output.csv`, `reports/data_quality_report.json`,
`reports/token_cost_log.json`.

### Run the reproducibility check (3 runs)

```bash
python scripts/run_reproducibility_check.py
```

Runs the pipeline 3 times, writes `outputs/run_{1,2,3}.csv`, and produces
`reports/reproducibility_report.txt`. Exits nonzero if any deterministic field
differs.

### Run the test suite

```bash
python -m pytest tests/ -v
```

### Dashboard (HTML / CSS / JS)

The dashboard is a static, no-build frontend in `dashboard/`. It reads a JSON
snapshot generated from the pipeline's real artifacts — nothing is hardcoded.

**1. Generate the dashboard data snapshot** (reads `outputs/final_output.csv`,
`context_notes.csv`, and `reports/*`):

```bash
python scripts/prepare_dashboard_data.py
```

**2. Serve the dashboard** (any static server works; Python's built-in server is
fine). Run this from the **repository root** so the dashboard can also fetch
`outputs/final_output.csv` for the CSV download button:

```bash
python -m http.server 8765
```

Then open **http://localhost:8765/dashboard/index.html** in a browser.

> The dashboard requires no npm install, no build step, and no API server.
> Chart.js is loaded from a CDN. If you prefer, you can also open
> `dashboard/index.html` directly from disk, but the CSV download and
> `fetch()` of `dashboard_data.json` need to be served over HTTP (browsers
> block `file://` fetches).

### Quick reference — all run commands

```bash
# ---- Python pipeline ----
python -m src.pipeline                       # run pipeline -> outputs/final_output.csv
python scripts/run_pipeline.py               # same, via script
python scripts/run_reproducibility_check.py  # 3 runs + diff -> reports/reproducibility_report.txt
python -m pytest tests/ -v                   # test suite (45 tests)

# ---- Dashboard ----
python scripts/prepare_dashboard_data.py     # regenerate dashboard/data/dashboard_data.json
python -m http.server 8765                   # serve, then open http://localhost:8765/dashboard/index.html
```

---

## 13. Dashboard Overview

A responsive analytics dashboard built with plain **HTML, CSS, and JavaScript**
(no framework, no build step). It visualizes the actual pipeline output and is
purely supplementary — the case-study deliverables remain runnable without it.

### Features

- **KPI cards** — total route-weeks, routes, flagged, justified, unexplained,
  not-flagged, and number of context notes (all computed from the generated
  output).
- **Filters** — by route, route type (Short / Medium / Long), week, verdict,
  and free-text search (route / note ID / reason).
- **Weekly cost trend chart** — cost-per-tonne-km overlaid with `vs own history`
  and `vs similar routes` percentages (dual y-axis). Changes route when you
  select a route filter or click a row in the route-stats table.
- **Route statistics table** — per-route weeks, flagged/justified/unexplained
  counts, and min / avg / max cost.
- **Records & anomaly verdicts table** — sortable, with color-coded percentage
  deviations and verdict badges. Clicking a row opens the evidence panel.
- **Route evidence panel** — shows the matched note (ID, date, full text) and
  the evidence-grounded explanation for the selected record.
- **Context notes list** — all supplied notes from `context_notes.csv`.
- **Reports panels** — reproducibility (byte-identical check, SHA-256, per-run
  counts), token & cost (LLM calls, tokens, USD), and data quality (total /
  dropped records). These render only when the corresponding report file
  exists.
- **CSV download** — downloads the actual `outputs/final_output.csv`.

### Data flow

```
outputs/final_output.csv  ─┐
data/context_notes.csv    ─┼─► scripts/prepare_dashboard_data.py ─► dashboard/data/dashboard_data.json ─► dashboard (fetch)
reports/*.json|txt        ─┘
```

Regenerate the snapshot whenever the pipeline output changes by re-running
`python scripts/prepare_dashboard_data.py`.

---

## 14. Actual Evaluation Results

### Pipeline run on the full dataset

| Metric | Value |
|--------|-------|
| Input shipment records | 2,940 |
| Valid records | 2,940 |
| Dropped records | 0 |
| Output rows (route-weeks) | 728 |
| Flagged route-weeks | 27 |
| Justified | 5 |
| Unexplained | 22 |
| Not flagged | 701 |

**Justified route-weeks:**

| Route | Week | Note |
|-------|------|------|
| Ahmedabad-Mumbai | 2025-01-20 | N002 (festival surcharge) |
| Chennai-Bangalore | 2025-02-24 | N001 (flooding, detours) |
| Chennai-Bangalore | 2025-03-03 | N001 |
| Chennai-Bangalore | 2025-03-10 | N001 |
| Chennai-Bangalore | 2025-03-17 | N001 |

The three illustrative rows in `sample_output_format_v2.csv` reproduce
exactly (Delhi-Jaipur 2024-11-11, Ahmedabad-Mumbai 2025-01-20, Mumbai-Pune
2025-09-15).

### Test suite

```
45 passed in ~2s
```

Covers: cost-per-tonne-km correctness, Monday-based week assignment, weekly
aggregation, unweighted-vs-weighted ratio, 8-week historical window,
fewer-than-8 observations, peer exclusion, peer grouping by route type,
missing baselines, zero denominators, negative changes, threshold behaviour,
note route/date matching, route exclusion, "costs not affected" rejection,
insufficient-impact rejection, wrong-route semantic similarity, output schema,
no index column, blank note IDs for unexplained, real note IDs for justified,
stable sorting.

### Reproducibility (3 runs)

```
Byte-identical outputs: True
SHA-256 (all three runs): 50c4cb536842fee59857a842b5b31645f6c74a2030f37e7d46badc4e19e13f35
Rows: 728 each · Flagged: 27 each · Justified: 5 each · Unexplained: 22 each
Overall deterministic match: True
```

See `reports/reproducibility_report.txt`.

### Token & cost report

See `reports/token_cost_log.json`. **No LLM is used.** All explanations are
generated by deterministic, evidence-grounded templates.

| Field | Value |
|-------|-------|
| LLM calls | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total estimated LLM cost | $0.00 |

---

## 15. Final Output Schema

```
route,week_of,cost_per_tonne_km,vs_own_history,vs_similar_routes,flagged,matched_note_id,reason
```

Verified programmatically against `data/sample_output_format_v2.csv` (column
names **and** order).

---

## 16. Limitations & Trade-offs

1. **Anomaly threshold is an assumption.** FreightTiger did not specify an
   exact percentage. The default is 15% for both comparisons; it is
   configurable and documented.
2. **No LLM.** Deterministic templates were chosen for perfect reproducibility
   and zero cost. The trade-off is that explanation wording is less varied
   than an LLM would produce, but every explanation is strictly grounded in
   validated evidence — which is the guardrail the case study emphasises.
3. **Event-impact window of ±14 days** is an engineering assumption for
   one-off events. Ongoing events (e.g. a permanent fuel price rise) are
   still bounded by the note's stated impact percentage.
4. **Impact-consistency check:** if a note states a ~5–7% impact but the
   observed rise is much larger, the note is rejected. This is conservative;
   it may leave some increases unexplained that a human would partially
   attribute to the note.
5. The supplied `sample_output_format_v2.csv` contains unquoted commas inside
   the `reason` field, so it cannot be parsed as a strict CSV. The schema
   validation reads only the header line.

---

## 17. Engineering Assumptions (not specified by FreightTiger)

- Anomaly thresholds: 15% for both `vs_own_history` and `vs_similar_routes`.
- Event-impact window: note date ± 14 days (or explicit date range in text).
- Impact-consistency tolerance: a note's stated impact must be within 1.5× of
  the observed increase to justify it.
- Unavailable comparisons render as `N/A` in the formatted `vs_*` columns.
- `flagged` mapping: `NOT_FLAGGED → No`, `JUSTIFIED → No (justified)`,
  `UNEXPLAINED → Yes`.

---

## 18. GitHub Submission Checklist

- [x] All source code in `src/`
- [x] Test suite in `tests/` (45 passing)
- [x] Scripts in `scripts/` (run pipeline, reproducibility check)
- [x] `requirements.txt`
- [x] `.gitignore` (venv, caches, `.env`, secrets)
- [x] `outputs/final_output.csv`
- [x] `reports/data_quality_report.json`
- [x] `reports/token_cost_log.json`
- [x] `reports/reproducibility_report.txt`
- [x] `README.md`
- [ ] Push to GitHub (not performed — no fabrications)
