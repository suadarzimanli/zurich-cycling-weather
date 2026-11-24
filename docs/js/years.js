// "Rain over the years": yearly effects for cycling, walking and cars, and the test table.
import { css, makeTable, signed } from "./util.js";
import { band, ciLines, crosshair, endLabels, gridColor, htmlTooltip, yearAxis } from "./charts.js";

/* global Chart */

const charts = {};
let E;

function series(rows, color, label, pointStyle, endLabel) {
  return {
    label, endLabel, data: rows.map((r) => ({ x: r.year, y: r.pct })), ci: rows.map((r) => [r.lo, r.hi]),
    borderColor: color, backgroundColor: color, showLine: false, pointStyle, pointRadius: 4.5, pointHoverRadius: 6,
    pointBorderColor: css("--surface"), pointBorderWidth: 1,
  };
}

function rowFn(dp) {
  const c = dp.dataset.ci[dp.dataIndex];
  return { value: signed(dp.parsed.y, 1), label: `${dp.dataset.label} (${signed(c[0], 1)} to ${signed(c[1], 1)})` };
}

function draw(id, datasets, opts = {}) {
  if (charts[id]) charts[id].destroy();
  const vals = datasets.flatMap((d) => d.ci.flat());
  const digits = opts.digits ?? 0;
  const step = opts.step;
  charts[id] = new Chart(document.getElementById(id), {
    type: "line",
    data: { datasets },
    options: {
      interaction: { mode: "x", intersect: false },
      layout: { padding: { right: opts.rightPad || 8 } },
      plugins: {
        legend: opts.legend ? { display: true, position: "top", align: "start", labels: { color: css("--ink2"), usePointStyle: true, boxWidth: 8 } } : { display: false },
        tooltip: { enabled: false, external: htmlTooltip((dps) => String(dps[0].parsed.x), rowFn) },
        band: { from: 2019.5, to: 2021.5, label: "pandemic" },
      },
      scales: {
        x: yearAxis(2011, 2026),
        y: { grid: { color: gridColor }, border: { display: false },
          min: Math.min(opts.ymin ?? Infinity, Math.floor(Math.min(...vals) / (step || 5)) * (step || 5)),
          max: Math.max(opts.ymax ?? -Infinity, Math.ceil(Math.max(...vals) / (step || 5)) * (step || 5)),
          ticks: { color: css("--muted"), stepSize: step, callback: (v) => signed(v, digits) } },
      },
    },
    plugins: [band, ciLines, crosshair, endLabels],
  });
}

function table(id, rows) {
  makeTable(document.getElementById(id), ["Year", "Effect", "95% CI"], rows.map((r) => [String(r.year), signed(r.pct, 1), `${signed(r.lo, 1)} to ${signed(r.hi, 1)}`]), [1]);
}

export function renderYears(effects) {
  E = effects;
  const m = E.wet_by_year_modes;
  draw("c-modes", [
    series(m.cycling, css("--s1"), "Cycling", "circle", "Cycling"),
    series(m.walking, css("--s2"), "Walking", "rect", "Walking"),
    series(m.cars, css("--s3"), "Cars", "rectRot", "Cars"),
  ], { legend: true, rightPad: 64, ymax: 5, step: 5 });
  const years = [...new Set([...m.cycling, ...m.walking, ...m.cars].map((r) => r.year))].sort();
  const get = (arr, y) => { const r = arr.find((x) => x.year === y); return r ? `${signed(r.pct, 1)} (${signed(r.lo, 1)} to ${signed(r.hi, 1)})` : ""; };
  makeTable(document.getElementById("tbl-modes"), ["Year", "Cycling", "Walking", "Cars"], years.map((y) => [String(y), get(m.cycling, y), get(m.walking, y), get(m.cars, y)]));
  const c = E.cycling_by_year;
  draw("c-rain", [series(c.rain, css("--s1"), "Cycling, wet day", "circle")], { ymax: 0, step: 5 });
  draw("c-cold", [series(c.cold, css("--s1"), "Cycling, per °C (0–15 °C)", "circle")], { ymin: 0, step: 1 });
  draw("c-heat", [series(c.heat, css("--s1"), "Cycling, per °C above 25 °C", "circle")], { step: 0.5, digits: 1 });
  table("tbl-rain", c.rain);
  table("tbl-cold", c.cold);
  table("tbl-heat", c.heat);
  testsTable();
}

function ci(o) { return `[${o.ci95 ? o.ci95.map((v) => fmt(v)).join(", ") : ""}]`; }
function fmt(v) { return (v < 0 ? "−" : "+") + Math.abs(v).toFixed(3); }

function testsTable() {
  const T = E.tests;
  const X = E.extended;
  const p1 = T.P1_P2_core.rain;
  const p3 = T.P3_core_rush.rain;
  const p2 = T.P1_P2_core;
  const q1 = X.Q1_bikes_trend.rain;
  const q2 = X.Q2_bike_vs_walk.rain.bike_minus_walk;
  const q3 = X.Q3_canton_vs_city_exploratory.rain.canton_minus_bike;
  const q4 = X.Q4_cars_periods.rain;
  const rows = [
    ["1. Wet days hurt cycling less in 2022–2026 than in 2011–2014 (9 counters)", `Change ${fmt(p1.change)} [${fmt(p1.change - 1.96 * p1.change_se)}, ${fmt(p1.change + 1.96 * p1.change_se)}]`, "Yes"],
    ["2. Cold and heat effects shrank more than the rain effect (the e-bike pattern)", `Cold minus rain shrinkage ${fmt(p2.cold_minus_rain_shrink)} [${fmt(p2.cold_minus_rain_shrink - 1.96 * p2.cold_minus_rain_shrink_se)}, ${fmt(p2.cold_minus_rain_shrink + 1.96 * p2.cold_minus_rain_shrink_se)}]`, "No"],
    ["3. The change also shows in weekday rush hours", `Change ${fmt(p3.change)} [${fmt(p3.change - 1.96 * p3.change_se)}, ${fmt(p3.change + 1.96 * p3.change_se)}]`, "Yes"],
    ["All 33 city counters: rain effect weakens over time (not a blind test)", `${fmt(q1.est)} per decade ${ci(q1)}`, "Yes"],
    ["Cycling changed more than walking (2014–2022)", `Difference ${fmt(q2.est)} ${ci(q2)}`, "Yes"],
    ["Larger change in the suburbs (exploratory)", `Canton minus city ${fmt(q3.est)} ${ci(q3)}`, "No"],
    ["More cars on wet days in 2012–2014", `${fmt(q4.early.est)} ${ci(q4.early)}`, "No"],
    ["The wet-day rise in car traffic became smaller", `Change ${fmt(q4.change.est)} ${ci(q4.change)}`, "No"],
  ];
  makeTable(document.getElementById("tbl-tests"), ["Prediction", "Result (log points, 95% CI)", "Supported"], rows);
}

export function yearsThemeChanged() { if (E) renderYears(E); }
