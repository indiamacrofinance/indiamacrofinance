// Draws every [data-chart] element with Observable Plot. House style: 02-conventions.md.
import * as Plot from "@observablehq/plot";

const css = getComputedStyle(document.documentElement);
// Brand colours first, then muted distinguishable hues for charts with many components.
const palette = [css.getPropertyValue("--primary").trim(), css.getPropertyValue("--accent").trim(), "#5b8c5a", "#8c5a7a",
  "#3f8fb5", "#c4a23a", "#b0605a", "#6f6fb0", "#4f9e8f", "#9a7b5c", "#a35f9e", "#7f8c8d"];

function drawStacked(el, spec) {
  const rows = spec.rows.map((r) => ({ ...r, date: new Date(r.period) }));
  const marks = [
    Plot.rectY(rows, { x: "date", y: "pp", fill: "component", interval: spec.interval ?? "month", inset: 1, tip: true }),
    Plot.ruleY([0], { stroke: "currentColor", strokeOpacity: 0.4 }),
  ];
  if (spec.total) {
    const tot = spec.total.map(([d, v]) => ({ date: new Date(d), value: v }));
    // Centre the dots on the month bars.
    const halfDays = spec.interval === "3 months" ? 45 : 15;
    const mid = tot.map((r) => ({ ...r, date: new Date(r.date.getTime() + halfDays * 864e5) }));
    marks.push(Plot.dot(mid, { x: "date", y: "value", fill: "currentColor", r: 3.5 }));
    marks.push(Plot.text(mid, { x: "date", y: "value", text: (d) => d.value.toFixed(2), dy: -9, fontSize: 10 }));
  }
  const width = el.clientWidth || 600;
  el.replaceChildren(Plot.plot({
    width, height: Math.max(240, Math.min(340, width * 0.55)),
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" },
    x: { type: "utc" }, y: { grid: true, label: spec.yLabel ?? "percentage points" },
    color: { domain: [...new Set(rows.map((r) => r.component))], range: palette, legend: spec.legend ?? true },
    marks,
  }));
}

function drawHbar(el, spec) {
  // Ranked horizontal bars (e.g. states), with an optional reference line (all-India).
  const rows = [...spec.rows].sort((a, b) => b.value - a.value);
  const width = el.clientWidth || 600;
  const marks = [
    Plot.barX(rows, { x: "value", y: "label", fill: (d) => (d.highlight ? palette[1] : palette[0]), sort: { y: "-x" } }),
    Plot.text(rows, { x: "value", y: "label", text: (d) => d.value.toFixed(spec.decimals ?? 1), dx: 4, textAnchor: "start", fontSize: 10 }),
    Plot.ruleX([0], { stroke: "currentColor", strokeOpacity: 0.4 }),
  ];
  if (spec.reference !== undefined && spec.reference !== null) {
    marks.push(Plot.ruleX([spec.reference], { stroke: palette[1], strokeDasharray: "4,3" }));
    marks.push(Plot.text([spec.reference], { x: (d) => d, frameAnchor: "top", dy: -4, text: () => `${spec.referenceLabel} ${spec.reference.toFixed(spec.decimals ?? 1)}`, fill: palette[1], fontSize: 10 }));
  }
  el.replaceChildren(Plot.plot({
    width, height: Math.max(260, rows.length * 16 + 50), marginLeft: Math.min(290, width * 0.45), marginRight: 40, marginTop: 24,
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" },
    x: { grid: true, label: spec.xLabel ?? null }, y: { label: null }, marks,
  }));
}

function drawCurve(el, spec) {
  // Yield curves: x = tenor in years (log scale, so the short end is readable), one line per date.
  const rows = spec.curves.flatMap((c) => c.points.map(([t, v]) => ({ tenor: t, value: v, label: c.label })));
  const colour = Object.fromEntries(spec.curves.map((c, i) => [c.label, palette[i % palette.length]]));
  const width = el.clientWidth || 600;
  const marks = [];
  for (const c of spec.curves) {
    const pts = rows.filter((r) => r.label === c.label);
    marks.push(Plot.lineY(pts, { x: "tenor", y: "value", stroke: colour[c.label], strokeWidth: c.main ? 2.2 : 1.5, strokeDasharray: c.main ? null : "4,3" }));
    marks.push(Plot.dot(pts, { x: "tenor", y: "value", fill: colour[c.label], r: c.main ? 2.5 : 1.5 }));
  }
  marks.push(Plot.tip(rows, Plot.pointer({ x: "tenor", y: "value", stroke: (d) => colour[d.label],
    title: (d) => `${d.label}\n${d.tenor < 1 ? `${Math.round(d.tenor * 12)} months` : `${d.tenor} years`}: ${d.value.toFixed(2)}%` })));
  const plot = Plot.plot({
    width, height: Math.max(240, Math.min(340, width * 0.55)), marginLeft: 40,
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" },
    x: { type: "log", label: "Years to maturity", ticks: [0.25, 0.5, 1, 2, 3, 5, 10, 20, 40], tickFormat: (t) => (t < 1 ? `${t * 12}m` : `${t}y`) },
    y: { grid: true, label: "%", zero: false }, marks,
  });
  const legend = Plot.legend({ color: { type: "categorical", domain: spec.curves.map((c) => c.label), range: spec.curves.map((c) => colour[c.label]) },
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" } });
  el.replaceChildren(legend, plot);
}

function drawFan(el, spec) {
  // Outturns as a line, a projection path as dots, with shaded bands (widest first).
  const hist = spec.history.map(([d, v]) => ({ date: new Date(d), value: v }));
  const path = spec.path.map((p) => ({ ...p, date: new Date(p.date) }));
  const marks = [];
  if (spec.band) marks.push(Plot.rectY([spec.band], { x1: hist[0].date, x2: path.at(-1).date, y1: (b) => b[0], y2: (b) => b[1], fill: "var(--accent)", fillOpacity: 0.07 }));
  if (spec.target !== undefined) marks.push(Plot.ruleY([spec.target], { stroke: "var(--accent)", strokeDasharray: "4,3" }));
  for (const [k, op] of [["90", 0.12], ["70", 0.2], ["50", 0.32]]) {
    marks.push(Plot.areaY(path, { x: "date", y1: `lo${k}`, y2: `hi${k}`, fill: palette[0], fillOpacity: op, curve: "monotone-x" }));
  }
  marks.push(Plot.lineY(hist, { x: "date", y: "value", stroke: "currentColor", strokeWidth: 1.8 }));
  marks.push(Plot.lineY(path, { x: "date", y: "mid", stroke: palette[0], strokeWidth: 1.8, strokeDasharray: "4,3" }));
  marks.push(Plot.dot(path.filter((p) => !p.anchor), { x: "date", y: "mid", fill: palette[0], r: 3.5, tip: true,
    title: (d) => `${d.label}: ${d.mid.toFixed(1)}%\n50%: ${d.lo50.toFixed(1)}–${d.hi50.toFixed(1)}\n90%: ${d.lo90.toFixed(1)}–${d.hi90.toFixed(1)}` }));
  marks.push(Plot.ruleY([0], { stroke: "currentColor", strokeOpacity: 0.25 }));
  const width = el.clientWidth || 600;
  el.replaceChildren(Plot.plot({
    width, height: Math.max(240, Math.min(340, width * 0.55)),
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" },
    x: { type: "utc" }, y: { grid: true, label: spec.yLabel ?? "%" }, marks,
  }));
}

function draw(el) {
  const spec = JSON.parse(el.dataset.chart);
  if (spec.kind === "fan") return drawFan(el, spec);
  if (spec.kind === "stacked") return drawStacked(el, spec);
  if (spec.kind === "curve") return drawCurve(el, spec);
  if (spec.kind === "hbar") return drawHbar(el, spec);
  const rows = spec.series.flatMap((s) => s.points.map(([d, v]) => ({ date: new Date(d), value: v, label: s.label })));
  const last = rows.reduce((m, r) => (r.date > m ? r.date : m), new Date(0));
  const start = new Date(last); start.setFullYear(start.getFullYear() - spec.years);
  const data = rows.filter((r) => r.date >= start);
  const ref = spec.reference;
  const marks = [];
  if (ref?.band) marks.push(Plot.rectY([ref.band], { x1: start, x2: last, y1: (b) => b[0], y2: (b) => b[1], fill: "var(--accent)", fillOpacity: 0.1 }));
  if (ref?.target !== undefined) marks.push(Plot.ruleY([ref.target], { stroke: "var(--accent)", strokeDasharray: "4,3" }));
  // Zero line only when the data reach zero; level series (e.g. USD/INR) keep a tight axis.
  const lo = Math.min(...data.map((r) => r.value));
  if (lo <= 0 || ref) marks.push(Plot.ruleY([0], { stroke: "currentColor", strokeOpacity: 0.25 }));
  // One line mark per series so each can have its own curve (policy rates are steps).
  // Colours are assigned explicitly: a label such as "Gold" is also a CSS colour name,
  // and Plot would otherwise draw it in that colour.
  const colour = Object.fromEntries(spec.series.map((s, i) => [s.label, palette[i % palette.length]]));
  for (const s of spec.series) {
    marks.push(Plot.lineY(data.filter((r) => r.label === s.label), { x: "date", y: "value", stroke: colour[s.label], strokeWidth: 1.8, curve: s.curve ?? "linear" }));
  }
  const lastPoints = spec.series.map((s) => data.filter((r) => r.label === s.label).at(-1)).filter(Boolean);
  marks.push(Plot.dot(lastPoints, { x: "date", y: "value", fill: (d) => colour[d.label], r: 3 }));
  // End labels: same decimals as the data (5.0, not 5); skip a label that would sit on top of
  // another (within 4% of the y-range) - the tooltip and table still give every value.
  const decimals = Math.min(2, Math.max(...data.slice(-50).map((r) => (String(r.value).split(".")[1] ?? "").length)));
  const span = Math.max(...data.map((r) => r.value)) - Math.min(...data.map((r) => r.value)) || 1;
  const labelled = [];
  for (const p of [...lastPoints].sort((a, b) => b.value - a.value)) {
    if (labelled.every((q) => Math.abs(q.value - p.value) > span * 0.04)) labelled.push(p);
  }
  marks.push(Plot.text(labelled, { x: "date", y: "value", text: (d) => d.value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }), dx: 6, textAnchor: "start", fontSize: 11 }));
  marks.push(Plot.tip(data, Plot.pointerX({ x: "date", y: "value", stroke: (d) => colour[d.label], title: (d) => `${d.label}\n${d.date.toISOString().slice(0, 10)}: ${d.value.toLocaleString("en-US", { maximumFractionDigits: 2 })}` })));
  const width = el.clientWidth || 600;
  // Margins sized to the longest y tick (e.g. "25,000") and end label (e.g. "22,698.85").
  const fmt = (v, d) => v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  const hi = Math.max(...data.map((r) => Math.abs(r.value)));
  const charPx = 6.6;
  const marginLeft = Math.max(36, 14 + charPx * fmt(Math.round(hi), 0).length);
  const marginRight = Math.max(40, 14 + charPx * Math.max(...labelled.map((d) => fmt(d.value, decimals).length), 0));
  const plot = Plot.plot({
    width, height: Math.max(240, Math.min(340, width * 0.55)), marginLeft, marginRight,
    style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" },
    x: { type: "utc" }, y: { grid: true, label: spec.yLabel || null, zero: lo <= 0 || !!ref },
    marks,
  });
  const legend = spec.series.length > 1
    ? Plot.legend({ color: { type: "categorical", domain: spec.series.map((s) => s.label), range: spec.series.map((s) => colour[s.label]) },
        style: { fontFamily: "Inter, system-ui, sans-serif", fontSize: "11px", background: "transparent" } })
    : null;
  el.replaceChildren(...(legend ? [legend, plot] : [plot]));
}

const charts = [...document.querySelectorAll("[data-chart]")];
charts.forEach(draw);
let timer;
window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(() => charts.forEach(draw), 200); });
