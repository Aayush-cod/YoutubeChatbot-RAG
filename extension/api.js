// Ask the background worker to call our backend, and wait for its answer.
function callBackend(path, body) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "api", path, body }, (reply) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!reply || !reply.ok) {
        reject(new Error((reply && reply.error) || "Unknown error"));
        return;
      }
      resolve(reply.data);
    });
  });
}

// Open a connection to the background worker and receive the streamed events.
// onEvent is called for every event; the promise finishes on "done".
function streamChat(body, onEvent) {
  return new Promise((resolve, reject) => {
    const port = chrome.runtime.connect({ name: "chat" });
    let finished = false;

    port.onMessage.addListener((event) => {
      if (event.type === "done") {
        finished = true;
        port.disconnect();
        resolve();
      } else if (event.type === "error") {
        finished = true;
        port.disconnect();
        reject(new Error(event.message));
      } else {
        onEvent(event);
      }
    });

    port.onDisconnect.addListener(() => {
      if (!finished) {
        reject(new Error("Lost the connection to the extension. Please try again."));
      }
    });

    port.postMessage({ path: "/chat", body });
  });
}