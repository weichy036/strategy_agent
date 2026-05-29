const REQUEST_CONTEXT = {
  user_id: "web-user",
  session_id: "thread-macd-510300",
};


export function setActiveSession(sessionId) {
  REQUEST_CONTEXT.session_id = sessionId || REQUEST_CONTEXT.session_id;
}


export function createLocalSession() {
  const id = `thread-${Date.now()}`;
  setActiveSession(id);
  return id;
}


export async function loadSessionHistory() {
  const params = new URLSearchParams({ user_id: REQUEST_CONTEXT.user_id });
  const res = await fetch(`/research/session/${encodeURIComponent(REQUEST_CONTEXT.session_id)}/history?${params}`);
  if (!res.ok) throw new Error(`history unavailable: ${res.status}`);
  return res.json();
}


export async function runResearchFallback(query) {
  const res = await fetch("/research/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, ...REQUEST_CONTEXT }),
  });
  return res.json();
}


export async function streamResearchRequest(query, handlers = {}) {
  const res = await fetch("/research/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, ...REQUEST_CONTEXT }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`stream unavailable: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;

  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const raw of events) {
        const event = parseSseEvent(raw);
        if (!event) continue;
        if (event.type === "started") handlers.onStarted?.();
        else if (event.type === "timeline") handlers.onTimeline?.(event.items || []);
        else if (event.type === "final") finalPayload = toResearchPayload(event.result);
        else if (event.type === "error") finalPayload = toErrorPayload(event);
      }
    }
    if (done) break;
  }
  if (!finalPayload) {
    throw new Error("stream finished without final result");
  }
  return finalPayload;
}

function toErrorPayload(event) {
  return {
    ok: false,
    status: event?.status || "error",
    error_code: event?.error_code || "agent_stream_failed",
    message: event?.message || "Agent 执行失败，请稍后重试。",
    data: null,
    tool_calls: [],
    timeline: [],
  };
}


function toResearchPayload(result) {
  return {
    ok: true,
    status: result?.status,
    assistant_message: result?.assistant_message,
    data: result?.data,
    tool_calls: result?.tool_calls,
    timeline: result?.timeline,
  };
}


function parseSseEvent(raw) {
  const dataLines = raw
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (dataLines.length === 0) return null;
  try {
    return JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }
}
