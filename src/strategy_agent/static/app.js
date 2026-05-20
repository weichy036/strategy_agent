const queryInput = document.getElementById("queryInput");
const runBtn = document.getElementById("runBtn");
const exampleBtn = document.getElementById("exampleBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const statusLine = document.getElementById("statusLine");
const resultBadge = document.getElementById("resultBadge");
const chatTimeline = document.getElementById("chatTimeline");
const traceList = document.getElementById("traceList");
const clarifyPanel = document.getElementById("clarifyPanel");
const clarifyQuestion = document.getElementById("clarifyQuestion");
const clarifyMissing = document.getElementById("clarifyMissing");
const summaryBox = document.getElementById("summaryBox");
const metricGrid = document.getElementById("metricGrid");
const equityChart = document.getElementById("equityChart");
const yearlyTableBody = document.querySelector("#yearlyTable tbody");
const riskBox = document.getElementById("riskBox");
const threadItems = document.querySelectorAll(".thread-item");

const examples = [
  "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？",
  "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？",
  "MACD 金叉买入效果怎么样？",
];

let exampleIndex = 0;
let lastSubmittedQuery = "";
let lastClarificationQuestion = "";
let chatTurns = [];
let traceTimer = null;

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function nowTimeLabel() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

function safeText(el, text) {
  if (el) el.textContent = text;
}

function pushTurn(role, text, meta = "") {
  if (!text) return;
  chatTurns.push({ role, text, meta, ts: nowTimeLabel() });
  renderTimeline();
}

function renderTimeline() {
  if (!chatTimeline) return;
  chatTimeline.innerHTML = "";
  if (chatTurns.length === 0) {
    const empty = document.createElement("div");
    empty.className = "bubble agent";
    empty.textContent = "这里会显示多轮澄清与回测对话轨迹。";
    chatTimeline.appendChild(empty);
  } else {
    for (const turn of chatTurns) {
      const bubble = document.createElement("div");
      bubble.className = `bubble ${turn.role}`;
      bubble.textContent = turn.text;
      const meta = document.createElement("div");
      meta.className = "bubble-meta";
      meta.textContent = `${turn.role === "user" ? "用户" : "Agent"} · ${turn.ts}${turn.meta ? ` · ${turn.meta}` : ""}`;
      bubble.appendChild(meta);
      chatTimeline.appendChild(bubble);
    }
  }
  chatTimeline.scrollTop = chatTimeline.scrollHeight;
}

function setBadge(status) {
  resultBadge.className = "badge";
  resultBadge.textContent = status || "未运行";
  if (status === "completed") resultBadge.classList.add("success");
  else if (status === "needs_clarification") resultBadge.classList.add("warn");
  else if (status && status !== "未运行") resultBadge.classList.add("error");
}

function stopTraceLoading() {
  if (traceTimer) {
    clearInterval(traceTimer);
    traceTimer = null;
  }
}

function renderTraceItems(items) {
  if (!traceList) return;
  traceList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "trace-item";
    empty.innerHTML = `<span class="trace-name">本轮尚无工具轨迹</span><span class="trace-state">idle</span>`;
    traceList.appendChild(empty);
    return;
  }
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "trace-item";
    const state = item.state || item.status;
    const stateClass = state === "success" ? "success" : state === "error" ? "error" : state === "running" ? "running" : "";
    const name = item.name || item.actor || item.stage || "Agent";
    const label = item.label || item.status || "done";
    const detail = item.message ? ` · ${item.message}` : "";
    const nameEl = document.createElement("span");
    nameEl.className = "trace-name";
    nameEl.textContent = `${name}${detail}`;
    const stateEl = document.createElement("span");
    stateEl.className = `trace-state ${stateClass}`;
    stateEl.textContent = label;
    row.appendChild(nameEl);
    row.appendChild(stateEl);
    traceList.appendChild(row);
  }
}

function startTraceLoading() {
  stopTraceLoading();
  const steps = [
    { name: "Intent / Clarification", label: "running", state: "running" },
    { name: "Strategy Schema", label: "waiting", state: "idle" },
    { name: "Backtest Engine", label: "waiting", state: "idle" },
    { name: "Metrics / Report", label: "waiting", state: "idle" },
  ];
  let tick = 0;
  renderTraceItems(steps);
  traceTimer = setInterval(() => {
    tick += 1;
    const active = Math.min(Math.floor(tick / 2), steps.length - 1);
    steps.forEach((step, idx) => {
      if (idx < active) {
        step.label = "success";
        step.state = "success";
      } else if (idx === active) {
        step.label = "running";
        step.state = "running";
      } else {
        step.label = "waiting";
        step.state = "idle";
      }
    });
    renderTraceItems(steps);
  }, 650);
}

function renderToolTraceFromPayload(payload) {
  const timeline = Array.isArray(payload?.timeline) ? payload.timeline : [];
  if (timeline.length > 0) {
    renderTraceItems(timeline.map((item) => ({
      name: item.actor || item.stage,
      label: item.status || "done",
      state: item.status || "idle",
      message: item.message || "",
    })));
    return;
  }
  const calls = Array.isArray(payload?.tool_calls) ? payload.tool_calls : [];
  if (calls.length === 0) {
    renderTraceItems([]);
    return;
  }
  const normalized = calls.map((call) => {
    const toolName = call?.name || "unknown_tool";
    const ok = call?.payload?.ok;
    return {
      name: toolName,
      label: ok === true ? "success" : ok === false ? "error" : "done",
      state: ok === true ? "success" : ok === false ? "error" : "idle",
    };
  });
  renderTraceItems(normalized);
}

function renderMetrics(metrics) {
  metricGrid.innerHTML = "";
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
    const labelEl = document.createElement("div");
    labelEl.className = "metric-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("div");
    valueEl.className = "metric-value";
    valueEl.textContent = label === "夏普比率" ? (value ?? "-") : pct(value);
    card.appendChild(labelEl);
    card.appendChild(valueEl);
    metricGrid.appendChild(card);
  }
}

function renderYearly(yearlyReturns) {
  yearlyTableBody.innerHTML = "";
  if (!Array.isArray(yearlyReturns)) return;
  for (const item of yearlyReturns) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${item.year || "-"}</td><td>${pct(item.return)}</td>`;
    yearlyTableBody.appendChild(tr);
  }
}

function renderChart(series) {
  equityChart.innerHTML = "";
  if (!Array.isArray(series) || series.length < 2) return;
  const values = series.map((p) => Number(p.nav));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 760;
  const height = 280;
  const pad = 20;
  const xStep = (width - pad * 2) / (series.length - 1);
  const yScale = (height - pad * 2) / Math.max(max - min, 1e-9);

  const points = series
    .map((p, idx) => {
      const x = pad + idx * xStep;
      const y = height - pad - (Number(p.nav) - min) * yScale;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const baseY = height - pad;
  const firstX = pad;
  const lastX = pad + (series.length - 1) * xStep;
  const areaPath = `M ${firstX},${baseY} L ${points} L ${lastX},${baseY} Z`;

  const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
  area.setAttribute("d", areaPath);
  area.setAttribute("fill", "rgba(17,17,17,0.07)");

  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", points);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#111111");
  line.setAttribute("stroke-width", "2");
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("stroke-linejoin", "round");

  equityChart.appendChild(area);
  equityChart.appendChild(line);
}

function hideClarifyPanel() {
  if (!clarifyPanel) return;
  clarifyPanel.classList.add("hidden");
  if (clarifyQuestion) clarifyQuestion.textContent = "";
  if (clarifyMissing) clarifyMissing.innerHTML = "";
}

function setActiveThread(target) {
  threadItems.forEach((item) => item.classList.remove("active"));
  if (target) target.classList.add("active");
}

function showClarifyPanel(question, missingFields) {
  if (!clarifyPanel) return;
  clarifyPanel.classList.remove("hidden");
  lastClarificationQuestion = question || "需要补充关键信息。";
  if (clarifyQuestion) clarifyQuestion.textContent = lastClarificationQuestion;
  if (clarifyMissing) clarifyMissing.innerHTML = "";
  if (Array.isArray(missingFields)) {
    for (const field of missingFields) {
      const chip = document.createElement("span");
      chip.className = "field-chip";
      chip.textContent = field;
      if (clarifyMissing) clarifyMissing.appendChild(chip);
    }
  }
}

function renderResult(payload) {
  stopTraceLoading();
  renderToolTraceFromPayload(payload);
  const data = payload?.data || null;
  const status = payload?.status || (payload?.ok ? "completed" : "error");
  setBadge(status);

  if (!payload?.ok) {
    hideClarifyPanel();
    safeText(summaryBox, payload?.message || "执行失败");
    safeText(statusLine, `状态：失败 (${payload?.error_code || "unknown"})`);
    safeText(riskBox, "请检查输入策略描述，或稍后重试。");
    renderMetrics(null);
    renderChart([]);
    renderYearly([]);
    pushTurn("agent", payload?.message || "执行失败", "error");
    return;
  }

  if (status === "needs_clarification") {
    const question = data?.clarification?.next_question || "需要补充条件。";
    const missingFields = data?.validation?.missing_fields || data?.clarification?.must_ask_fields || [];
    showClarifyPanel(question, missingFields);
    safeText(summaryBox, `需要澄清：${question}`);
    safeText(statusLine, "状态：等待补充条件");
    safeText(riskBox, "当前未执行回测。请先补全关键信息。");
    if (queryInput) {
      queryInput.value = "";
      queryInput.placeholder = "直接在这里回复补充信息，例如：用 510300.SH，MACD 参数 12/26/9";
      queryInput.focus();
    }
    renderMetrics(null);
    renderChart([]);
    renderYearly([]);
    pushTurn("agent", question, "needs_clarification");
    return;
  }

  if (status !== "completed") {
    hideClarifyPanel();
    const assistantText = status === "blocked_missing_equity_curve"
      ? "结果页缺少收益曲线，Agent 会继续补全后再标记完成。"
      : (payload?.assistant_message || "Agent 已响应，但尚未产出可执行回测结果。");
    safeText(summaryBox, assistantText);
    safeText(statusLine, `状态：${status}`);
    safeText(riskBox, "可继续补充问题细节，Agent 会基于同一 session 继续多轮对话。");
    renderMetrics(null);
    renderChart([]);
    renderYearly([]);
    pushTurn("agent", assistantText, status);
    return;
  }

  hideClarifyPanel();
  const summary = data?.result_page?.summary || {};
  const summaryText = summary.summary_text || "回测完成。";
  const strategyName = summary.strategy_name || "未命名策略";
  safeText(summaryBox, `${strategyName}：${summaryText}`);
  safeText(statusLine, "状态：回测完成");

  const metrics = data?.metrics || null;
  renderMetrics(metrics);
  renderChart(data?.result_page?.equity_curve?.series || []);
  renderYearly(metrics?.period_breakdown?.yearly_returns || []);

  const risks = data?.result_page?.risk_disclosures || [];
  safeText(riskBox, risks.length ? risks.join("；") : (summary.risk_text || "回测结果不代表未来表现。"));
  pushTurn("agent", `${strategyName} 回测完成。`, "completed");
}

async function runResearch(queryOverride = null, options = {}) {
  const { logUser = true, userMeta = "submit" } = options;
  const query = (queryOverride ?? queryInput.value).trim();
  if (!query) {
    safeText(statusLine, "状态：请输入研究问题");
    return;
  }
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.textContent = "…";
  }
  safeText(statusLine, "状态：提交请求中...");
  startTraceLoading();
  try {
    lastSubmittedQuery = query;
    if (logUser) {
      pushTurn("user", query, userMeta);
    }
    const res = await fetch("/research/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, user_id: "web-user", session_id: "ui-session" }),
    });
    const payload = await res.json();
    renderResult(payload);
  } catch (err) {
    stopTraceLoading();
    renderTraceItems([{ name: "Network / API", label: "error", state: "error" }]);
    setBadge("error");
    safeText(summaryBox, "网络请求失败，请检查服务状态。");
    safeText(statusLine, `状态：请求异常 (${String(err)})`);
    safeText(riskBox, "请确认 API 服务已启动并可访问。");
  } finally {
    stopTraceLoading();
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.textContent = "↑";
    }
  }
}

async function continueWithClarification() {
  const addition = queryInput.value.trim();
  if (!addition) {
    safeText(statusLine, "状态：请先填写补充条件");
    return;
  }
  const continueMessage = `补充信息：${addition}`;
  queryInput.value = `${(lastSubmittedQuery || queryInput.value).trim()}\n\n${continueMessage}`;
  safeText(statusLine, "状态：已发送补充信息，继续多轮会话中...");
  pushTurn("user", continueMessage, "clarification");
  await runResearch(continueMessage, { logUser: false });
}

if (runBtn) runBtn.addEventListener("click", () => runResearch());
if (exampleBtn) {
  exampleBtn.addEventListener("click", () => {
    chatTurns = [];
    renderTimeline();
    renderTraceItems([]);
    safeText(statusLine, "状态：旧会话已归档到本地展示区");
    hideClarifyPanel();
  });
}
threadItems.forEach((item) => {
  item.addEventListener("click", () => {
    const query = item.dataset.query || examples[exampleIndex % examples.length];
    if (queryInput) queryInput.value = query;
    if (queryInput) queryInput.placeholder = "例如：帮我验证一个策略，每月买入成交额最大的20只股票，每月调仓一次";
    setActiveThread(item);
    safeText(statusLine, "状态：已选择示例，可直接运行");
    hideClarifyPanel();
  });
});
if (clearChatBtn) {
  clearChatBtn.addEventListener("click", () => {
    chatTurns = [];
    renderTimeline();
    renderTraceItems([]);
    safeText(statusLine, "状态：已创建新的本地会话视图");
  });
}

if (queryInput) queryInput.value = examples[0];
hideClarifyPanel();
renderTimeline();
renderTraceItems([]);
safeText(statusLine, "状态：前端已加载，输入问题后点击箭头发送");

window.addEventListener("error", (event) => {
  safeText(statusLine, `状态：前端脚本异常 (${event.message})`);
});
