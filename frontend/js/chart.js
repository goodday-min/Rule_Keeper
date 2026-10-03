// 외부 라이브러리 없이 SVG로 그리는 시계열 선 그래프.
// series: [{name, color, points:[{x:'YYYY-MM-DD', y}], dash, width}]
// hlines: [{y, name, color, dash}]   markers: [{x, y, color, label}]
import { esc, money } from "./util.js";

const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export function lineChart(el, { series = [], hlines = [], markers = [], height = 260, yFormat = v => money(v) } = {}) {
  const xs = [...new Set(series.flatMap(s => s.points.map(p => p.x)))].sort();
  if (!xs.length) { el.innerHTML = `<p class="muted small">그릴 데이터가 없습니다.</p>`; return; }
  const W = 760, H = height, L = 56, R = 16, T = 14, B = 28;
  const idx = new Map(xs.map((x, i) => [x, i]));
  const ys = [
    ...series.flatMap(s => s.points.map(p => p.y)),
    ...hlines.map(h => h.y), ...markers.filter(m => idx.has(m.x)).map(m => m.y),
  ].filter(v => v !== null && v !== undefined && !isNaN(v));
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.05 || 1;
  lo -= pad; hi += pad;
  const X = i => L + (xs.length === 1 ? (W - L - R) / 2 : (i / (xs.length - 1)) * (W - L - R));
  const Y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);

  // 눈금: y 4칸, x 최대 6개
  const yTicks = [0, 1, 2, 3, 4].map(k => lo + (hi - lo) * k / 4);
  const step = Math.max(1, Math.ceil(xs.length / 6));
  const xTicks = xs.map((x, i) => [x, i]).filter(([, i]) => i % step === 0 || i === xs.length - 1);

  const muted = css("--muted");
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.map(s => s.name).join(", "))} 그래프">`;
  svg += `<g class="grid">${yTicks.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("")}</g>`;
  svg += `<g class="axis">${yTicks.map(v => `<text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${esc(yFormat(v))}</text>`).join("")}`;
  svg += xTicks.map(([x, i]) => `<text x="${X(i)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === xs.length - 1 ? "end" : "middle"}">${esc(xs.length > 400 ? x.slice(0, 7) : x.slice(2))}</text>`).join("") + `</g>`;
  for (const h of hlines) {
    if (h.y === null || h.y === undefined) continue;
    svg += `<line x1="${L}" x2="${W - R}" y1="${Y(h.y)}" y2="${Y(h.y)}" stroke="${h.color}" stroke-width="1.4" ${h.dash !== false ? 'stroke-dasharray="5 4"' : ""}/>`;
    svg += `<text x="${W - R}" y="${Y(h.y) - 5}" text-anchor="end" fill="${h.color}" font-size="11">${esc(h.name)} ${esc(yFormat(h.y))}</text>`;
  }
  for (const s of series) {
    const pts = s.points.filter(p => p.y !== null && p.y !== undefined).map(p => `${X(idx.get(p.x)).toFixed(1)},${Y(p.y).toFixed(1)}`);
    if (!pts.length) continue;
    if (s.dots) {
      svg += s.points.map(p => `<circle cx="${X(idx.get(p.x))}" cy="${Y(p.y)}" r="3" fill="${s.color}"/>`).join("");
    } else {
      svg += `<polyline points="${pts.join(" ")}" fill="none" stroke="${s.color}" stroke-width="${s.width || 1.8}" ${s.dash ? 'stroke-dasharray="5 4"' : ""} stroke-linejoin="round"/>`;
    }
  }
  for (const m of markers) {
    if (!idx.has(m.x)) continue;
    svg += `<circle cx="${X(idx.get(m.x))}" cy="${Y(m.y)}" r="3.2" fill="${m.color}" stroke="${css("--surface")}" stroke-width="1"/>`;
  }
  svg += `<line class="cursor" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="${muted}" stroke-width="1" visibility="hidden"/>`;
  svg += `<rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/></svg>`;

  const legend = [
    ...series.map(s => `<span><i class="${s.dots ? "dot" : s.dash ? "dash" : ""}" style="${s.dots ? "background" : "border-color"}:${s.color}"></i>${esc(s.name)}</span>`),
    ...hlines.filter(h => h.y != null).map(h => `<span><i class="${h.dash !== false ? "dash" : ""}" style="border-color:${h.color}"></i>${esc(h.name)}</span>`),
    ...[...new Map(markers.map(m => [m.label, m.color])).entries()].map(([l, c]) => `<span><i class="dot" style="background:${c}"></i>${esc(l)}</span>`),
  ].join("");
  el.innerHTML = `<div class="chart">${svg}<div class="tip" hidden></div></div><div class="legend">${legend}</div>`;

  // 마우스를 올리면 그날 값
  const box = el.querySelector(".chart"), tip = el.querySelector(".tip"), cursor = el.querySelector(".cursor");
  const lookup = series.map(s => new Map(s.points.map(p => [p.x, p.y])));
  const hit = el.querySelector(".hit");
  const move = ev => {
    const r = box.querySelector("svg").getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(xs.length - 1, Math.round(((px - L) / (W - L - R)) * (xs.length - 1))));
    const x = xs[i];
    cursor.setAttribute("x1", X(i)); cursor.setAttribute("x2", X(i)); cursor.setAttribute("visibility", "visible");
    const rows = series.map((s, k) => lookup[k].has(x) ? `${esc(s.name)} ${esc(yFormat(lookup[k].get(x)))}` : null).filter(Boolean);
    const ms = markers.filter(m => m.x === x).map(m => esc(m.label));
    tip.innerHTML = `<b>${esc(x)}</b><br>${rows.join("<br>")}${ms.length ? "<br>" + [...new Set(ms)].join(", ") : ""}`;
    tip.hidden = false;
    tip.style.left = `${(X(i) / W) * 100}%`;
    tip.style.top = `${(T / H) * 100}%`;
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerleave", () => { tip.hidden = true; cursor.setAttribute("visibility", "hidden"); });
}

export const colors = () => ({
  ink: css("--ink"), muted: css("--muted"), buy: css("--buy"), sell: css("--sell"), warn: css("--warn"), ok: css("--ok"),
});
