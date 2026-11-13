import { ApiError, getToken } from "./api.js";

function headers() {
  const h = { "Content-Type": "application/json" };
  if (getToken()) h.Authorization = "Bearer " + getToken();
  return h;
}

export async function getChatState() {
  let response;
  try {
    response = await fetch("/api/chat/", { headers: headers() });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.message || "Couldn't load the chat.", response.status);
  return data;
}

// Sends a message and reads the streamed answer (server-sent events).
// `on` has optional handlers: meta, token, done, error.
export async function sendChatMessage({ content, conversationId, provider }, on, signal) {
  let response;
  try {
    response = await fetch("/api/chat/messages/", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ content, conversation_id: conversationId, provider }),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.message || "Something went wrong. Please try again.", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);

      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        on[event]?.(JSON.parse(data));
      } catch {
        /* ignore a malformed event */
      }
    }
  }
}

export async function sendFeedback(messageId, feedback) {
  const response = await fetch(`/api/chat/messages/${messageId}/feedback/`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ feedback }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.message || "Could not save feedback.", response.status);
  }
  return response.json();
}