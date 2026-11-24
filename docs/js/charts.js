// Chart.js setup: theme colours, HTML tooltip, crosshair, confidence intervals, bands and end labels.
import { css } from "./util.js";

/* global Chart */

export function applyDefaults() {
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = css("--muted");
  Chart.defaults.animation = false;
  Chart.defaults.maintainAspectRatio = false;
}

// One HTML tooltip per chart. Values lead, labels follow. Text is set with textContent.
export function htmlTooltip(titleFn, rowFn) {
  return (context) => {
    const { chart, tooltip } = context;
    const box = chart.canvas.parentNode;
    let el = box.querySelector(".tt");
    if (!el) {
      el = document.createElement("div");
      el.className = "tt";
      box.appendChild(el);
    }
    if (tooltip.opacity === 0 || !tooltip.dataPoints || !tooltip.dataPoints.length) {
      el.style.opacity = 0;
      return;
    }
    el.textContent = "";
    const t = document.createElement("div");
    t.className = "tt-title";
    t.textContent = titleFn(tooltip.dataPoints);
    el.appendChild(t);
    tooltip.dataPoints.forEach((dp) => {
      const r = rowFn(dp);
      if (!r) return;
      const row = document.createElement("div");
      row.className = "tt-row";
      const key = document.createElement("span");
      key.className = "tt-key";
      key.style.background = dp.dataset.borderColor || dp.dataset.backgroundColor;
      const val = document.createElement("span");
      val.className = "tt-val";
      val.textContent = r.value;
      const sub = document.createElement("span");
      sub.className = "tt-sub";
      sub.textContent = r.label;
      row.append(key, val, sub);
      el.appendChild(row);
    });
    el.style.opacity = 1;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    let x = tooltip.caretX + 14;
    if (x + w > chart.width) x = tooltip.caretX - w - 14;
    let y = tooltip.caretY - h / 2;
    y = Math.max(0, Math.min(y, chart.height - h));
    el.style.left = `${Math.max(0, x)}px`;
    el.style.top = `${y}px`;
  };
}

export const crosshair = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip && chart.tooltip.getActiveElements ? chart.tooltip.getActiveElements() : [];
    if (!active.length || chart.config.options.indexAxis === "y") return;
    const x = active[0].element.x;
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    ctx.save();
    ctx.strokeStyle = css("--muted");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.restore();
  },
};

// Vertical (or horizontal for indexAxis "y") 95% interval lines from dataset.ci = [[lo, hi], ...]
export const ciLines = {
  id: "ciLines",
  beforeDatasetsDraw(chart) {
    const ctx = chart.ctx;
    const horiz = chart.config.options.indexAxis === "y";
    chart.data.datasets.forEach((ds, i) => {
      if (!ds.ci || !chart.isDatasetVisible(i)) return;
      const meta = chart.getDatasetMeta(i);
      const scale = horiz ? chart.scales.x : chart.scales.y;
      const area = chart.chartArea;
      ctx.save();
      ctx.beginPath();
      ctx.rect(area.left, area.top, area.right - area.left, area.bottom - area.top);
      ctx.clip();
      ctx.strokeStyle = ds.ciColor || ds.borderColor;
      ctx.lineWidth = ds.ciWidth || 1.6;
      meta.data.forEach((pt, j) => {
        const c = ds.ci[j];
        if (!c) return;
        ctx.beginPath();
        if (horiz) {
          ctx.moveTo(scale.getPixelForValue(c[0]), pt.y);
          ctx.lineTo(scale.getPixelForValue(c[1]), pt.y);
        } else {
          ctx.moveTo(pt.x, scale.getPixelForValue(c[0]));
          ctx.lineTo(pt.x, scale.getPixelForValue(c[1]));
        }
        ctx.stroke();
      });
      ctx.restore();
    });
  },
};

// Shaded band on a linear x axis: options.plugins.band = {from, to, label}
export const band = {
  id: "band",
  beforeDatasetsDraw(chart, args, opts) {
    if (!opts || opts.from === undefined) return;
    const x = chart.scales.x;
    const { top, bottom } = chart.chartArea;
    const ctx = chart.ctx;
    const a = x.getPixelForValue(opts.from);
    const b = x.getPixelForValue(opts.to);
    ctx.save();
    ctx.fillStyle = css("--band");
    ctx.fillRect(a, top, b - a, bottom - top);
    if (opts.label) {
      ctx.fillStyle = css("--muted");
      ctx.font = "11px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(opts.label, (a + b) / 2, top + 12);
    }
    ctx.restore();
  },
};

// Direct label at the last point of each dataset with ds.endLabel
export const endLabels = {
  id: "endLabels",
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((ds, i) => {
      if (!ds.endLabel || !chart.isDatasetVisible(i)) return;
      const meta = chart.getDatasetMeta(i);
      const last = meta.data[meta.data.length - 1];
      if (!last) return;
      ctx.save();
      ctx.fillStyle = css("--ink");
      ctx.font = "12px system-ui, sans-serif";
      ctx.textBaseline = "middle";
      ctx.fillText(ds.endLabel, last.x + 9, last.y);
      ctx.restore();
    });
  },
};

// Value labels at the end of horizontal bars: dataset.valueLabels = ["0.41", ...]
export const barLabels = {
  id: "barLabels",
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((ds, i) => {
      if (!ds.valueLabels || !chart.isDatasetVisible(i)) return;
      const meta = chart.getDatasetMeta(i);
      meta.data.forEach((bar, j) => {
        const txt = ds.valueLabels[j];
        if (!txt) return;
        ctx.save();
        ctx.fillStyle = css("--ink");
        ctx.font = "12px system-ui, sans-serif";
        ctx.textBaseline = "middle";
        const x = ds.labelAt ? chart.scales.x.getPixelForValue(ds.labelAt[j]) : bar.x;
        ctx.fillText(txt, x + 6, bar.y);
        ctx.restore();
      });
    });
  },
};

export function gridColor(ctx) {
  return ctx.tick && ctx.tick.value === 0 ? css("--axis") : css("--grid");
}

export function yearAxis(min, max) {
  const years = [];
  for (let y = min; y <= max; y += 1) years.push(y);
  return {
    type: "linear",
    min: min - 0.6,
    max: max + 0.6,
    grid: { display: false },
    border: { color: css("--axis") },
    afterBuildTicks: (axis) => { axis.ticks = years.filter((y) => y % 2 === 1 || years.length < 9).map((v) => ({ value: v })); },
    ticks: { color: css("--muted"), callback: (v) => String(v), maxRotation: 0 },
  };
}
