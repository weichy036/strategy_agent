import { els } from "./dom.js?v=52";

export function renderMetrics(metrics) {
  els.metricGrid.innerHTML = "";
  if (!metrics) return;
  const items = [
    ["累计收益", metrics?.return_metrics?.total_return],
    ["年化收益", metrics?.return_metrics?.annualized_return],
    ["最大回撤", metrics?.risk_metrics?.max_drawdown],
    ["夏普比率", metrics?.risk_metrics?.sharpe],
  ];
  for (const [label, value] of items) {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `<div class="metric-label">${label}</div><div class="metric-value">${label === "夏普比率" ? sig(value) : pct(value)}</div>`;
    els.metricGrid.appendChild(card);
  }
}

export function renderYearly(yearlyReturns) {
  els.yearlyTableBody.innerHTML = "";
  if (!Array.isArray(yearlyReturns) || yearlyReturns.length === 0) {
    els.yearlyWrap?.classList.add("hidden");
    return;
  }
  els.yearlyWrap?.classList.remove("hidden");
  for (const item of yearlyReturns) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${item.year || "-"}</td><td>${pct(item.return)}</td>`;
    els.yearlyTableBody.appendChild(tr);
  }
}

export function renderChart(series) {
  const artifactUrl = series?.artifact?.url;
  const meta = series?.meta || {};
  if (artifactUrl) {
    renderArtifactChart(artifactUrl, meta);
    return;
  }

  els.chartWrap?.querySelector(".main-chart-image")?.remove();
  els.chartWrap?.querySelector(".chart-date-labels")?.remove();
  els.equityChart.classList.remove("hidden");
  els.equityChart.innerHTML = "";
  if (!Array.isArray(series) || series.length < 2) {
    els.chartWrap?.classList.add("hidden");
    return;
  }
  els.chartWrap?.classList.remove("hidden");

  const width = 760;
  const height = 280;
  const pad = 20;
  const points = chartPoints(series, width, height, pad);
  const endX = pad + (series.length - 1) * ((width - pad * 2) / (series.length - 1));
  appendSvgPath(`M ${pad},${height - pad} L ${points} L ${endX},${height - pad} Z`, "rgba(17,17,17,0.07)");
  appendSvgLine(points);
  appendDateLabels(series, width, height, pad);
}

function renderArtifactChart(url, meta) {
  els.equityChart.innerHTML = "";
  els.equityChart.classList.add("hidden");
  els.chartWrap?.classList.remove("hidden");
  els.chartWrap?.querySelector(".main-chart-image")?.remove();
  els.chartWrap?.querySelector(".chart-date-labels")?.remove();

  const image = document.createElement("img");
  image.className = "main-chart-image";
  image.src = url;
  image.alt = "收益曲线";
  image.loading = "lazy";
  image.onerror = () => {
    image.remove();
    els.equityChart.classList.remove("hidden");
  };
  els.chartWrap?.appendChild(image);

  const labels = document.createElement("div");
  labels.className = "chart-date-labels";
  labels.innerHTML = `<span>${formatDate(meta.start_date)}</span><span>${formatDate(meta.end_date)}</span>`;
  els.chartWrap?.appendChild(labels);
}

function chartPoints(series, width, height, pad) {
  const values = series.map((p) => Number(p.nav));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return series.map((p, idx) => {
    const x = pad + idx * ((width - pad * 2) / (series.length - 1));
    const y = height - pad - (Number(p.nav) - min) * ((height - pad * 2) / Math.max(max - min, 1e-9));
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function appendSvgPath(d, fill) {
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", fill);
  els.equityChart.appendChild(path);
}

function appendSvgLine(points) {
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", points);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#111111");
  line.setAttribute("stroke-width", "2");
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("stroke-linejoin", "round");
  els.equityChart.appendChild(line);
}

function appendDateLabels(series, width, height, pad) {
  const labels = [
    [pad, height - 2, formatDate(series[0]?.trade_date), "start"],
    [width - pad, height - 2, formatDate(series[series.length - 1]?.trade_date), "end"],
  ];
  for (const [x, y, label, anchor] of labels) {
    if (!label) continue;
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", String(x));
    text.setAttribute("y", String(y));
    text.setAttribute("fill", "#75716a");
    text.setAttribute("font-size", "12");
    text.setAttribute("font-weight", "700");
    text.setAttribute("text-anchor", anchor === "end" ? "end" : "start");
    text.textContent = label;
    els.equityChart.appendChild(text);
  }
}

function formatDate(value) {
  const text = String(value || "");
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  return text;
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function sig(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toPrecision(4);
}
