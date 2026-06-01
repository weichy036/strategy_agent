import { els, safeText, setBadge, setStatus } from "./dom.js?v=49";
import { updateLastAgentResult, updateLastAgentTrace, updateLastAgentTurn } from "./chat_view.js?v=49";
import { mergeLiveTrace, stopTraceLoading, traceItemsFromPayload } from "./trace_view.js?v=49";
import { renderChart, renderMetrics, renderYearly } from "./result_widgets.js?v=49";

export function resetHomeView(statusText = "输入问题后点击箭头发送") {
  hideClarifyPanel();
  renderInsights([]);
  renderMetrics(null);
  renderChart([]);
  renderYearly([]);
  safeText(els.riskBox, "");
  clearSummary();
  setBadge("未运行");
  setStatus(statusText);
}

export function renderResult(rawPayload) {
  stopTraceLoading();
  const payload = mergeLiveTrace(rawPayload || {});
  updateLastAgentTrace(traceItemsFromPayload(payload));

  const data = payload?.data || null;
  const status = payload?.status || (payload?.ok ? "completed" : "error");
  setBadge(status);

  if (!payload?.ok) return renderError(payload);
  if (status === "needs_clarification") return renderClarification(data);
  if (status === "answered") return renderAnswered(data);
  if (status === "blocked_missing_data") return renderMissingData(data);
  if (status !== "completed") return renderUnfinished(payload, status);
  return renderCompleted(data);
}

export function renderNetworkError(error) {
  stopTraceLoading();
  updateLastAgentTrace([{ name: "Network / API", label: "error", state: "error" }]);
  setBadge("error");
  safeText(els.summaryBox, "网络请求失败，请检查服务状态。");
  setStatus(`请求异常 (${String(error)})`);
  safeText(els.riskBox, "请确认 API 服务已启动并可访问。");
  updateLastAgentTurn("网络请求失败，请检查服务状态。", "error");
}

function clearSummary() {
  if (!els.summaryBox) return;
  els.summaryBox.classList.remove("empty-state");
  els.summaryBox.textContent = "";
}

function renderError(payload) {
  hideClarifyPanel();
  clearResultPanels();
  renderInsights([]);
  safeText(els.summaryBox, payload?.message || "执行失败");
  setStatus(`失败 (${payload?.error_code || "unknown"})`);
  safeText(els.riskBox, "请检查输入策略描述，或稍后重试。");
  updateLastAgentTurn(payload?.message || "执行失败", "error");
}

function renderClarification(data) {
  const question = data?.clarification?.next_question || "需要补充条件。";
  const missingFields = data?.validation?.missing_fields || data?.clarification?.must_ask_fields || [];
  showClarifyPanel(question, missingFields);
  clearResultPanels();
  renderInsights([{ title: "为什么需要补充", value: "缺少会影响回测含义的关键条件。" }]);
  safeText(els.summaryBox, `需要澄清：${question}`);
  setStatus("等待补充条件");
  safeText(els.riskBox, "当前未执行回测。请先补全关键信息。");
  prepareClarifyInput();
  updateLastAgentTurn("需要补充信息", "needs_clarification");
  updateLastAgentResult("needs_clarification", data);
}

function renderUnfinished(payload, status) {
  const assistantText = status === "blocked_missing_equity_curve"
    ? "结果页缺少收益曲线，Agent 会继续补全后再标记完成。"
    : (payload?.assistant_message || "Agent 已响应，但尚未产出可执行回测结果。");
  hideClarifyPanel();
  clearResultPanels();
  renderInsights([]);
  safeText(els.summaryBox, assistantText);
  setStatus(status);
  safeText(els.riskBox, "可继续补充问题细节，Agent 会基于同一 session 继续多轮对话。");
  updateLastAgentTurn(assistantText, status);
}

function renderAnswered(data) {
  const explanations = data?.explanations || {};
  hideClarifyPanel();
  clearResultPanels();
  renderInsights(renderSuggestionInsights(explanations));
  safeText(els.summaryBox, explanations.summary_text || "Agent 已回答。");
  setStatus("已回答");
  safeText(els.riskBox, [explanations.risk_text, explanations.limitations_text].filter(Boolean).join(" "));
  updateLastAgentTurn(explanations.summary_text || "Agent 已回答。", "answered");
  updateLastAgentResult("answered", data);
}

function renderMissingData(data) {
  const report = data?.data_availability || {};
  const issues = Array.isArray(report.blocking_issues) ? report.blocking_issues : [];
  const plans = Array.isArray(report.fetch_plan) ? report.fetch_plan : [];
  hideClarifyPanel();
  clearResultPanels();
  renderInsights([
    { title: "数据状态", value: "本地数据不足，未执行回测。" },
    { title: "建议接口", value: plans.length ? plans.map((item) => item.api_name).join("、") : "暂无补数计划" },
  ]);
  safeText(els.summaryBox, `数据暂未就绪：${issues.join("；") || report.rationale || "缺少本地数据。"}`);
  setStatus("等待补齐数据");
  safeText(els.riskBox, plans.length
    ? `建议补数接口：${plans.map((item) => item.api_name).join("、")}`
    : "当前未执行回测。请先补齐本地数据后再运行。");
  updateLastAgentTurn("本地数据暂未就绪，已生成补数计划。", "blocked_missing_data");
  updateLastAgentResult("blocked_missing_data", data);
}

function renderCompleted(data) {
  const summary = data?.result_page?.summary || {};
  const strategyName = summary.strategy_name || "策略";
  hideClarifyPanel();
  els.summaryBox.classList.remove("empty-state");
  safeText(els.summaryBox, summary.summary_text || `${strategyName} 回测完成。`);
  setStatus("回测完成");
  renderInsights(renderCompletedInsights(data));
  renderMetrics(data?.metrics || null);
  renderChart(data?.result_page?.equity_curve || []);
  renderYearly(data?.metrics?.period_breakdown?.yearly_returns || []);
  renderRisks(data, summary);
  updateLastAgentTurn(`${strategyName} 回测完成。`, "completed");
  updateLastAgentResult("completed", data);
}

function clearResultPanels() {
  els.summaryBox.classList.remove("empty-state");
  renderInsights([]);
  renderMetrics(null);
  renderChart([]);
  renderYearly([]);
}

function renderCompletedInsights(data) {
  const schema = data?.strategy_schema || {};
  const availability = data?.data_availability || {};
  const required = Array.isArray(availability.required_datasets)
    ? availability.required_datasets.map((item) => item.dataset).join("、")
    : "";
  const universe = schema?.universe?.symbols?.length ? schema.universe.symbols.join("、") : schema?.universe?.type || "未识别";
  return [
    { title: "交易标的", value: universe },
    { title: "数据检查", value: availability.is_ready ? `已就绪${required ? `（${required}）` : ""}` : "未就绪" },
    { title: "执行口径", value: "信号次日开盘成交，历史回测不代表未来。" },
  ];
}

function renderSuggestionInsights(explanations) {
  const suggestions = Array.isArray(explanations.follow_up_suggestions) ? explanations.follow_up_suggestions : [];
  return suggestions.slice(0, 3).map((value, index) => ({ title: `继续追问 ${index + 1}`, value }));
}

function renderInsights(items) {
  if (!els.insightGrid) return;
  els.insightGrid.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    els.insightGrid.classList.add("hidden");
    return;
  }
  els.insightGrid.classList.remove("hidden");
  for (const item of items) {
    const card = document.createElement("div");
    card.className = "insight-card";
    const title = document.createElement("div");
    title.className = "insight-title";
    title.textContent = item.title;
    const value = document.createElement("div");
    value.className = "insight-value";
    value.textContent = item.value;
    card.append(title, value);
    els.insightGrid.appendChild(card);
  }
}

function renderRisks(data, summary) {
  const risks = data?.result_page?.risk_disclosures || [];
  safeText(els.riskBox, risks.length ? risks.join("；") : (summary.risk_text || "回测结果不代表未来表现。"));
}

function prepareClarifyInput() {
  if (!els.queryInput) return;
  els.queryInput.value = "";
  els.queryInput.placeholder = "直接在这里回复补充信息，例如：用 510300.SH，MACD 参数 12/26/9";
  els.queryInput.focus();
}

function hideClarifyPanel() {
  els.clarifyPanel?.classList.add("hidden");
  safeText(els.clarifyQuestion, "");
  if (els.clarifyMissing) els.clarifyMissing.innerHTML = "";
}

function showClarifyPanel(question, missingFields) {
  els.clarifyPanel?.classList.remove("hidden");
  safeText(els.clarifyQuestion, question || "需要补充关键信息。");
  if (els.clarifyMissing) els.clarifyMissing.innerHTML = "";
  if (!Array.isArray(missingFields)) return;
  for (const field of missingFields) {
    const chip = document.createElement("span");
    chip.className = "field-chip";
    chip.textContent = field;
    els.clarifyMissing?.appendChild(chip);
  }
}
