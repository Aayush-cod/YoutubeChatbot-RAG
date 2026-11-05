const PANEL_ID = "yt-rag-panel";

// Videos the server already has the transcript of (during this page's life).
const ingestedVideos = new Set();
// The conversation so far; sent to the server so follow-up questions make sense.
let chatHistory = [];
let chatBusy = false;

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

// Make sure the server has this video's transcript (send it once).
async function ensureIngested(videoId, status) {
  if (ingestedVideos.has(videoId)) {
    return;
  }
  status.textContent = "Reading transcript...";
  const segments = await loadTranscript();
  status.textContent = `Sending ${segments.length} lines to the server...`;
  await callBackend("/ingest", { video_id: videoId, segments });
  ingestedVideos.add(videoId);
}

// Run an action that needs the transcript on the server. If the server says it
// doesn't have it (for example, it was restarted), send it again and retry once.
async function withIngest(videoId, status, action) {
  await ensureIngested(videoId, status);
  try {
    return await action();
  } catch (error) {
    if (!error.message.includes("ingest")) {
      throw error;
    }
    ingestedVideos.delete(videoId);
    await ensureIngested(videoId, status);
    return await action();
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
    const summary = await withIngest(videoId, status, () => {
      status.textContent = "Summarizing (long videos can take a few minutes)...";
      return callBackend("/summary", { video_id: videoId });
    });

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

function addMessage(role, text) {
  const box = document.getElementById("yt-rag-messages");
  const element = document.createElement("div");
  element.className = `yt-rag-msg yt-rag-${role}`;
  element.textContent = text;
  box.append(element);
  box.scrollTop = box.scrollHeight;
  return element;
}

function setChatDisabled(disabled) {
  document.getElementById("yt-rag-input").disabled = disabled;
  document.getElementById("yt-rag-send").disabled = disabled;
}

async function onAsk(event) {
  event.preventDefault(); // stop the form from reloading the page
  if (chatBusy) {
    return;
  }
  const input = document.getElementById("yt-rag-input");
  const status = document.getElementById("yt-rag-status");
  const box = document.getElementById("yt-rag-messages");
  const videoId = getVideoId();
  const question = input.value.trim();
  if (!question || !videoId) {
    return;
  }

  chatBusy = true;
  setChatDisabled(true);
  input.value = "";
  addMessage("user", question);
  const answerElement = addMessage("assistant", "Thinking...");
  let answer = "";
  let sources = [];

  try {
    await withIngest(videoId, status, () => {
      status.textContent = "";
      answer = "";
      return streamChat(
        { video_id: videoId, question, history: chatHistory.slice(-10) },
        (item) => {
          if (item.type === "sources") {
            sources = item.sources || [];
          } else if (item.type === "token") {
            answer += item.text;
            answerElement.textContent = answer;
            box.scrollTop = box.scrollHeight;
          }
        }
      );
    });

    if (getVideoId() === videoId) {
      chatHistory.push({ role: "user", content: question });
      chatHistory.push({ role: "assistant", content: answer });
      if (sources.length > 0) {
        const line = document.createElement("div");
        line.className = "yt-rag-sources";
        line.textContent = "Sources: " + sources.map((s) => formatTime(s.start)).join(", ");
        answerElement.after(line);
        box.scrollTop = box.scrollHeight;
      }
    }
  } catch (error) {
    status.textContent = error.message;
    if (!answer) {
      answerElement.remove();
    }
  } finally {
    chatBusy = false;
    setChatDisabled(false);
    input.focus();
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
        <h4>Ask about this video</h4>
        <div id="yt-rag-messages"></div>
        <form id="yt-rag-form">
          <input id="yt-rag-input" type="text" maxlength="1000"
                 placeholder="Ask a question..." autocomplete="off">
          <button id="yt-rag-send" type="submit">Send</button>
        </form>
      </div>
    `;
    panel.querySelector("#yt-rag-summarize").addEventListener("click", onSummarizeClick);
    panel.querySelector("#yt-rag-form").addEventListener("submit", onAsk);
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
    chatHistory = [];
    document.getElementById("yt-rag-status").textContent = "";
    document.getElementById("yt-rag-result").textContent = "";
    document.getElementById("yt-rag-messages").textContent = "";
  }
  document.getElementById("yt-rag-video-id").textContent = videoId;
}

// YouTube changes videos without reloading the page, and fires this event when it does.
document.addEventListener("yt-navigate-finish", update);

update();