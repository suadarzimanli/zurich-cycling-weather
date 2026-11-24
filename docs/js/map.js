// Map of all counters, filters, and the counter panel with its daily chart.
import { TYPES, css, dayToDate, fmtDate, getJSON, makeTable, num, shapeSVG, signed, tickDays } from "./util.js";
import { crosshair, gridColor, htmlTooltip } from "./charts.js";

/* global L, Chart */

// OpenStreetMap tiles, shown in grey (light theme) or inverted (dark theme) with CSS filters.
const TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · boundaries &copy; swisstopo, City of Zurich';

let map, tiles, boundaryLayer, locations, current = null, chart = null, range = 365;
const groups = {};
const markers = {};
const cache = {};

function theme() { return document.documentElement.dataset.theme; }

function icon(type, selected) {
  const size = selected ? 20 : 14;
  return L.divIcon({ className: "marker-wrap", html: shapeSVG(type, size, selected), iconSize: [24, 24], iconAnchor: [12, 12] });
}

function drawBoundaries(b) {
  if (boundaryLayer) boundaryLayer.remove();
  const style = { color: css("--muted"), weight: 0.8, fill: false, interactive: false };
  boundaryLayer = L.layerGroup([
    ...b.districts.map((p) => L.polygon(p, style)),
    ...b.canton.map((p) => L.polygon(p, { ...style, weight: 1.4 })),
  ]).addTo(map);
}

let boundaries;
export async function initMap(locs) {
  locations = locs;
  map = L.map("map", { zoomControl: true, preferCanvas: false }).fitBounds([[47.325, 8.45], [47.44, 8.62]]);
  tiles = L.tileLayer(TILE, { attribution: ATTR, maxZoom: 19, className: "base-tiles" }).addTo(map);
  boundaries = await getJSON("data/boundaries.json");
  drawBoundaries(boundaries);
  Object.keys(TYPES).forEach((t) => { groups[t] = L.layerGroup().addTo(map); });
  locations.forEach((loc) => {
    const m = L.marker([loc.lat, loc.lon], { icon: icon(loc.type, false), keyboard: true, title: loc.name, alt: `${TYPES[loc.type].label}: ${loc.name}` });
    const tip = document.createElement("div");
    tip.textContent = loc.name;
    m.bindTooltip(tip, { direction: "top", offset: [0, -8] });
    m.on("click", () => select(loc.id));
    m.addTo(groups[loc.type]);
    markers[loc.id] = m;
  });
  document.querySelectorAll(".filters input").forEach((cb) => {
    const t = cb.dataset.type;
    document.getElementById(`n-${t}`).textContent = `(${locations.filter((l) => l.type === t).length})`;
    cb.addEventListener("change", () => { if (cb.checked) groups[t].addTo(map); else groups[t].remove(); });
  });
  drawKeys();
  document.querySelectorAll("#panel-detail .range button").forEach((b) => {
    b.addEventListener("click", () => {
      range = b.dataset.range === "all" ? "all" : Number(b.dataset.range);
      document.querySelectorAll("#panel-detail .range button").forEach((x) => x.classList.toggle("on", x === b));
      if (current) drawSeries(current.loc, current.s);
    });
  });
}

function drawKeys() {
  document.querySelectorAll(".key").forEach((k) => { k.innerHTML = shapeSVG(k.dataset.shape, 14, false); });
}

export function mapThemeChanged() {
  if (!map) return;
  drawBoundaries(boundaries);
  drawKeys();
  locations.forEach((l) => markers[l.id].setIcon(icon(l.type, current && current.loc.id === l.id)));
  if (current) drawSeries(current.loc, current.s);
}

export function invalidate() { if (map) map.invalidateSize(); }

async function select(id) {
  const loc = locations.find((l) => l.id === id);
  if (current) markers[current.loc.id].setIcon(icon(current.loc.type, false));
  markers[id].setIcon(icon(loc.type, true));
  document.getElementById("panel-empty").hidden = true;
  document.getElementById("panel-detail").hidden = false;
  document.getElementById("d-type").textContent = loc.label;
  document.getElementById("d-name").textContent = loc.name;
  const unit = loc.type === "car" ? "vehicles" : loc.type === "walk" ? "pedestrians" : "cyclists";
  if (loc.rain) {
    document.getElementById("d-rain").textContent = signed(loc.rain.pct);
    document.getElementById("d-rain-l").textContent = `${unit} on a wet day at this counter (95% CI ${signed(loc.rain.lo)} to ${signed(loc.rain.hi)})`;
  } else {
    document.getElementById("d-rain").textContent = "n/a";
    document.getElementById("d-rain-l").textContent = "too few days for a reliable rain estimate";
  }
  document.getElementById("d-mean").textContent = num(loc.mean);
  document.getElementById("d-period").textContent =
    `${num(loc.days)} complete days between ${fmtDate(new Date(loc.first + "T00:00:00Z"))} and ${fmtDate(new Date(loc.last + "T00:00:00Z"))}. Weather station: ${loc.weather_station}. The rain effect compares each day with dry days at the same counter in the same month, over all its years.`;
  if (!cache[id]) cache[id] = await getJSON(`data/series/${id}.json`);
  current = { loc, s: cache[id] };
  drawSeries(loc, cache[id]);
}

function drawSeries(loc, s) {
  const last = s.d[s.d.length - 1];
  const min = range === "all" ? s.d[0] : Math.max(s.d[0], last - range);
  const pts = [];
  const wet = [];
  const rainAt = new Map();
  s.d.forEach((d, i) => {
    if (d < min) return;
    pts.push({ x: d, y: s.y[i] });
    rainAt.set(d, s.r[i] / 10);
    if (s.r[i] >= 20) wet.push({ x: d, y: s.y[i] });
  });
  const color = css(TYPES[loc.type].color);
  const longSpan = last - min > 800;
  const data = {
    datasets: [
      { label: "Daily count", data: pts, borderColor: color, backgroundColor: color, borderWidth: longSpan ? 0.8 : 1.4, pointRadius: 0, pointStyle: "line", spanGaps: false },
      { label: "Wet day (2 mm or more)", data: wet, type: "scatter", borderColor: css("--ink"), backgroundColor: css("--ink"), pointRadius: longSpan ? 1.4 : 2.4, pointStyle: "circle" },
    ],
  };
  const options = {
    parsing: false,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    plugins: {
      legend: { display: true, position: "top", align: "start", labels: { color: css("--ink2"), usePointStyle: true, boxWidth: 14, boxHeight: 6 } },
      tooltip: {
        enabled: false,
        external: htmlTooltip(
          (dps) => fmtDate(dayToDate(s.day0, dps[0].parsed.x)),
          (dp) => dp.datasetIndex === 0 ? { value: num(dp.parsed.y), label: `${rainAt.get(dp.parsed.x).toFixed(1)} mm rain, 6:00–20:00` } : null,
        ),
      },
    },
    scales: {
      x: { type: "linear", min, max: last, grid: { display: false }, border: { color: css("--axis") },
        afterBuildTicks: (axis) => { axis.ticks = tickDays(min, last, s.day0); },
        ticks: { color: css("--muted"), maxRotation: 0, autoSkip: true, callback: (v) => fmtDate(dayToDate(s.day0, v), false) } },
      y: { beginAtZero: true, grid: { color: gridColor }, border: { display: false }, ticks: { color: css("--muted"), callback: (v) => num(v) } },
    },
  };
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("c-series"), { type: "line", data, options, plugins: [crosshair] });
  // table view: simple yearly averages on dry and wet days (not adjusted for season)
  const years = {};
  s.d.forEach((d, i) => {
    const y = dayToDate(s.day0, d).getUTCFullYear();
    years[y] = years[y] || { n: 0, dry: [], wet: [] };
    years[y].n += 1;
    if (s.r[i] < 1) years[y].dry.push(s.y[i]);
    if (s.r[i] >= 20) years[y].wet.push(s.y[i]);
  });
  const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
  const rows = Object.keys(years).sort().map((y) => {
    const a = mean(years[y].dry);
    const b = mean(years[y].wet);
    return [y, num(years[y].n), Number.isNaN(a) ? "" : num(a), Number.isNaN(b) ? "" : num(b), Number.isNaN(a) || Number.isNaN(b) ? "" : signed(100 * (b / a - 1))];
  });
  makeTable(document.getElementById("tbl-series"), ["Year", "Days", "Mean on dry days", "Mean on wet days", "Difference"], rows, [1, 2, 3, 4]);
  const note = document.createElement("p");
  note.className = "small";
  note.textContent = "Simple averages, not adjusted for season or weekday. The estimate above is adjusted.";
  document.getElementById("tbl-series").appendChild(note);
}
