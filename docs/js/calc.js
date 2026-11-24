// "Then and now" calculator: expected change in cyclists for a chosen day, 2011-2014 vs 2022-2026.
import { css, signed } from "./util.js";
import { barLabels, ciLines, gridColor } from "./charts.js";

/* global Chart */

const VARS = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"];
let C, chart;

function features(rain, t, sun) {
  return [rain === "light" ? 1 : 0, rain === "wet" ? 1 : 0, Math.min(t, 5), Math.min(Math.max(t - 5, 0), 10),
    Math.min(Math.max(t - 15, 0), 10), Math.max(t - 25, 0), sun];
}
const REF = features("dry", 20, 8);

function quad(g, V) {
  let s = 0;
  for (let i = 0; i < g.length; i += 1) for (let j = 0; j < g.length; j += 1) s += g[i] * V[i][j] * g[j];
  return s;
}

function compute() {
  const rain = document.querySelector('input[name="rain"]:checked').value;
  const t = Number(document.getElementById("in-temp").value);
  const sun = Number(document.getElementById("in-sun").value);
  document.getElementById("v-temp").textContent = `${t < 0 ? "−" : ""}${Math.abs(t)} °C`;
  document.getElementById("v-sun").textContent = `${sun} hour${sun === 1 ? "" : "s"}`;
  const f = features(rain, t, sun);
  const dx = f.map((v, i) => v - REF[i]);
  const idx = (p) => VARS.map((v) => C.names.indexOf(`${v}:${p}`));
  const out = {};
  for (const p of ["early", "late"]) {
    const ii = idx(p);
    const eta = ii.reduce((s, k, j) => s + C.beta[k] * dx[j], 0);
    const g = new Array(C.names.length).fill(0);
    ii.forEach((k, j) => { g[k] = dx[j]; });
    const se = Math.sqrt(quad(g, C.vcov));
    out[p] = { pct: 100 * (Math.exp(eta) - 1), lo: 100 * (Math.exp(eta - 1.96 * se) - 1), hi: 100 * (Math.exp(eta + 1.96 * se) - 1), eta };
  }
  // difference in percentage points, delta method
  const ge = idx("early");
  const gl = idx("late");
  const g = new Array(C.names.length).fill(0);
  ge.forEach((k, j) => { g[k] = -Math.exp(out.early.eta) * dx[j] * 100; });
  gl.forEach((k, j) => { g[k] = Math.exp(out.late.eta) * dx[j] * 100; });
  const diff = out.late.pct - out.early.pct;
  const dse = Math.sqrt(quad(g, C.vcov));
  return { out, diff, dse };
}

function render() {
  const { out, diff, dse } = compute();
  document.getElementById("o-early").textContent = signed(out.early.pct);
  document.getElementById("o-late").textContent = signed(out.late.pct);
  document.getElementById("o-early-ci").textContent = `95% CI ${signed(out.early.lo)} to ${signed(out.early.hi)}`;
  document.getElementById("o-late-ci").textContent = `95% CI ${signed(out.late.lo)} to ${signed(out.late.hi)}`;
  const lo = diff - 1.96 * dse;
  const hi = diff + 1.96 * dse;
  const sure = lo > 0 || hi < 0;
  document.getElementById("o-diff").textContent = Math.abs(diff) < 0.05
    ? "This day is the reference day, so both periods show no change."
    : `Difference between the periods: ${signed(diff, 1, " percentage points")} (95% CI ${signed(lo, 1, "")} to ${signed(hi, 1, "")}). ${sure ? "The interval excludes zero." : "The interval includes zero, so the two periods cannot be told apart for this day."}`;
  const data = {
    labels: ["2011–2014", "2022–2026"],
    datasets: [{
      label: "Expected change", data: [out.early.pct, out.late.pct], backgroundColor: css("--s1"), borderColor: css("--ink2"),
      ci: [[out.early.lo, out.early.hi], [out.late.lo, out.late.hi]], ciColor: css("--ink2"), barThickness: 18, borderRadius: 4,
      valueLabels: [signed(out.early.pct), signed(out.late.pct)], labelAt: [Math.max(out.early.hi, 0), Math.max(out.late.hi, 0)],
    }],
  };
  const all = [out.early.lo, out.late.lo, out.early.hi, out.late.hi, 0];
  const min = Math.floor(Math.min(...all) / 10) * 10;
  const max = Math.max(10, Math.ceil(Math.max(...all) / 10) * 10 + 10);
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("c-calc"), {
    type: "bar", data,
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { min, max, grid: { color: gridColor }, border: { display: false }, ticks: { color: css("--muted"), callback: (v) => signed(v) } },
        y: { grid: { display: false }, border: { color: css("--axis") }, ticks: { color: css("--ink2") } },
      },
    },
    plugins: [ciLines, barLabels],
  });
}

export function initCalc(calc) {
  C = calc;
  document.querySelectorAll('input[name="rain"], #in-temp, #in-sun').forEach((el) => el.addEventListener("input", render));
  render();
}

export function calcThemeChanged() { if (C) render(); }
