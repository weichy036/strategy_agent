import { DEFAULT_QUERY, els, setStatus } from "./dom.js?v=52";
import { renderTraceDashboard } from "./trace_dashboard.js?v=52";
import { createTracePanel } from "./trace_view.js?v=52";
import { createTurnResult } from "./turn_result_view.js?v=52";

let chatTurns = [];

export function resetChat() {
  chatTurns = [];
  renderTimeline();
}

export function pushTurn(role, text, meta = "") {
  if (!text) return;
  chatTurns.push({ role, text, meta, ts: nowTimeLabel(), trace: [] });
  renderTimeline();
}

export function updateLastAgentTrace(trace) {
  const turn = [...chatTurns].reverse().find((item) => item.role === "agent");
  if (!turn) return;
  turn.trace = trace || [];
  renderTimeline();
}

export function updateLastAgentTurn(text, meta = "") {
  const turn = [...chatTurns].reverse().find((item) => item.role === "agent");
  if (!turn) {
    pushTurn("agent", text, meta);
    return;
  }
  turn.text = text || turn.text;
  turn.meta = meta || turn.meta;
  renderTimeline();
}

export function updateLastAgentMeta(meta = "") {
  const turn = [...chatTurns].reverse().find((item) => item.role === "agent");
  if (!turn) return;
  turn.meta = meta || turn.meta;
  renderTimeline();
}

export function updateLastAgentResult(status, data) {
  const turn = [...chatTurns].reverse().find((item) => item.role === "agent");
  if (!turn) return;
  turn.result = { status, data };
  renderTimeline();
}

export function setChatTurns(turns) {
  chatTurns = (turns || [])
    .filter((turn) => turn?.text)
    .map((turn) => ({
      role: turn.role === "agent" ? "agent" : "user",
      text: turn.text,
      meta: turn.status || "history",
      ts: turn.timestamp ? timeLabelFromSeconds(turn.timestamp) : "",
      trace: Array.isArray(turn.timeline) ? turn.timeline : [],
      result: turn.role === "agent" && turn.data ? { status: turn.status, data: turn.data } : null,
    }));
  renderTimeline();
}

function setActiveThread(target) {
  els.threadItems.forEach((item) => item.classList.remove("active"));
  if (target) target.classList.add("active");
}

export function fillThreadQuery(item) {
  if (!els.queryInput) return;
  els.queryInput.value = item.dataset.query || DEFAULT_QUERY;
  els.queryInput.placeholder = "例如：帮我验证一个策略，每月买入成交额最大的20只股票，每月调仓一次";
  setActiveThread(item);
  setStatus("已选择示例，可直接运行");
}

function renderTimeline() {
  renderTraceDashboard(chatTurns);
  if (!els.chatTimeline) return;
  els.chatTimeline.innerHTML = "";
  if (chatTurns.length === 0) {
    els.chatStrip?.classList.add("hidden");
    return;
  }
  if (els.traceBoard?.classList.contains("hidden")) {
    els.chatStrip?.classList.remove("hidden");
  } else {
    els.chatStrip?.classList.add("hidden");
  }
  for (const turn of chatTurns) {
    els.chatTimeline.appendChild(createBubble(turn));
  }
  els.chatTimeline.scrollTop = els.chatTimeline.scrollHeight;
}

function createBubble(turn) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${turn.role}`;
  if (turn.meta === "running" || String(turn.meta).includes("已处理")) {
    bubble.classList.add("is-running");
  }

  const body = document.createElement("div");
  body.className = "bubble-body";
  body.textContent = turn.text;
  bubble.appendChild(body);

  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  meta.textContent = `${turn.role === "user" ? "用户" : "Agent"} · ${turn.ts}${turn.meta ? ` · ${turn.meta}` : ""}`;
  bubble.appendChild(meta);
  if (turn.trace?.length) {
    const tracePanel = createTracePanel(turn.trace, Boolean(turn.result));
    if (turn.result) tracePanel.open = false;
    bubble.appendChild(tracePanel);
  }
  if (turn.result) {
    const result = createTurnResult(turn.result.status, turn.result.data);
    if (result) bubble.appendChild(result);
  }
  return bubble;
}

function nowTimeLabel() {
  const d = new Date();
  return timeLabel(d);
}

function timeLabelFromSeconds(seconds) {
  return timeLabel(new Date(seconds * 1000));
}

function timeLabel(d) {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}
