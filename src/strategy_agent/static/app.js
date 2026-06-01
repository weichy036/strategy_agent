import { createLocalSession, loadSessionHistory, setActiveSession } from "./api.js?v=52";
import { runResearchFallback, streamResearchRequest } from "./api.js?v=52";
import {
  DEFAULT_QUERY,
  addLiveTraceItems,
  els,
  fillThreadQuery,
  pushTurn,
  renderNetworkError,
  renderResult,
  resetChat,
  setChatTurns,
  updateLastAgentMeta,
  updateLastAgentTrace,
  resetHomeView,
  setSendLoading,
  setStatus,
  startTraceLoading,
  stopTraceLoading,
} from "./render.js?v=52";
import { showTraceBoard } from "./trace_dashboard.js?v=52";

let runTimer = null;

async function runResearch() {
  const query = els.queryInput.value.trim();
  if (!query) return setStatus("请输入研究问题");

  setSendLoading(true);
  setStatus("提交请求中...");
  pushTurn("user", query, "submit");
  clearQueryInput();
  pushTurn("agent", "Agent 正在分析...", "running");
  startRunTimer();
  startTraceLoading(updateLastAgentTrace);

  try {
    const payload = await streamResearchRequest(query, {
      onStarted: () => setStatus("Agent 已开始分析..."),
      onTimeline: (items) => updateLastAgentTrace(addLiveTraceItems(items)),
    });
    renderResult(payload);
  } catch (streamError) {
    await runWithFallback(query, streamError);
  } finally {
    stopRunTimer();
    stopTraceLoading();
    setSendLoading(false);
  }
}


function clearQueryInput() {
  if (!els.queryInput) return;
  els.queryInput.value = "";
  els.queryInput.style.height = "";
}

function startRunTimer() {
  stopRunTimer();
  const startedAt = Date.now();
  runTimer = setInterval(() => {
    const seconds = Math.max(1, Math.floor((Date.now() - startedAt) / 1000));
    updateLastAgentMeta(`已处理 ${seconds}s`);
    if (seconds < 8) setStatus("Agent 正在理解问题...");
    else if (seconds < 25) setStatus("Agent 正在设计策略和检查数据...");
    else setStatus("Agent 还在执行，复杂回测会稍慢...");
  }, 1000);
}

function stopRunTimer() {
  if (!runTimer) return;
  clearInterval(runTimer);
  runTimer = null;
}


async function runWithFallback(query, streamError) {
  try {
    renderResult(await runResearchFallback(query));
  } catch (fallbackError) {
    renderNetworkError(fallbackError || streamError);
  }
}


function bindEvents() {
  els.runBtn?.addEventListener("click", () => runResearch());
  els.chatTabBtn?.addEventListener("click", () => showTraceBoard(false));
  els.traceTabBtn?.addEventListener("click", () => showTraceBoard(true));
  els.exampleBtn?.addEventListener("click", () => {
    resetChat();
    resetHomeView("旧会话已归档到本地展示区");
  });
  els.clearChatBtn?.addEventListener("click", () => {
    setActiveSession(createLocalSession());
    resetChat();
    if (els.queryInput) els.queryInput.value = "";
    resetHomeView("已创建新的本地会话视图");
  });
  els.threadItems.forEach((item) => {
    item.addEventListener("click", () => selectThread(item));
  });
}


async function selectThread(item) {
  const sessionId = item.dataset.sessionId;
  if (sessionId) setActiveSession(sessionId);
  fillThreadQuery(item);
  resetHomeView("正在加载线程上下文...");
  showTraceBoard(false);
  try {
    const history = await loadSessionHistory();
    setChatTurns(history.turns || []);
    resetHomeView(history.turns?.length ? "已加载线程上下文" : "此线程暂无历史对话");
  } catch (error) {
    resetHomeView(`线程上下文加载失败 (${error.message})`);
  }
}


async function init() {
  if (els.queryInput) els.queryInput.value = DEFAULT_QUERY;
  resetChat();
  resetHomeView();
  bindEvents();
  const active = document.querySelector(".thread-item.active");
  if (active?.dataset.sessionId) {
    setActiveSession(active.dataset.sessionId);
    await selectThread(active);
  }
}


init();

window.addEventListener("error", (event) => {
  setStatus(`前端脚本异常 (${event.message})`);
});
