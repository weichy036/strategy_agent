export function createTurnResult(status, data) {
  if (status === "completed") return completedResult(data);
  if (status === "needs_clarification") return clarificationResult(data);
  if (status === "blocked_missing_data") return missingDataResult(data);
  return null;
}

function completedResult(data) {
  const summary = data?.result_page?.summary || {};
  const root = div("turn-result");
  root.append(textBlock(summary.summary_text || "回测完成。", "turn-result-summary"));

  const tabs = [
    ["overview", "概况", overviewPanel(data)],
    ["selection", "选股", selectionPanel(data?.result_page?.trade_stats || {})],
    ["trades", "交易", tradesPanel(data?.result_page?.trade_stats || {})],
  ].filter(([, , panel]) => panel);
  root.append(tabShell(tabs));

  const risks = data?.result_page?.risk_disclosures || [];
  root.append(textBlock(risks.length ? risks.join("；") : "回测结果不构成投资建议。", "turn-result-risk"));
  return root;
}

function tabShell(tabs) {
  const root = div("result-tabs");
  const nav = div("result-tab-nav");
  const panels = div("result-tab-panels");
  tabs.forEach(([key, label, panel], index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `result-tab ${index === 0 ? "active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      root.querySelectorAll(".result-tab").forEach((item) => item.classList.remove("active"));
      root.querySelectorAll(".result-tab-panel").forEach((item) => item.classList.add("hidden"));
      button.classList.add("active");
      root.querySelector(`[data-panel="${key}"]`)?.classList.remove("hidden");
    });
    panel.dataset.panel = key;
    panel.classList.add("result-tab-panel");
    if (index > 0) panel.classList.add("hidden");
    nav.append(button);
    panels.append(panel);
  });
  root.append(nav, panels);
  return root;
}

function overviewPanel(data) {
  const root = div("overview-panel");
  root.append(insightRows(completedInsights(data)));
  root.append(metricRows(data?.metrics));
  const chart = equityChart(data?.result_page?.equity_curve || {});
  if (chart) root.append(chart);
  return root;
}

function selectionPanel(tradeStats) {
  const items = tradeStats?.selection_snapshots || [];
  if (!Array.isArray(items) || items.length === 0) return null;
  const root = div("selection-snapshots");
  root.append(sectionHead("最近调仓选股", tradeStats?.selection_artifact, "完整明细"));
  for (const item of items.slice().reverse()) {
    const row = div("selection-row");
    row.append(textBlock(formatDate(item.trade_date), "selection-date"));
    row.append(chips((item.symbols || []).slice(0, 20)));
    root.append(row);
  }
  return root;
}

function tradesPanel(tradeStats) {
  const items = tradeStats?.trade_snapshots || [];
  if (!Array.isArray(items) || items.length === 0) return null;
  const root = div("trade-panel");
  root.append(sectionHead("最近交易明细", tradeStats?.trade_artifact, "完整交易日志"));
  const table = document.createElement("table");
  table.className = "trade-table";
  table.innerHTML = "<thead><tr><th>日期</th><th>股票</th><th>方向</th><th>数量</th><th>成交价</th><th>金额</th><th>当次收益</th><th>累计收益</th></tr></thead>";
  const body = document.createElement("tbody");
  for (const item of items.slice().reverse()) {
    const row = document.createElement("tr");
    const side = String(item.side || "");
    row.innerHTML = `
      <td>${escapeHtml(formatDate(item.trade_date))}</td>
      <td>${escapeHtml(item.symbol || "-")}</td>
      <td><span class="trade-side ${side}">${sideText(side)}</span></td>
      <td>${formatNumber(item.shares, 0)}</td>
      <td>${formatNumber(item.price, 2)}</td>
      <td>${formatNumber(item.amount, 0)}</td>
      <td class="${profitClass(item.realized_profit)}">${formatSigned(item.realized_profit, 2)}</td>
      <td class="${profitClass(item.cumulative_profit)}">${formatSigned(item.cumulative_profit, 2)}</td>
    `;
    body.append(row);
  }
  table.append(body);
  root.append(table);
  return root;
}

function sectionHead(title, artifact, linkText) {
  const head = div("section-head");
  head.append(textBlock(title, "section-title-muted"));
  if (artifact?.url) {
    const link = document.createElement("a");
    link.className = "selection-link";
    link.href = artifact.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = linkText;
    head.append(link);
  }
  return head;
}

function clarificationResult(data) {
  const clarification = data?.clarification || {};
  const root = div("turn-result");
  root.append(textBlock("需要补充信息", "turn-result-title"));
  root.append(textBlock(clarification.next_question || "需要补充关键条件后再继续。", "turn-result-summary"));
  const fields = clarification.must_ask_fields || [];
  if (fields.length) root.append(chips(fields));
  return root;
}

function missingDataResult(data) {
  const report = data?.data_availability || {};
  const root = div("turn-result");
  root.append(textBlock("数据暂未就绪", "turn-result-title"));
  root.append(textBlock((report.blocking_issues || []).join("；") || report.rationale || "缺少本地数据。", "turn-result-summary"));
  return root;
}

function completedInsights(data) {
  const schema = data?.strategy_schema || {};
  const availability = data?.data_availability || {};
  const required = Array.isArray(availability.required_datasets)
    ? availability.required_datasets.map((item) => item.dataset).join("、")
    : "";
  return [
    [schema?.universe?.type === "equity_universe" ? "选股范围" : "交易标的", universeLabel(schema?.universe)],
    ["数据检查", availability.is_ready ? `已就绪${required ? `（${required}）` : ""}` : "未就绪"],
    ["执行口径", "信号次日开盘成交，历史回测不代表未来。"],
  ];
}

function universeLabel(universe) {
  if (universe?.symbols?.length) return universe.symbols.join("、");
  if (universe?.scope) return universe.scope;
  if (universe?.type === "equity_universe") return "A股全市场";
  return "未识别";
}

function metricRows(metrics) {
  const rows = [
    ["累计收益", pct(metrics?.return_metrics?.total_return)],
    ["年化收益", pct(metrics?.return_metrics?.annualized_return)],
    ["最大回撤", pct(metrics?.risk_metrics?.max_drawdown)],
    ["夏普比率", sig(metrics?.risk_metrics?.sharpe)],
  ];
  const root = div("turn-metrics");
  for (const [label, value] of rows) {
    const item = div("metric-card");
    item.append(textBlock(label, "metric-label"));
    item.append(textBlock(String(value), "metric-value"));
    root.append(item);
  }
  return root;
}

function insightRows(rows) {
  const root = div("turn-insights");
  for (const [label, value] of rows) {
    const item = div("insight-card");
    item.append(textBlock(label, "insight-title"));
    item.append(textBlock(value, "insight-value"));
    root.append(item);
  }
  return root;
}

function equityChart(equityCurve) {
  const artifactUrl = equityCurve?.artifact?.url;
  if (artifactUrl) {
    const root = div("turn-chart-wrap");
    const image = document.createElement("img");
    image.className = "turn-chart";
    image.src = artifactUrl;
    image.alt = "收益曲线";
    image.loading = "lazy";
    image.onerror = () => image.replaceWith(equityChartSvg(equityCurve.series || []));
    root.append(image, dateLabels(equityCurve.series || [], equityCurve.meta || {}));
    return root;
  }
  return equityChartSvg(equityCurve?.series || []);
}

function equityChartSvg(series) {
  if (!Array.isArray(series) || series.length < 2) return null;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("turn-chart");
  svg.setAttribute("viewBox", "0 0 760 250");
  svg.setAttribute("preserveAspectRatio", "none");
  const points = chartPoints(series, 760, 250, 18);
  const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
  area.setAttribute("d", `M 18,232 L ${points} L 742,232 Z`);
  area.setAttribute("fill", "rgba(17,17,17,0.07)");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", points);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#111111");
  line.setAttribute("stroke-width", "2");
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("stroke-linejoin", "round");
  svg.append(area, line);
  appendSvgDateLabels(svg, series, 760, 250, 18);
  return svg;
}

function chartPoints(series, width, height, pad) {
  const values = series.map((point) => Number(point.nav));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return series.map((point, idx) => {
    const x = pad + idx * ((width - pad * 2) / (series.length - 1));
    const y = height - pad - (Number(point.nav) - min) * ((height - pad * 2) / Math.max(max - min, 1e-9));
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function dateLabels(series, meta = {}) {
  const root = div("chart-date-labels");
  if (meta.start_date || meta.end_date) {
    root.append(textBlock(formatDate(meta.start_date), "chart-date-label"));
    root.append(textBlock(formatDate(meta.end_date), "chart-date-label"));
    return root;
  }
  if (!Array.isArray(series) || series.length < 2) return root;
  root.append(textBlock(formatDate(series[0]?.trade_date), "chart-date-label"));
  root.append(textBlock(formatDate(series[series.length - 1]?.trade_date), "chart-date-label"));
  return root;
}

function appendSvgDateLabels(svg, series, width, height, pad) {
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
    svg.appendChild(text);
  }
}

function formatDate(value) {
  const text = String(value || "");
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  return text;
}

function chips(items) {
  const root = div("clarify-missing");
  for (const item of items) root.append(textBlock(item, "field-chip"));
  return root;
}

function div(className) {
  const node = document.createElement("div");
  node.className = className;
  return node;
}

function textBlock(text, className) {
  const node = document.createElement("div");
  node.className = className;
  node.textContent = text;
  return node;
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function sig(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toPrecision(4);
}

function sideText(side) {
  return side === "buy" ? "买" : side === "sell" ? "卖" : side || "-";
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatSigned(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  const sign = number > 0 ? "+" : "";
  return `${sign}${number.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

function profitClass(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) return "";
  return number > 0 ? "profit-positive" : "profit-negative";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
