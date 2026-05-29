import { els } from "./dom.js?v=49";

let selectedRunId = null;

export function renderTraceDashboard(turns) {
  if (!els.traceBoard || !els.traceStats || !els.traceTurns) return;
  const runs = buildRuns(turns || []);
  const selected = pickSelectedRun(runs);

  els.traceTokenSummary.textContent = `${formatNumber(totalUsage(runs).total_tokens)} tokens`;
  renderStats(runs);
  renderRuns(runs, selected);
}

export function showTraceBoard(show) {
  els.traceBoard?.classList.toggle("hidden", !show);
  els.chatStrip?.classList.toggle("hidden", show);
  els.researchDoc?.classList.toggle("hidden", show);
  els.chatTabBtn?.classList.toggle("active", !show);
  els.traceTabBtn?.classList.toggle("active", show);
}

function renderStats(runs) {
  const usage = totalUsage(runs);
  const completed = runs.filter((run) => isOk(run.status)).length;
  const errorRate = runs.length ? ((runs.length - completed) / runs.length) * 100 : 0;
  const p95 = percentile(runs.map((run) => run.durationMs), 0.95);
  els.traceStats.innerHTML = "";
  [
    ["Runs", runs.length],
    ["Error rate", `${errorRate.toFixed(1)}%`],
    ["P95 latency", formatDuration(p95)],
    ["Tokens", formatNumber(usage.total_tokens)],
  ].forEach(([label, value]) => els.traceStats.appendChild(statCard(label, value)));
}

function renderRuns(runs, selected) {
  els.traceTurns.innerHTML = "";
  if (!runs.length) {
    els.traceTurns.appendChild(emptyState());
    return;
  }

  const shell = document.createElement("div");
  shell.className = "trace-console";
  shell.append(runList(runs, selected));
  shell.append(runDetail(selected));
  els.traceTurns.appendChild(shell);
}

function runList(runs, selected) {
  const root = document.createElement("aside");
  root.className = "trace-run-list";
  root.append(filterBar());
  for (const run of runs) {
    const button = document.createElement("button");
    button.className = `trace-run-item ${run.id === selected?.id ? "active" : ""}`;
    button.type = "button";
    button.dataset.runId = run.id;
    button.innerHTML = `
      <span class="trace-run-dot ${statusClass(run.status)}"></span>
      <div class="trace-run-main">
        <strong>${escapeHtml(run.title)}</strong>
        <span>${escapeHtml(short(run.input || run.output || "Agent run", 54))}</span>
        <small>${escapeHtml(run.model)} · ${run.spans.length} spans · ${formatNumber(run.usage.total_tokens)} tok</small>
      </div>
      <em>${formatDuration(run.durationMs)}</em>
    `;
    button.addEventListener("click", () => {
      selectedRunId = run.id;
      renderTraceDashboard(window.__TRADEX_TURNS__ || []);
    });
    root.append(button);
  }
  return root;
}

function filterBar() {
  const root = document.createElement("div");
  root.className = "trace-filter-bar";
  root.innerHTML = `
    <div class="trace-search">Search input, run id, status...</div>
    <span>agent <b>Any</b></span>
    <span>model <b>Any</b></span>
    <span>time <b>Session</b></span>
  `;
  return root;
}

function runDetail(run) {
  const root = document.createElement("section");
  root.className = "trace-run-detail";
  if (!run) {
    root.appendChild(emptyState());
    return root;
  }
  root.append(detailHeader(run));
  root.append(detailTabs(run));
  root.append(waterfall(run));
  root.append(detailSide(run));
  return root;
}

function detailHeader(run) {
  const root = document.createElement("div");
  root.className = "trace-detail-head";
  root.innerHTML = `
    <div class="trace-avatar">${escapeHtml(run.title.slice(0, 2).toUpperCase())}</div>
    <div class="trace-detail-title">
      <h3>${escapeHtml(run.input || run.output || "Agent run")}</h3>
      <p>run ${escapeHtml(run.id)} · thread ${escapeHtml(run.threadId)} · started ${escapeHtml(run.startedAt)}</p>
      <div class="trace-pills">
        <span class="${statusClass(run.status)}">${displayStatus(run.status)}</span>
        <span>${escapeHtml(run.model)}</span>
        <span>${formatDuration(run.durationMs)}</span>
        <span>${run.spans.length} spans</span>
        <span>${formatNumber(run.usage.total_tokens)} tok</span>
      </div>
    </div>
  `;
  return root;
}

function detailTabs(run) {
  const root = document.createElement("div");
  root.className = "trace-tabs";
  root.innerHTML = `
    <strong>Waterfall</strong>
    <span>${run.spans.length} spans</span>
    <span>LLM ${run.spans.filter((span) => span.type === "llm").length}</span>
    <span>Tool ${run.spans.filter((span) => span.type === "tool").length}</span>
    <span>Error ${run.spans.filter((span) => span.status === "error").length}</span>
  `;
  return root;
}

function waterfall(run) {
  const root = document.createElement("div");
  root.className = "trace-waterfall";
  const axis = document.createElement("div");
  axis.className = "trace-axis";
  axis.innerHTML = `<span>SPAN</span><span>0ms</span><span>${formatDuration(run.durationMs || 1)}</span><span>DUR</span>`;
  root.append(axis);

  for (const span of run.spans) {
    const row = document.createElement("div");
    row.className = "trace-span-row";
    row.innerHTML = `
      <span class="trace-span-type ${span.type}">${span.type.toUpperCase()}</span>
      <strong>${escapeHtml(span.name)}</strong>
      <div class="trace-span-track">
        <i class="${span.type} ${span.status === "error" ? "error" : ""}" style="left:${span.left}%;width:${span.width}%"></i>
      </div>
      <em>${formatDuration(span.durationMs)}</em>
    `;
    root.append(row);
  }
  return root;
}

function detailSide(run) {
  const root = document.createElement("div");
  root.className = "trace-detail-side";
  root.innerHTML = `
    <section>
      <h4>Run overview</h4>
      <label>User input</label>
      <p>${escapeHtml(run.input || "-")}</p>
      <label>Final output</label>
      <p>${escapeHtml(run.output || "-")}</p>
    </section>
    <section>
      <h4>Metadata</h4>
      ${metadataRow("run_id", run.id)}
      ${metadataRow("thread_id", run.threadId)}
      ${metadataRow("status", run.status)}
      ${metadataRow("model", run.model)}
      ${metadataRow("prompt_tokens", formatNumber(run.usage.prompt_tokens))}
      ${metadataRow("completion_tokens", formatNumber(run.usage.completion_tokens))}
    </section>
  `;
  const artifact = run.artifact;
  if (artifact?.url) root.append(artifactPreview(artifact));
  return root;
}

function buildRuns(turns) {
  window.__TRADEX_TURNS__ = turns;
  const runs = [];
  let lastUser = null;
  turns.forEach((turn, index) => {
    if (turn.role === "user") {
      lastUser = turn;
      return;
    }
    if (turn.role !== "agent") return;
    const usage = usageFromTurn(turn);
    const data = turn.result?.data || {};
    const observability = data?.observability || {};
    const spans = normalizedSpans(observability.spans || spansFromTimeline(turn.trace || [], usage.items || []));
    const durationMs = Number(observability.latency_ms || Math.max(...spans.map((span) => span.endMs), 0));
    const runId = observability.run_id || data?.backtest?.run_id || `run_${index}_${turn.ts || ""}`.replaceAll(":", "");
    runs.push({
      id: runId,
      threadId: data?.session_id || "web-user",
      title: runTitle(turn, data),
      input: lastUser?.text || "",
      output: turn.text || "",
      status: turn.result?.status || turn.meta || "answered",
      model: data?.usage?.model || "deepseek",
      startedAt: turn.ts || "-",
      trace: turn.trace || [],
      spans,
      usage,
      durationMs,
      artifact: data?.result_page?.equity_curve?.artifact || null,
    });
  });
  return runs.reverse();
}

function spansFromTimeline(timeline, usageItems) {
  const events = timeline.map((item, index) => ({
    ...item,
    at: parseTime(item.timestamp),
    index,
  }));
  const first = events.find((event) => event.at)?.at || Date.now();
  const starts = new Map();
  const spans = [];

  for (const event of events) {
    const name = event.actor || event.stage || "Agent";
    const key = `${name}:${event.event_type?.replace("_done", "").replace("_start", "") || "event"}`;
    const offset = event.at ? event.at - first : event.index * 42;
    if (String(event.event_type || "").endsWith("_start")) {
      starts.set(name, { event, offset });
      continue;
    }
    if (String(event.event_type || "").endsWith("_done") && starts.has(name)) {
      const start = starts.get(name);
      const duration = Math.max(offset - start.offset, 1);
      spans.push(makeSpan(name, event, start.offset, duration));
      starts.delete(name);
      continue;
    }
    if (event.event_type === "token_usage") {
      spans.push(makeSpan(name, { ...event, status: "success", type: "llm" }, offset, 50));
      continue;
    }
    if (!String(event.event_type || "").endsWith("_start")) {
      spans.push(makeSpan(name, event, offset, 50));
    }
  }

  for (const item of usageItems) {
    if (spans.some((span) => span.name === item.actor && span.type === "llm")) continue;
    spans.push(makeSpan(item.actor || "LLM", { status: "success", type: "llm" }, spans.length * 50, 50));
  }
  return normalizeSpans(spans);
}

function normalizedSpans(spans) {
  return normalizeSpans(
    (spans || []).map((span) => ({
      name: span.name || span.actor || "Agent",
      rawName: span.actor || span.name || "Agent",
      type: span.type || "agent",
      status: span.status || "success",
      startMs: Number(span.start_ms || span.startMs || 0),
      durationMs: Number(span.duration_ms || span.durationMs || 1),
      endMs: Number(span.end_ms || span.endMs || 0) || Number(span.start_ms || span.startMs || 0) + Number(span.duration_ms || span.durationMs || 1),
    })),
  );
}

function makeSpan(name, event, startMs, durationMs) {
  const status = event.status === "error" ? "error" : event.status === "running" ? "running" : "success";
  return {
    name: displayName(name),
    rawName: name,
    type: event.type || spanType(event),
    status,
    startMs,
    durationMs,
    endMs: startMs + durationMs,
  };
}

function normalizeSpans(spans) {
  const total = Math.max(...spans.map((span) => span.endMs), 1);
  return spans.map((span) => ({
    ...span,
    left: Math.min(96, Math.max(0, (span.startMs / total) * 100)).toFixed(2),
    width: Math.max(1, (span.durationMs / total) * 100).toFixed(2),
  }));
}

function spanType(event) {
  const actor = String(event.actor || event.stage || "");
  if (event.event_type === "token_usage" || actor.includes("Agent")) return "llm";
  if (String(event.event_type || "").includes("tool")) return "tool";
  if (event.status === "error") return "error";
  return "agent";
}

function pickSelectedRun(runs) {
  if (!runs.length) return null;
  const selected = runs.find((run) => run.id === selectedRunId);
  if (selected) return selected;
  selectedRunId = runs[0].id;
  return runs[0];
}

function usageFromTurn(turn) {
  const usage = turn?.result?.data?.usage || {};
  const total = usage.total || {};
  return {
    prompt_tokens: Number(total.prompt_tokens || 0),
    completion_tokens: Number(total.completion_tokens || 0),
    total_tokens: Number(total.total_tokens || 0),
    items: usage.items || [],
  };
}

function totalUsage(runs) {
  return runs.reduce(
    (sum, run) => ({
      prompt_tokens: sum.prompt_tokens + run.usage.prompt_tokens,
      completion_tokens: sum.completion_tokens + run.usage.completion_tokens,
      total_tokens: sum.total_tokens + run.usage.total_tokens,
    }),
    { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  );
}

function runTitle(turn, data) {
  const name = data?.result_page?.summary?.strategy_name;
  if (name) return name;
  if (turn.result?.status === "needs_clarification") return "Clarification";
  if (turn.result?.status === "blocked_missing_data") return "Data blocked";
  return "Agent run";
}

function artifactPreview(artifact) {
  const root = document.createElement("a");
  root.className = "trace-artifact compact";
  root.href = artifact.url;
  root.target = "_blank";
  root.rel = "noreferrer";
  root.innerHTML = `
    <div>
      <div class="trace-artifact-title">Artifact · ${escapeHtml(artifact.artifact_type || "equity_curve")}</div>
      <div class="trace-artifact-subtitle">${escapeHtml(artifact.artifact_id || "收益曲线")}</div>
    </div>
    <img src="${artifact.url}" alt="收益曲线 artifact" />
  `;
  return root;
}

function metadataRow(label, value) {
  return `<div class="trace-meta-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function statCard(label, value) {
  const card = document.createElement("div");
  card.className = "trace-stat";
  card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>`;
  return card;
}

function emptyState() {
  const node = document.createElement("div");
  node.className = "trace-empty";
  node.textContent = "当前会话还没有 Agent 执行轨迹。发送一条消息后，这里会显示 run 列表、waterfall、token 和详情。";
  return node;
}

function percentile(values, p) {
  const items = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (!items.length) return 0;
  return items[Math.min(items.length - 1, Math.floor((items.length - 1) * p))];
}

function parseTime(value) {
  const time = Date.parse(value || "");
  return Number.isFinite(time) ? time : null;
}

function isOk(status) {
  return ["completed", "answered", "success"].includes(status);
}

function statusClass(status) {
  if (isOk(status)) return "ok";
  if (status === "running") return "running";
  return "error";
}

function displayStatus(status) {
  return { completed: "ok", answered: "ok", needs_clarification: "wait", blocked_missing_data: "blocked" }[status] || status || "unknown";
}

function displayName(name) {
  const map = {
    IntentClassifierAgent: "Intent classifier",
    ClarificationAgent: "Clarification",
    StrategyDesignerAgent: "Strategy designer",
    DataResearchAgent: "Data research",
    ResultExplanationAgent: "Result explanation",
    validate_strategy_schema: "validate_strategy_schema",
    query_market_data: "query_market_data",
    run_backtest: "run_backtest",
    compute_metrics: "compute_metrics",
    assemble_result_page: "assemble_result_page",
  };
  return map[name] || name;
}

function formatDuration(ms) {
  const value = Number(ms || 0);
  if (value >= 1000) return `${(value / 1000).toFixed(2)}s`;
  return `${Math.max(0, Math.round(value))}ms`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function short(value, limit) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
