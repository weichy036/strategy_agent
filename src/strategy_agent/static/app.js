import { createLocalSession, deleteSession, getActiveSession, loadSessionHistory, setActiveSession } from "./api.js?v=62";
import { runResearchFallback, streamResearchRequest } from "./api.js?v=62";
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
} from "./render.js?v=62";
import { showTraceBoard } from "./trace_dashboard.js?v=62";

let runTimer = null;
const THREADS_KEY = "tradex.threads";

async function runResearch() {
  const query = els.queryInput.value.trim();
  if (!query) return setStatus("请输入研究问题");

  upsertThread(getActiveSession(), titleFromQuery(query), query);
  renderThreadList(getActiveSession());
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
  els.clearChatBtn?.addEventListener("click", () => {
    const sessionId = createLocalSession();
    upsertThread(sessionId, "新会话", "");
    renderThreadList(sessionId);
    resetChat();
    if (els.queryInput) els.queryInput.value = "";
    resetHomeView("已创建新的本地会话视图");
  });
  els.threadList?.addEventListener("click", (event) => {
    const menuButton = event.target.closest(".thread-menu-button");
    if (menuButton) {
      event.stopPropagation();
      toggleThreadMenu(menuButton.closest(".thread-item"));
      return;
    }
    const deleteButton = event.target.closest(".thread-delete");
    if (deleteButton) {
      event.stopPropagation();
      deleteThread(deleteButton.closest(".thread-item"));
      return;
    }
    const item = event.target.closest(".thread-item");
    if (item) selectThread(item);
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".thread-item")) closeThreadMenus();
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
  renderThreadList(getActiveSession());
  if (els.queryInput) els.queryInput.value = DEFAULT_QUERY;
  resetChat();
  resetHomeView();
  bindEvents();
  const active = document.querySelector(`[data-session-id="${getActiveSession()}"]`) || document.querySelector(".thread-item.active");
  if (active?.dataset.sessionId) {
    setActiveSession(active.dataset.sessionId);
    await selectThread(active);
  } else {
    await loadActiveSessionHistory();
  }
}


function renderThreadList(activeSessionId) {
  if (!els.threadList) return;
  const threads = readThreads();
  els.threadList.innerHTML = "";
  for (const thread of threads) {
    const item = document.createElement("div");
    item.className = `thread-item ${thread.session_id === activeSessionId ? "active" : ""}`;
    item.role = "button";
    item.tabIndex = 0;
    item.dataset.sessionId = thread.session_id;
    item.dataset.query = thread.query || "";
    item.innerHTML = `
      <span class="thread-title">${escapeHtml(thread.title || "未命名会话")}</span>
      <button class="thread-menu-button" type="button" aria-label="会话操作">...</button>
      <div class="thread-menu" role="menu">
        <button class="thread-delete" type="button" role="menuitem">删除</button>
      </div>
    `;
    els.threadList.append(item);
  }
}


function readThreads() {
  try {
    const stored = JSON.parse(localStorage.getItem(THREADS_KEY) || "[]");
    if (Array.isArray(stored) && stored.length) {
      return stored.map((thread) => ({
        ...thread,
        title: titleFromQuery(thread.query || thread.title),
      }));
    }
  } catch {
    // Ignore broken localStorage; the static examples below are enough to recover.
  }
  return staticThreads();
}


function writeThreads(threads) {
  localStorage.setItem(THREADS_KEY, JSON.stringify(threads.slice(0, 30)));
}


function upsertThread(sessionId, title, query) {
  const threads = readThreads().filter((item) => item.session_id !== sessionId);
  threads.unshift({ session_id: sessionId, title, query });
  writeThreads(threads);
}


async function deleteThread(item) {
  if (!item?.dataset.sessionId) return;
  const sessionId = item.dataset.sessionId;
  const title = item.querySelector(".thread-title")?.textContent?.trim() || "这个会话";
  if (!confirm(`删除「${title}」？历史记录将不可恢复。`)) return;

  const remaining = readThreads().filter((thread) => thread.session_id !== sessionId);
  writeThreads(remaining);
  if (sessionId === getActiveSession()) {
    await switchAfterDelete(remaining);
  } else {
    renderThreadList(getActiveSession());
  }

  try {
    await deleteSession(sessionId);
  } catch (error) {
    setStatus(`本地已移除，服务端删除失败 (${error.message})`);
  }
}


async function switchAfterDelete(remaining) {
  const next = remaining[0];
  if (next?.session_id) {
    setActiveSession(next.session_id);
    renderThreadList(next.session_id);
    const active = document.querySelector(`[data-session-id="${next.session_id}"]`);
    if (active) await selectThread(active);
    return;
  }
  const sessionId = createLocalSession();
  upsertThread(sessionId, "新会话", "");
  renderThreadList(sessionId);
  resetChat();
  if (els.queryInput) els.queryInput.value = "";
  resetHomeView("已删除旧会话，并创建新的空会话");
}


function toggleThreadMenu(item) {
  if (!item) return;
  const shouldOpen = !item.classList.contains("menu-open");
  closeThreadMenus();
  if (shouldOpen) item.classList.add("menu-open");
}


function closeThreadMenus() {
  document.querySelectorAll(".thread-item.menu-open").forEach((item) => item.classList.remove("menu-open"));
}


function staticThreads() {
  return Array.from(document.querySelectorAll(".thread-item")).map((item) => ({
    session_id: item.dataset.sessionId,
    title: titleFromQuery(item.dataset.query || (item.querySelector(".thread-title") || item).textContent),
    query: item.dataset.query || "",
  })).filter((item) => item.session_id);
}


async function loadActiveSessionHistory() {
  resetHomeView("正在加载线程上下文...");
  try {
    const history = await loadSessionHistory();
    setChatTurns(history.turns || []);
    resetHomeView(history.turns?.length ? "已加载线程上下文" : "此线程暂无历史对话");
  } catch (error) {
    resetHomeView(`线程上下文加载失败 (${error.message})`);
  }
}


function titleFromQuery(query) {
  const compact = cleanTitleText(query);
  if (!compact) return "新会话";

  const top = topLabel(compact);
  const instrument = instrumentLabel(compact);
  if (/MACD/i.test(compact)) return shortTitle(`${instrument || ""}MACD`);
  if (/RSI/i.test(compact)) return shortTitle(`${instrument || ""}RSI`);
  if (/均线|MA\s*\d+/i.test(compact)) return shortTitle(`${instrument || ""}均线`);
  if (/成交额|成交金额|成交量/.test(compact)) return shortTitle(`成交额${top}`);
  if (/市值/.test(compact)) return shortTitle(`市值${top}`);
  if (/涨幅|涨跌幅/.test(compact)) return shortTitle(`涨幅${top}`);
  if (/回撤/.test(compact)) return shortTitle(`${instrument || ""}回撤`);

  return shortTitle(compact);
}


function cleanTitleText(value) {
  return String(value || "")
    .replace(/\s+/g, "")
    .replace(/[，。！？、：:；;（）()【】[\]“”"']/g, "")
    .replace(/^(帮我)?(验证|回测|测试|看下|看一下|分析|介绍)(一个)?(策略)?/, "")
    .replace(/^(对于|如果|请问)/, "")
    .replace(/(每年的平均收益是多少|回测一下收益|回测一下效果|回测一下|效果怎么样|表现如何|收益是多少)$/g, "")
    .trim();
}


function topLabel(text) {
  const match = text.match(/TOP\s*(\d+)/i) || text.match(/前?(\d+)只/);
  return match ? `TOP${match[1]}` : "TOP";
}


function instrumentLabel(text) {
  const known = [
    ["沪深300ETF", "沪深300"],
    ["中证500ETF", "中证500"],
    ["创业板ETF", "创业板"],
    ["阳光电源", "阳光电源"],
    ["宁德时代", "宁德时代"],
    ["证券ETF", "证券ETF"],
    ["红利ETF", "红利ETF"],
  ];
  const found = known.find(([name]) => text.includes(name));
  if (found) return found[1];

  const code = text.match(/\b\d{6}\.(?:SH|SZ|BJ)\b/i) || text.match(/\b\d{6}\b/);
  return code?.[0]?.toUpperCase() || "";
}


function shortTitle(value) {
  const title = String(value || "").replace(/\s+/g, "").trim();
  return title ? Array.from(title).slice(0, 10).join("") : "新会话";
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}


init();

window.addEventListener("error", (event) => {
  setStatus(`前端脚本异常 (${event.message})`);
});
