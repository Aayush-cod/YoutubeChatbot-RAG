const PANEL_ID = "yt-rag-panel";

function getVideoId() {
  const url = new URL(window.location.href);
  if (url.pathname !== "/watch") {
    return null;
  }
  return url.searchParams.get("v");
}

function renderSummary(container, summary) {
  container.textContent = "";

  const heading = document.createElement("h4");
  heading.textContent = "Summary";
  const paragraph = document.createElement("p");
  paragraph.textContent = summary.summary;
  container.append(heading, paragraph);

  if (summary.key_points.length > 0) {
    const pointsHeading = document.createElement("h4");
    pointsHeading.textContent = "Key points";
    const list = document.createElement("ul");
    for (const point of summary.key_points) {
      const item = document.createElement("li");
      const when = point.timestamp_seconds == null ? "" : `[${formatTime(point.timestamp_seconds)}] `;
      item.textContent = when + point.point;
      list.append(item);
    }
    container.append(pointsHeading, list);
  }

  if (summary.topics.length > 0) {
    const topics = document.createElement("p");
    topics.className = "yt-rag-topics";
    topics.textContent = "Topics: " + summary.topics.join(", ");
    container.append(topics);
  }
}

async function onSummarizeClick() {
  const videoId = getVideoId();
  const button = document.getElementById("yt-rag-summarize");
  const status = document.getElementById("yt-rag-status");
  const result = document.getElementById("yt-rag-result");

  button.disabled = true;
  result.textContent = "";
  try {
    status.textContent = "Reading transcript...";
    const segments = await loadTranscript();

    status.textContent = `Sending ${segments.length} lines to the server...`;
    await callBackend("/ingest", { video_id: videoId, segments });

    status.textContent = "Summarizing (long videos can take a few minutes)...";
    const summary = await callBackend("/summary", { video_id: videoId });

    if (getVideoId() !== videoId) {
      return; // the user moved to another video while we were waiting
    }
    status.textContent = "";
    renderSummary(result, summary);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
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
        <p class="yt-rag-small">Video: <code id="yt-rag-video-id"></code></p>
        <button id="yt-rag-summarize">Summarize video</button>
        <p id="yt-rag-status"></p>
        <div id="yt-rag-result"></div>
      </div>
    `;
    panel.querySelector("#yt-rag-summarize").addEventListener("click", onSummarizeClick);
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
    document.getElementById("yt-rag-result").textContent = "";
  }
  document.getElementById("yt-rag-video-id").textContent = videoId;
}

// YouTube changes videos without reloading the page, and fires this event when it does.
document.addEventListener("yt-navigate-finish", update);

update();