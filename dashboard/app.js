/* FreightTiger dashboard — plain HTML/CSS/JS.
 * Loads dashboard/data/dashboard_data.json produced by the Python pipeline.
 * No metrics are hardcoded; everything is derived from generated artifacts.
 */

const state = {
  data: null,
  filtered: [],
  selectedRoute: "All",
  trendRoute: null,
  sort: { key: "week_of", dir: "asc" },
  chart: null,
};

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => (n == null || Number.isNaN(n) ? "N/A" : Number(n).toFixed(d));

function verdictOf(flagged) {
  if (flagged === "No (justified)") return "Justified";
  if (flagged === "Yes") return "Unexplained";
  return "Not flagged";
}

function verdictBadge(verdict) {
  const cls =
    verdict === "Justified" ? "justified" :
    verdict === "Unexplained" ? "unexplained" : "notflagged";
  return `<span class="badge ${cls}"><span class="dot"></span>${verdict}</span>`;
}

function pctCell(pct, raw) {
  if (pct == null) return `<span class="pct-na">N/A</span>`;
  const cls = pct > 0 ? "pct-up" : "pct-down";
  const sign = pct > 0 ? "+" : "";
  return `<span class="${cls} mono" title="${raw}">${sign}${pct.toFixed(1)}%</span>`;
}

async function loadData() {
  $("data-status").textContent = "Loading…";
  try {
    const res = await fetch("data/dashboard_data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();
    $("data-status").textContent = `Data loaded · ${state.data.summary.total_route_weeks} route-weeks`;
    $("data-status").classList.add("ok");
    $("data-status").classList.remove("err");
    renderAll();
  } catch (err) {
    console.error(err);
    $("data-status").textContent = `Failed to load data: ${err.message}`;
    $("data-status").classList.add("err");
    $("data-status").classList.remove("ok");
  }
}

function renderAll() {
  renderKPIs();
  populateFilters();
  renderRouteStats();
  renderNotes();
  renderReproducibility();
  renderTokenCost();
  renderDataQuality();
  applyFilters();
}

/* ---------------- KPI cards ---------------- */
function renderKPIs() {
  const s = state.data.summary;
  const cards = [
    { label: "Route-weeks", value: s.total_route_weeks, cls: "blue", sub: `${s.total_routes} routes` },
    { label: "Flagged", value: s.flagged, cls: "rose", sub: `anomalous cost rises` },
    { label: "Justified", value: s.justified, cls: "green", sub: `with supporting note` },
    { label: "Unexplained", value: s.unexplained, cls: "amber", sub: `need human review` },
    { label: "Not flagged", value: s.not_flagged, cls: "cyan", sub: `within expected range` },
    { label: "Notes available", value: state.data.notes.length, cls: "blue", sub: `context_notes.csv` },
  ];
  $("kpi-grid").innerHTML = cards.map(c => `
    <div class="kpi ${c.cls}">
      <div class="label">${c.label}</div>
      <div class="value">${c.value.toLocaleString()}</div>
      <div class="sub">${c.sub}</div>
    </div>
  `).join("");
}

/* ---------------- Filters ---------------- */
function populateFilters() {
  const f = state.data.filters;
  fillSelect("filter-route", f.routes, state.selectedRoute);
  fillSelect("filter-route-type", f.route_types, "All");
  fillSelect("filter-week", f.weeks, "All");
}

function fillSelect(id, options, selected) {
  const el = $(id);
  el.innerHTML = options.map(o => `<option value="${o}" ${o === selected ? "selected" : ""}>${o}</option>`).join("");
}

function applyFilters() {
  const route = $("filter-route").value;
  const rtype = $("filter-route-type").value;
  const week = $("filter-week").value;
  const verdict = $("filter-verdict").value;
  const search = $("search").value.trim().toLowerCase();

  state.selectedRoute = route;

  state.filtered = state.data.records.filter(r => {
    if (route !== "All" && r.route !== route) return false;
    if (rtype !== "All" && r.route_type !== rtype) return false;
    if (week !== "All" && r.week_of !== week) return false;
    if (verdict !== "All" && verdictOf(r.flagged) !== verdict) return false;
    if (search) {
      const hay = `${r.route} ${r.matched_note_id || ""} ${r.reason || ""}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });

  sortRecords();
  renderRecordsTable();
  renderTrend();
}

function sortRecords() {
  const { key, dir } = state.sort;
  state.filtered.sort((a, b) => {
    let av = a[key], bv = b[key];
    if (key === "cost_per_tonne_km" || key === "vs_own_history_pct" || key === "vs_similar_routes_pct") {
      av = av == null ? -Infinity : av;
      bv = bv == null ? -Infinity : bv;
    }
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

/* ---------------- Trend chart ---------------- */
function renderTrend() {
  const route = state.selectedRoute !== "All" ? state.selectedRoute : (state.trendRoute || state.data.filters.routes[1]);
  state.trendRoute = route;

  const series = state.data.records
    .filter(r => r.route === route)
    .sort((a, b) => a.week_of.localeCompare(b.week_of));

  const labels = series.map(r => r.week_of);
  const cost = series.map(r => r.cost_per_tonne_km);
  const own = series.map(r => r.vs_own_history_pct);
  const peer = series.map(r => r.vs_similar_routes_pct);

  const ctx = $("trend-chart").getContext("2d");
  if (state.chart) state.chart.destroy();

  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Cost / tonne-km (INR)",
          data: cost,
          borderColor: "#22d3ee",
          backgroundColor: "rgba(34, 211, 238, 0.12)",
          yAxisID: "y",
          tension: 0.3,
          pointRadius: 2,
          borderWidth: 2,
          fill: true,
        },
        {
          label: "vs own history (%)",
          data: own,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          yAxisID: "y1",
          tension: 0.3,
          pointRadius: 1.5,
          borderWidth: 1.8,
          borderDash: [4, 3],
        },
        {
          label: "vs similar routes (%)",
          data: peer,
          borderColor: "#f43f5e",
          backgroundColor: "rgba(244, 63, 94, 0.08)",
          yAxisID: "y1",
          tension: 0.3,
          pointRadius: 1.5,
          borderWidth: 1.8,
          borderDash: [2, 2],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0f1833",
          borderColor: "#243466",
          borderWidth: 1,
          titleColor: "#e6edff",
          bodyColor: "#9fb0d4",
        },
      },
      scales: {
        x: {
          ticks: { color: "#6f81a8", maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
          grid: { color: "rgba(36, 52, 102, 0.4)" },
        },
        y: {
          position: "left",
          title: { display: true, text: "Cost / tonne-km (INR)", color: "#22d3ee" },
          ticks: { color: "#9fb0d4" },
          grid: { color: "rgba(36, 52, 102, 0.4)" },
        },
        y1: {
          position: "right",
          title: { display: true, text: "Deviation (%)", color: "#f59e0b" },
          ticks: { color: "#9fb0d4", callback: v => v + "%" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });

  $("chart-note").textContent = `Showing ${route}${state.selectedRoute === "All" ? " (change the Route filter to view another route)" : ""} — ${series.length} weekly observations.`;
}

/* ---------------- Route stats table ---------------- */
function renderRouteStats() {
  const tbody = document.querySelector("#route-stats-table tbody");
  tbody.innerHTML = state.data.route_stats.map(r => `
    <tr data-route="${r.route}">
      <td><strong>${r.route}</strong></td>
      <td>${r.route_type}</td>
      <td class="mono">${r.weeks}</td>
      <td class="mono">${r.flagged}</td>
      <td class="mono" style="color:var(--green)">${r.justified}</td>
      <td class="mono" style="color:var(--amber)">${r.unexplained}</td>
      <td class="mono">${fmt(r.avg_cost)}</td>
      <td class="mono">${fmt(r.min_cost)}</td>
      <td class="mono">${fmt(r.max_cost)}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", () => {
      const route = tr.dataset.route;
      state.trendRoute = route;
      $("filter-route").value = route;
      applyFilters();
    });
  });
}

/* ---------------- Records table ---------------- */
function renderRecordsTable() {
  const tbody = document.querySelector("#records-table tbody");
  $("records-count").textContent = `${state.filtered.length} of ${state.data.records.length} records`;

  const rows = state.filtered.slice(0, 500);
  tbody.innerHTML = rows.map(r => {
    const verdict = verdictOf(r.flagged);
    return `
      <tr data-route="${r.route}" data-week="${r.week_of}">
        <td><strong>${r.route}</strong></td>
        <td>${r.route_type || ""}</td>
        <td class="mono">${r.week_of}</td>
        <td class="mono">${fmt(r.cost_per_tonne_km)}</td>
        <td>${pctCell(r.vs_own_history_pct, r.vs_own_history)}</td>
        <td>${pctCell(r.vs_similar_routes_pct, r.vs_similar_routes)}</td>
        <td>${verdictBadge(verdict)}</td>
        <td class="mono">${r.matched_note_id || ""}</td>
        <td class="reason">${r.reason || ""}</td>
      </tr>
    `;
  }).join("");

  if (state.filtered.length > rows.length) {
    tbody.innerHTML += `<tr><td colspan="9" style="text-align:center;color:var(--text-faint);padding:12px;">Showing first ${rows.length} of ${state.filtered.length} — use filters to narrow down.</td></tr>`;
  }

  tbody.querySelectorAll("tr[data-route]").forEach(tr => {
    tr.addEventListener("click", () => showEvidence(tr.dataset.route, tr.dataset.week));
  });
}

/* ---------------- Evidence panel ---------------- */
function showEvidence(route, week) {
  document.querySelectorAll("#records-table tbody tr").forEach(tr => tr.classList.remove("selected"));
  const row = document.querySelector(`#records-table tr[data-route="${route}"][data-week="${week}"]`);
  if (row) row.classList.add("selected");

  const rec = state.data.records.find(r => r.route === route && r.week_of === week);
  if (!rec) return;

  const verdict = verdictOf(rec.flagged);
  const note = rec.matched_note_id
    ? state.data.notes.find(n => n.note_id === rec.matched_note_id)
    : null;

  const html = `
    <div class="evidence-field">
      <span class="k">Route</span>
      <span class="v"><strong>${rec.route}</strong> <span style="color:var(--text-faint)">(${rec.route_type})</span></span>
    </div>
    <div class="evidence-field">
      <span class="k">Week</span>
      <span class="v mono">${rec.week_of}</span>
    </div>
    <div class="evidence-field">
      <span class="k">Cost / tonne-km</span>
      <span class="v mono">${fmt(rec.cost_per_tonne_km)} INR</span>
    </div>
    <div class="evidence-field">
      <span class="k">vs own history</span>
      <span class="v">${pctCell(rec.vs_own_history_pct, rec.vs_own_history)}</span>
    </div>
    <div class="evidence-field">
      <span class="k">vs similar routes</span>
      <span class="v">${pctCell(rec.vs_similar_routes_pct, rec.vs_similar_routes)}</span>
    </div>
    <div class="evidence-field">
      <span class="k">Verdict</span>
      <span class="v">${verdictBadge(verdict)}</span>
    </div>
    ${note ? `
      <div class="evidence-field">
        <span class="k">Matched note</span>
        <div class="note-card">
          <div class="note-head">
            <span class="note-id">${note.note_id}</span>
            <span class="note-date">${note.date}</span>
          </div>
          <div class="note-text">${note.note}</div>
        </div>
      </div>
    ` : ""}
    <div class="evidence-field">
      <span class="k">Explanation</span>
      <div class="v" style="color:var(--text-dim);font-size:13px;line-height:1.55;">${rec.reason || ""}</div>
    </div>
  `;
  $("evidence-body").innerHTML = html;
}

/* ---------------- Notes list ---------------- */
function renderNotes() {
  $("notes-list").innerHTML = state.data.notes.map(n => `
    <div class="note-card">
      <div class="note-head">
        <span class="note-id">${n.note_id}</span>
        <span class="note-date">${n.date} · ${n.applies_to}</span>
      </div>
      <div class="note-text">${n.note}</div>
    </div>
  `).join("");
}

/* ---------------- Reports ---------------- */
function renderReproducibility() {
  const r = state.data.reproducibility;
  if (!r) {
    $("reproducibility-body").innerHTML = `<p class="empty">No reproducibility report found.</p>`;
    return;
  }
  const runs = r.runs.map((run, i) => `
    <div class="report-item">
      <div class="k">Run ${i + 1}</div>
      <div class="v">${run.rows} rows</div>
      <div style="font-size:11px;color:var(--text-faint);margin-top:4px;">flagged ${run.flagged} · justified ${run.justified} · unexplained ${run.unexplained}</div>
    </div>
  `).join("");

  $("reproducibility-body").innerHTML = `
    <div class="report-grid">
      <div class="report-item">
        <div class="k">Byte-identical outputs</div>
        <div class="v" style="color:${r.byte_identical ? "var(--green)" : "var(--rose)"}">${r.byte_identical ? "Yes" : "No"}</div>
      </div>
      <div class="report-item">
        <div class="k">Deterministic match</div>
        <div class="v" style="color:${r.deterministic_match ? "var(--green)" : "var(--rose)"}">${r.deterministic_match ? "Yes" : "No"}</div>
      </div>
      ${runs}
    </div>
    ${r.sha256 ? `<div class="evidence-field" style="margin-top:12px;">
      <span class="k">SHA-256 (all runs)</span>
      <span class="v mono" style="font-size:11px;word-break:break-all;">${r.sha256}</span>
    </div>` : ""}
    <pre class="report-pre" style="margin-top:12px;">${r.report_text}</pre>
  `;
}

function renderTokenCost() {
  const t = state.data.token_cost;
  if (!t) {
    $("token-cost-body").innerHTML = `<p class="empty">No token/cost report found.</p>`;
    return;
  }
  $("token-cost-body").innerHTML = `
    <div class="report-grid">
      <div class="report-item"><div class="k">LLM used</div><div class="v">${t.llm_used ? "Yes" : "No"}</div></div>
      <div class="report-item"><div class="k">Provider / model</div><div class="v">${t.provider} / ${t.model}</div></div>
      <div class="report-item"><div class="k">LLM calls</div><div class="v">${t.llm_calls}</div></div>
      <div class="report-item"><div class="k">Input tokens</div><div class="v">${t.input_tokens.toLocaleString()}</div></div>
      <div class="report-item"><div class="k">Output tokens</div><div class="v">${t.output_tokens.toLocaleString()}</div></div>
      <div class="report-item"><div class="k">Total cost (USD)</div><div class="v">$${fmt(t.total_cost_usd, 4)}</div></div>
    </div>
    ${t.note ? `<p style="color:var(--text-dim);font-size:12px;margin:12px 0 0;">${t.note}</p>` : ""}
  `;
}

function renderDataQuality() {
  const q = state.data.data_quality;
  if (!q) {
    $("data-quality-body").innerHTML = `<p class="empty">No data quality report found.</p>`;
    return;
  }
  const invalid = Array.isArray(q.invalid_records) ? q.invalid_records.length : 0;
  $("data-quality-body").innerHTML = `
    <div class="report-grid">
      <div class="report-item"><div class="k">Total records</div><div class="v">${q.total_records}</div></div>
      <div class="report-item"><div class="k">Dropped (invalid)</div><div class="v" style="color:${q.dropped_count ? "var(--rose)" : "var(--green)"}">${q.dropped_count}</div></div>
      <div class="report-item"><div class="k">Invalid detail rows</div><div class="v">${invalid}</div></div>
    </div>
  `;
}

/* ---------------- CSV download ---------------- */
async function downloadCSV() {
  try {
    const res = await fetch("../outputs/final_output.csv", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "final_output.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Could not download final_output.csv: ${err.message}\n\nThe file is available at outputs/final_output.csv`);
  }
}

/* ---------------- Sorting ---------------- */
function attachSortHandlers() {
  document.querySelectorAll("#records-table thead th").forEach(th => {
    th.addEventListener("click", () => {
      const keyMap = {
        "Route": "route",
        "Type": "route_type",
        "Week": "week_of",
        "Cost / t-km": "cost_per_tonne_km",
        "vs own history": "vs_own_history_pct",
        "vs similar routes": "vs_similar_routes_pct",
        "Verdict": "flagged",
        "Note ID": "matched_note_id",
      };
      const key = keyMap[th.textContent.trim()];
      if (!key) return;
      if (state.sort.key === key) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = { key, dir: "asc" };
      }
      sortRecords();
      renderRecordsTable();
    });
  });
}

/* ---------------- Init ---------------- */
function init() {
  $("refresh-btn").addEventListener("click", loadData);
  $("download-csv-btn").addEventListener("click", downloadCSV);
  $("reset-filters").addEventListener("click", () => {
    $("filter-route").value = "All";
    $("filter-route-type").value = "All";
    $("filter-week").value = "All";
    $("filter-verdict").value = "All";
    $("search").value = "";
    state.trendRoute = state.data.filters.routes[1];
    applyFilters();
  });

  ["filter-route", "filter-route-type", "filter-week", "filter-verdict"].forEach(id => {
    $(id).addEventListener("change", applyFilters);
  });
  $("search").addEventListener("input", applyFilters);

  attachSortHandlers();
  loadData();
}

document.addEventListener("DOMContentLoaded", init);
