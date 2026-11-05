const API_BASE = "http://localhost:8000";

// Extension background workers get shut down after ~30 s of silence.
// Calling any extension API every 20 s counts as activity and keeps it alive
// while a slow request (like a long summary) is in progress.
function startKeepAlive() {
  return setInterval(() => chrome.runtime.getPlatformInfo(() => {}), 20000);
}

async function callApi(path, body) {
  const keepAlive = startKeepAlive();
  try {
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new Error("Could not reach the server. Is the backend running on localhost:8000?");
    }

    if (!response.ok) {
      let message = `Server error (${response.status})`;
      try {
        const data = await response.json();
        const detail = data.detail || data.error;
        if (typeof detail === "string") {
          message = detail;
        }
      } catch (error) {
        // the reply wasn't JSON; keep the generic message
      }
      throw new Error(message);
    }
    return await response.json();
  } finally {
    clearInterval(keepAlive);
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "api") {
    callApi(message.path, message.body)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true; // tells Chrome we will answer later, asynchronously
  }
});

// Read an error message out of a failed response.
async function errorMessageFrom(response) {
  let message = `Server error (${response.status})`;
  try {
    const data = await response.json();
    const detail = data.detail || data.error;
    if (typeof detail === "string") {
      message = detail;
    }
  } catch (error) {
    // not JSON; keep the generic message
  }
  return message;
}

// Call the streaming endpoint and forward each line to the page as it arrives.
async function streamFromApi(path, body, port, signal) {
  const keepAlive = startKeepAlive();
  try {
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
    } catch (error) {
      if (signal.aborted) {
        return;
      }
      throw new Error("Could not reach the server. Is the backend running on localhost:8000?");
    }
    if (!response.ok) {
      throw new Error(await errorMessageFrom(response));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // the last piece may be an unfinished line; keep it
      for (const line of lines) {
        if (line.trim()) {
          port.postMessage(JSON.parse(line));
        }
      }
    }
    if (buffer.trim()) {
      port.postMessage(JSON.parse(buffer));
    }
  } catch (error) {
    if (!signal.aborted) {
      port.postMessage({ type: "error", message: error.message });
    }
  } finally {
    clearInterval(keepAlive);
  }
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "chat") {
    return;
  }
  const controller = new AbortController();
  port.onDisconnect.addListener(() => controller.abort());
  port.onMessage.addListener((message) => {
    streamFromApi(message.path, message.body, port, controller.signal);
  });
});