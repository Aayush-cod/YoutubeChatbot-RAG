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