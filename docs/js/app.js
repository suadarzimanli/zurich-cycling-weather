// Entry point: theme, tabs and lazy loading of each section.
import { getJSON, wireTableButtons } from "./util.js";
import { applyDefaults } from "./charts.js";
import { initMap, invalidate, mapThemeChanged } from "./map.js";
import { renderYears, yearsThemeChanged } from "./years.js";
import { calcThemeChanged, initCalc } from "./calc.js";
import { forecastThemeChanged, renderForecast } from "./forecast.js";

const root = document.documentElement;
const btn = document.getElementById("themeBtn");
const stored = localStorage.getItem("theme");
root.dataset.theme = stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function labelThemeButton() {
  const dark = root.dataset.theme === "dark";
  btn.textContent = dark ? "Light theme" : "Dark theme";
  btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
}
labelThemeButton();
applyDefaults();

const shown = new Set();
const loaders = {
  map: async () => initMap(await getJSON("data/locations.json")),
  years: async () => renderYears(await getJSON("data/effects.json")),
  calc: async () => initCalc(await getJSON("data/calculator.json")),
  fc: async () => renderForecast(await getJSON("data/forecast.json")),
  about: async () => {},
};

async function show(tab) {
  document.querySelectorAll(".tabs [role=tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== `tab-${tab}`; s.classList.toggle("active", s.id === `tab-${tab}`); });
  if (!shown.has(tab)) {
    shown.add(tab);
    try {
      await loaders[tab]();
    } catch (e) {
      const p = document.createElement("p");
      p.className = "small";
      p.textContent = `Could not load this section (${e.message}). If you opened the file directly, serve the folder over HTTP.`;
      document.getElementById(`tab-${tab}`).prepend(p);
      console.error(e);
    }
  }
  if (tab === "map") invalidate();
  history.replaceState(null, "", `#${tab}`);
}

document.querySelectorAll(".tabs [role=tab]").forEach((b, i, all) => {
  b.addEventListener("click", () => show(b.dataset.tab));
  b.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const next = all[(i + (e.key === "ArrowRight" ? 1 : all.length - 1)) % all.length];
    next.focus();
    show(next.dataset.tab);
  });
});

btn.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", root.dataset.theme);
  labelThemeButton();
  applyDefaults();
  mapThemeChanged();
  if (shown.has("years")) yearsThemeChanged();
  if (shown.has("calc")) calcThemeChanged();
  if (shown.has("fc")) forecastThemeChanged();
});

wireTableButtons();
const start = (location.hash || "#map").slice(1);
show(loaders[start] ? start : "map");
if (start !== "map") { shown.add("map"); loaders.map(); }
