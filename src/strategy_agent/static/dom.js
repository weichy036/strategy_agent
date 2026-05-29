export const DEFAULT_QUERY = "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？";

export const els = {
  queryInput: document.getElementById("queryInput"),
  runBtn: document.getElementById("runBtn"),
  exampleBtn: document.getElementById("exampleBtn"),
  clearChatBtn: document.getElementById("clearChatBtn"),
  chatTabBtn: document.getElementById("chatTabBtn"),
  traceTabBtn: document.getElementById("traceTabBtn"),
  statusLine: document.getElementById("statusLine"),
  resultBadge: document.getElementById("resultBadge"),
  chatStrip: document.getElementById("chatStrip"),
  chatTimeline: document.getElementById("chatTimeline"),
  traceBoard: document.getElementById("traceBoard"),
  traceStats: document.getElementById("traceStats"),
  traceTurns: document.getElementById("traceTurns"),
  traceTokenSummary: document.getElementById("traceTokenSummary"),
  researchDoc: document.querySelector(".research-doc"),
  traceList: document.getElementById("traceList"),
  traceWrap: document.getElementById("traceWrap"),
  clarifyPanel: document.getElementById("clarifyPanel"),
  clarifyQuestion: document.getElementById("clarifyQuestion"),
  clarifyMissing: document.getElementById("clarifyMissing"),
  summaryBox: document.getElementById("summaryBox"),
  insightGrid: document.getElementById("insightGrid"),
  metricGrid: document.getElementById("metricGrid"),
  chartWrap: document.getElementById("chartWrap"),
  equityChart: document.getElementById("equityChart"),
  yearlyTableBody: document.querySelector("#yearlyTable tbody"),
  yearlyWrap: document.getElementById("yearlyWrap"),
  riskBox: document.getElementById("riskBox"),
  threadItems: document.querySelectorAll(".thread-item"),
};

export function setStatus(text) {
  safeText(els.statusLine, text);
}

export function setSendLoading(isLoading) {
  if (!els.runBtn) return;
  els.runBtn.disabled = isLoading;
  els.runBtn.textContent = isLoading ? "…" : "↑";
}

export function setBadge(status) {
  els.resultBadge.className = "badge";
  els.resultBadge.textContent = displayStatus(status || "未运行");
  if (status === "completed" || status === "answered") els.resultBadge.classList.add("success");
  else if (status === "needs_clarification" || status === "blocked_missing_data") els.resultBadge.classList.add("warn");
  else if (status && status !== "未运行") els.resultBadge.classList.add("error");
}

export function safeText(el, text) {
  if (el) el.textContent = text;
}

function displayStatus(status) {
  const map = {
    completed: "已处理",
    needs_clarification: "待补充",
    blocked_missing_data: "需补数据",
    answered: "已处理",
    error: "异常",
    "未运行": "未运行",
  };
  return map[status] || status;
}
