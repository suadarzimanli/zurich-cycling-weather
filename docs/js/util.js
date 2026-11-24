// Small helpers shared by all modules.
export const MINUS = "−";

export async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

export function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function signed(v, digits = 0, unit = "%") {
  const r = Number(v.toFixed(digits));
  const a = Math.abs(r).toFixed(digits);
  if (r === 0) return `0${unit}`;
  return `${r < 0 ? MINUS : "+"}${a}${unit}`;
}

export function num(v) {
  return Math.round(v).toLocaleString("en-GB");
}

export function dayToDate(day0, d) {
  const t = new Date(`${day0}T00:00:00Z`);
  t.setUTCDate(t.getUTCDate() + d);
  return t;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function fmtDate(t, withDay = true) {
  const m = MONTHS[t.getUTCMonth()];
  return withDay ? `${t.getUTCDate()} ${m} ${t.getUTCFullYear()}` : `${m} ${t.getUTCFullYear()}`;
}

// Build a table with textContent only (labels may come from data files).
export function makeTable(el, headers, rows, numeric = []) {
  el.textContent = "";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  headers.forEach((h, i) => {
    const th = document.createElement("th");
    th.textContent = h;
    if (numeric.includes(i)) th.className = "num";
    tr.appendChild(th);
  });
  thead.appendChild(tr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const r = document.createElement("tr");
    row.forEach((cell, i) => {
      const td = document.createElement("td");
      td.textContent = cell;
      if (numeric.includes(i)) td.className = "num";
      r.appendChild(td);
    });
    tbody.appendChild(r);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

export function wireTableButtons(root = document) {
  root.querySelectorAll(".table-btn").forEach((b) => {
    if (b.dataset.wired) return;
    b.dataset.wired = "1";
    b.addEventListener("click", () => {
      const t = document.getElementById(b.dataset.table);
      const show = t.hidden;
      t.hidden = !show;
      b.textContent = show ? "Hide table" : "Show table";
      b.setAttribute("aria-expanded", String(show));
    });
  });
}

// Marker shapes, used on the map and in the legend keys.
export const TYPES = {
  bike: { label: "City bike counter", color: "--s1", shape: "circle" },
  walk: { label: "Pedestrian counter", color: "--s2", shape: "square" },
  car: { label: "Car measuring point", color: "--s3", shape: "diamond" },
  canton: { label: "Canton bike counter", color: "--s4", shape: "triangle" },
};

export function shapeSVG(type, size = 14, selected = false) {
  const c = css(TYPES[type].color);
  const o = css("--outline");
  const s = size;
  const sw = selected ? 2.2 : 1;
  const h = s / 2;
  let body;
  if (TYPES[type].shape === "circle") body = `<circle cx="${h}" cy="${h}" r="${h - 1.5}"/>`;
  else if (TYPES[type].shape === "square") body = `<rect x="1.5" y="1.5" width="${s - 3}" height="${s - 3}"/>`;
  else if (TYPES[type].shape === "diamond") body = `<polygon points="${h},1 ${s - 1},${h} ${h},${s - 1} 1,${h}"/>`;
  else body = `<polygon points="${h},1 ${s - 1},${s - 1.5} 1,${s - 1.5}"/>`;
  return `<svg width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" aria-hidden="true"><g fill="${c}" stroke="${o}" stroke-opacity="${selected ? 1 : 0.75}" stroke-width="${sw}">${body}</g></svg>`;
}

// Ticks at month starts (every 1, 2, 6 or 24 months depending on the span) for a day-offset axis.
export function tickDays(min, max, day0) {
  const span = max - min;
  const out = [];
  const start = dayToDate(day0, min);
  const y0 = start.getUTCFullYear();
  const step = span > 2000 ? 24 : span > 800 ? 6 : span > 300 ? 2 : 1;
  for (let y = y0; y <= y0 + 20; y += 1) {
    for (let m = 0; m < 12; m += step) {
      const d = Math.round((Date.UTC(y, m, 1) - Date.parse(`${day0}T00:00:00Z`)) / 86400000);
      if (d >= min && d <= max) out.push({ value: d });
    }
  }
  return out;
}
