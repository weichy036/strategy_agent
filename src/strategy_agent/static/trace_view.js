import { els, setStatus } from "./dom.js?v=52";

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

export function createTracePanel(items, completed = false) {
  const wrap = document.createElement("details");
  wrap.className = "turn-trace";
  wrap.open = true;
  const summary = document.createElement("summary");
  summary.textContent = processTitle(items || [], completed);
  const list = document.createElement("div");
  list.className = "process-list";
  for (const item of processItems(items || [])) {
    list.appendChild(createProcessRow(item));
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
    event_type: item.event_type || "",
    name: item.actor || item.stage,
    stage: item.stage || item.actor || "",
    label: item.status || "done",
    state: item.status || "idle",
    message: item.message || "",
    timestamp: item.timestamp || "",
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

function processTitle(items, completed = false) {
  const elapsed = elapsedText(items);
  if (completed) return elapsed ? `已处理 ${elapsed}` : "已处理";
  const hasRunning = items.some((item) => item.state === "running" || item.status === "running");
  if (hasRunning) return elapsed ? `处理中 ${elapsed}` : "处理中";
  return elapsed ? `已处理 ${elapsed}` : "已处理";
}

function processItems(items) {
  const seen = new Set();
  return items
    .filter((item) => {
      const type = item.event_type || "";
      if (type === "narration" || type === "agent_output_parsed" || type === "adk_error") return true;
      if (type !== "tool_start" && type !== "tool_done") return false;
      return isUserFacingTool(item.stage || item.name || item.actor || "");
    })
    .filter((item) => {
      if ((item.event_type || "") === "narration") return true;
      const key = [item.event_type || "", item.stage || item.name || item.actor || "", item.status || item.state || ""].join("|");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 28);
}

function isUserFacingTool(name) {
  return new Set([
    "validate_strategy_schema",
    "query_market_data",
    "run_backtest",
    "compute_metrics",
    "assemble_result_page",
  ]).has(name);
}

function createProcessRow(item) {
  const type = item.event_type || "";
  const row = document.createElement("div");
  if (type === "narration") {
    row.className = "process-narration";
    row.textContent = item.message || "";
    return row;
  }

  const state = item.state || item.status || "done";
  const stateClass = state === "success" ? "success" : state === "error" ? "error" : state === "running" ? "running" : "";
  row.className = `process-event ${stateClass}`;
  const label = document.createElement("span");
  label.textContent = processEventText(item);
  const status = document.createElement("span");
  status.className = `trace-state ${stateClass}`;
  status.textContent = displayTraceState(item.label || item.status || "done");
  row.append(label, status);
  return row;
}

function processEventText(item) {
  const type = item.event_type || "";
  const name = displayTraceName(item.stage || item.name || item.actor || "Agent");
  if (type === "tool_start") return `正在调用 ${name}`;
  if (type === "tool_done") return `已完成 ${name}`;
  if (type === "agent_output_parsed") return `已完成 ${name}`;
  if (type === "adk_error") return item.message || "执行异常";
  return item.message || name;
}

function elapsedText(items) {
  const stamps = items.map((item) => item.timestamp).filter(Boolean);
  if (stamps.length < 2) return "";
  const start = Date.parse(stamps[0]);
  const end = Date.parse(stamps[stamps.length - 1]);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return "";
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
