const PANEL_ID = "yt-rag-panel";

function getVideoId() {
  const url = new URL(window.location.href);
  if (url.pathname !== "/watch") {
    return null;
  }
  return url.searchParams.get("v");
}

function ensurePanel() {
  let panel = document.getElementById(PANEL_ID);
  if (!panel) {
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <div class="yt-rag-header">Video Assistant</div>
      <div class="yt-rag-body">
        <p>Video ID: <code id="yt-rag-video-id"></code></p>
      </div>
    `;
    document.body.appendChild(panel);
  }
  return panel;
}

function update() {
  const videoId = getVideoId();
  const existing = document.getElementById(PANEL_ID);

  if (!videoId) {
    if (existing) {
      existing.remove();
    }
    return;
  }

  ensurePanel();
  document.getElementById("yt-rag-video-id").textContent = videoId;
}

// YouTube changes videos without reloading the page, and fires this event when it does.
document.addEventListener("yt-navigate-finish", update);

update();