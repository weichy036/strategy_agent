import { els, setStatus } from "./dom.js?v=49";

let traceTimer = null;
let liveTraceItems = [];

export function startTraceLoading(onChange = null) {
  stopTraceLoading();
  liveTraceItems = [];
  const steps = loadingSteps();
  let tick = 0;
  renderTraceItems(steps);
  onChange?.(steps);
  traceTimer = setInterval(() => {
    tick += 1;
    markLoadingStep(steps, Math.min(Math.floor(tick / 2), steps.length - 1));
    renderTraceItems(steps);
    onChange?.(steps);
  }, 650);
}

export function stopTraceLoading() {
  if (!traceTimer) return;
  clearInterval(traceTimer);
  traceTimer = null;
}

export function addLiveTraceItems(items) {
  stopTraceLoading();
  liveTraceItems = mergeTraceItems(liveTraceItems, items || []);
  setStatus("Agent 正在执行...");
  return traceItemsFromPayload({ timeline: liveTraceItems });
}

export function renderToolTraceFromPayload(payload) {
  const items = traceItemsFromPayload(payload);
  renderTraceItems(items);
  return items;
}

export function traceItemsFromPayload(payload) {
  const timeline = cleanTimeline(Array.isArray(payload?.timeline) ? payload.timeline : [], payload);
  if (timeline.length > 0) return timeline.map(toTraceItem);

  const calls = Array.isArray(payload?.tool_calls) ? payload.tool_calls : [];
  if (calls.length === 0) return [];
  return calls.map(toToolCallItem);
}

function cleanTimeline(timeline, payload) {
  if (payload?.status === "completed") {
    return timeline.filter((item) => item.event_type !== "agent_output_parse_failed");
  }
  if (payload?.status !== "answered") return timeline;
  return timeline.filter((item) => {
    if (item.event_type === "agent_output_parse_failed") return false;
    return true;
  });
}

export function mergeLiveTrace(payload) {
  if (liveTraceItems.length === 0 || !Array.isArray(payload?.timeline)) return payload;
  return { ...payload, timeline: mergeTraceItems(liveTraceItems, payload.timeline) };
}

export function renderTraceItems(items) {
  if (!els.traceList) return;
  els.traceList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) return renderEmptyTrace();

  els.traceWrap?.classList.remove("hidden");
  if (els.traceWrap) els.traceWrap.open = true;
  for (const item of items) {
    els.traceList.appendChild(createTraceRow(item));
  }
}

export function createTracePanel(items) {
  const wrap = document.createElement("details");
  wrap.className = "turn-trace";
  wrap.open = true;
  const summary = document.createElement("summary");
  summary.textContent = "Agent 执行轨迹";
  const list = document.createElement("div");
  list.className = "trace-list";
  for (const item of items || []) {
    list.appendChild(createTraceRow(item));
  }
  wrap.append(summary, list);
  return wrap;
}

function loadingSteps() {
  return [
    { name: "Intent / Clarification", label: "running", state: "running" },
    { name: "Strategy Schema", label: "waiting", state: "idle" },
    { name: "Data Check", label: "waiting", state: "idle" },
    { name: "Backtest Engine", label: "waiting", state: "idle" },
    { name: "Metrics / Report", label: "waiting", state: "idle" },
  ];
}

function markLoadingStep(steps, active) {
  steps.forEach((step, idx) => {
    step.label = idx < active ? "success" : idx === active ? "running" : "waiting";
    step.state = idx < active ? "success" : idx === active ? "running" : "idle";
  });
}

function renderEmptyTrace() {
  els.traceWrap?.classList.add("hidden");
  els.traceList.innerHTML = `<div class="trace-item"><span class="trace-name">本轮尚无工具轨迹</span><span class="trace-state">idle</span></div>`;
}

function createTraceRow(item) {
  const state = item.state || item.status;
  const stateClass = state === "success" ? "success" : state === "error" ? "error" : state === "running" ? "running" : "";
  const row = document.createElement("div");
  row.className = `trace-item ${stateClass}`;
  row.innerHTML = `
    <span class="trace-name">${displayTraceName(item.name || item.actor || item.stage || "Agent")}${item.message ? ` · ${item.message}` : ""}</span>
    <span class="trace-state ${stateClass}">${displayTraceState(item.label || item.status || "done")}</span>
  `;
  return row;
}

function toTraceItem(item) {
  return {
    name: item.actor || item.stage,
    label: item.status || "done",
    state: item.status || "idle",
    message: item.message || "",
  };
}

function toToolCallItem(call) {
  const ok = call?.payload?.ok;
  return {
    name: call?.name || "unknown_tool",
    label: ok === true ? "success" : ok === false ? "error" : "done",
    state: ok === true ? "success" : ok === false ? "error" : "idle",
  };
}

function mergeTraceItems(left, right) {
  const merged = [];
  const seen = new Set();
  for (const item of [...left, ...right]) {
    const key = [item.event_type || "", item.actor || item.name || "", item.message || "", item.timestamp || ""].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

function displayTraceName(name) {
  const map = {
    IntentClassifierAgent: "意图分类 Agent",
    ClarificationAgent: "澄清判断 Agent",
    StrategyDesignerAgent: "策略设计 Agent",
    DataResearchAgent: "数据研究 Agent",
    ResultExplanationAgent: "结果解释 Agent",
    validate_strategy_schema: "校验策略结构",
    resolve_instrument_tool: "识别交易标的",
    query_market_data: "读取行情数据",
    run_backtest: "执行回测",
    compute_metrics: "计算指标",
    assemble_result_page: "生成结果页",
    store_artifact: "保存研究产物",
  };
  return map[name] || name;
}

function displayTraceState(state) {
  const map = { running: "执行中", waiting: "等待", success: "完成", done: "完成", error: "异常", idle: "空闲" };
  return map[state] || state;
}
