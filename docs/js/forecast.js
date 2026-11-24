// Forecasting: model scores and actual vs forecast per counter.
import { css, dayToDate, fmtDate, makeTable, num, tickDays } from "./util.js";
import { barLabels, crosshair, gridColor, htmlTooltip } from "./charts.js";

/* global Chart */

let F, scoreChart, lineChart, fcRange = 120;
const MODELS = [
  { key: "gwn", label: "Graph neural network (Graph WaveNet)", color: "--s1" },
  { key: "lgbm", label: "LightGBM", color: "--s2" },
  { key: "rnn", label: "Network without graph (RNN)", color: "--s3" },
];

function scores() {
  const S = F.scores;
  const labels = MODELS.map((m) => m.label);
  const wx = MODELS.map((m) => S[`${m.key}_wx`].mae_ratio);
  const nowx = MODELS.map((m) => S[`${m.key}_nowx`].mae_ratio);
  if (scoreChart) scoreChart.destroy();
  scoreChart = new Chart(document.getElementById("c-scores"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Tomorrow's weather known", data: wx, backgroundColor: css("--s1"), barThickness: 14, borderRadius: 3, valueLabels: wx.map((v) => v.toFixed(2)) },
        { label: "Not known", data: nowx, backgroundColor: css("--s2"), barThickness: 14, borderRadius: 3, valueLabels: nowx.map((v) => v.toFixed(2)) },
      ],
    },
    options: {
      indexAxis: "y",
      layout: { padding: { right: 30 } },
      plugins: {
        legend: { display: true, position: "top", align: "start", labels: { color: css("--ink2"), boxWidth: 12 } },
        tooltip: { enabled: false },
      },
      scales: {
        x: { min: 0, max: 1, grid: { color: gridColor }, border: { display: false }, ticks: { color: css("--muted"), callback: (v) => v.toFixed(1) },
          title: { display: true, text: "Error relative to 'same weekday last week' (1.0 = no better)", color: css("--ink2") } },
        y: { grid: { display: false }, ticks: { color: css("--ink2") }, border: { color: css("--axis") } },
      },
    },
    plugins: [barLabels],
  });
  const rows = MODELS.map((m) => [m.label, S[`${m.key}_wx`].mae_ratio.toFixed(2), S[`${m.key}_nowx`].mae_ratio.toFixed(2),
    num(S[`${m.key}_wx`].mae), num(S[`${m.key}_nowx`].mae)]);
  rows.push(["Same weekday last week", "1.00", "1.00", num(S.lastweek.mae), num(S.lastweek.mae)]);
  makeTable(document.getElementById("tbl-scores"), ["Model", "Ratio, weather known", "Ratio, not known", "Mean error, known (bikes/day)", "Mean error, not known"], rows, [1, 2, 3, 4]);
}

function line() {
  const node = document.getElementById("fc-node").value;
  const v = document.getElementById("fc-wx").value;
  const n = F.nodes[node];
  const last = n.d[n.d.length - 1];
  const min = fcRange === "all" ? n.d[0] : last - fcRange;
  const pick = (arr) => n.d.map((d, i) => ({ x: d, y: arr[i] })).filter((p) => p.x >= min);
  const datasets = [
    { label: "Actual", data: pick(n.y), borderColor: css("--ink"), backgroundColor: css("--ink"), borderWidth: 2, pointRadius: 0, pointStyle: "line" },
    ...MODELS.map((m) => ({ label: m.label, data: pick(n[`${m.key}_${v}`]), borderColor: css(m.color), backgroundColor: css(m.color), borderWidth: 1.3, pointRadius: 0, pointStyle: "line", hidden: m.key === "rnn" })),
    { label: "Same weekday last week", data: pick(n.lastweek), borderColor: css("--muted"), backgroundColor: css("--muted"), borderWidth: 1.1, borderDash: [4, 3], pointRadius: 0, pointStyle: "line", hidden: true },
  ];
  if (lineChart) lineChart.destroy();
  lineChart = new Chart(document.getElementById("c-fc"), {
    type: "line",
    data: { datasets },
    options: {
      parsing: false,
      interaction: { mode: "x", intersect: false },
      plugins: {
        legend: { display: true, position: "top", align: "start", labels: { color: css("--ink2"), usePointStyle: true, boxWidth: 18, boxHeight: 6 } },
        tooltip: { enabled: false, external: htmlTooltip((dps) => fmtDate(dayToDate(F.day0, dps[0].parsed.x)), (dp) => ({ value: num(dp.parsed.y), label: dp.dataset.label })) },
      },
      scales: {
        x: { type: "linear", min, max: last, grid: { display: false }, border: { color: css("--axis") },
          afterBuildTicks: (axis) => { axis.ticks = tickDays(min, last, F.day0); },
          ticks: { color: css("--muted"), maxRotation: 0, callback: (val) => fmtDate(dayToDate(F.day0, val), false) } },
        y: { beginAtZero: true, grid: { color: gridColor }, border: { display: false }, ticks: { color: css("--muted"), callback: (val) => num(val) } },
      },
    },
    plugins: [crosshair],
  });
}

export function renderForecast(fc) {
  F = fc;
  const sel = document.getElementById("fc-node");
  if (!sel.options.length) {
    Object.entries(F.nodes).sort((a, b) => a[1].name.localeCompare(b[1].name)).forEach(([k, n]) => {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = n.name;
      sel.appendChild(o);
    });
    sel.value = Object.keys(F.nodes).includes("VZS_MYTH") ? "VZS_MYTH" : sel.options[0].value;
    sel.addEventListener("change", line);
    document.getElementById("fc-wx").addEventListener("change", line);
    document.querySelectorAll("[data-fcrange]").forEach((b) => b.addEventListener("click", () => {
      fcRange = b.dataset.fcrange === "all" ? "all" : Number(b.dataset.fcrange);
      document.querySelectorAll("[data-fcrange]").forEach((x) => x.classList.toggle("on", x === b));
      line();
    }));
  }
  scores();
  line();
}

export function forecastThemeChanged() { if (F) { scores(); line(); } }
