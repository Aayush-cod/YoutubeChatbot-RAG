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