const PANEL_ID = "yt-rag-panel";

function getVideoId() {
  const url = new URL(window.location.href);
  if (url.pathname !== "/watch") {
    return null;
  }
  return url.searchParams.get("v");
}

async function onLoadClick() {
  const status = document.getElementById("yt-rag-status");
  status.textContent = "Loading transcript...";
  try {
    const segments = await loadTranscript();
    const last = segments[segments.length - 1];
    status.textContent = `Loaded ${segments.length} lines, up to ${formatTime(last.start)}.`;
    console.log("yt-rag first lines:", segments.slice(0, 3));
  } catch (error) {
    status.textContent = error.message;
  }
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
        <button id="yt-rag-load">Load transcript</button>
        <p id="yt-rag-status"></p>
      </div>
    `;
    panel.querySelector("#yt-rag-load").addEventListener("click", onLoadClick);
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

  const panel = ensurePanel();
  if (panel.dataset.videoId !== videoId) {
    panel.dataset.videoId = videoId;
    document.getElementById("yt-rag-status").textContent = "";
  }
  document.getElementById("yt-rag-video-id").textContent = videoId;
}

// YouTube changes videos without reloading the page, and fires this event when it does.
document.addEventListener("yt-navigate-finish", update);

update();