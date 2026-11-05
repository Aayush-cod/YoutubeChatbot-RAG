const PANEL_ID = "yt-rag-panel";

// Videos the server already has the transcript of (during this page's life).
const ingestedVideos = new Set();
// The conversation so far; sent to the server so follow-up questions make sense.
let chatHistory = [];
let chatBusy = false;
let panelCollapsed = false;

function getVideoId() {
  const url = new URL(window.location.href);
  if (url.pathname !== "/watch") {
    return null;
  }
  return url.searchParams.get("v");
}

// A small blue "1:05" link that seeks the video when clicked.
function makeTimeButton(seconds) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "yt-rag-time";
  button.textContent = formatTime(seconds);
  button.addEventListener("click", () => seekVideo(seconds));
  return button;
}

// Add text to an element, turning **bold** into <strong> and [m:ss] into time links.
function appendInline(parent, text) {
  const pattern = /\*\*(.+?)\*\*|\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    parent.append(text.slice(last, match.index));
    if (match[1] !== undefined) {
      const strong = document.createElement("strong");
      strong.textContent = match[1];
      parent.append(strong);
    } else {
      parent.append(makeTimeButton(parseTimestamp(match[2])));
    }
    last = match.index + match[0].length;
  }
  parent.append(text.slice(last));
}

// Turn the model's text into paragraphs and bullet lists, line by line.
function renderRichText(container, text) {
  container.textContent = "";
  let list = null;
  for (const line of text.split("\n")) {
    const bullet = line.match(/^\s*[*-]\s+(.*)$/);
    if (bullet) {
      if (!list) {
        list = document.createElement("ul");
        container.append(list);
      }
      const item = document.createElement("li");
      appendInline(item, bullet[1]);
      list.append(item);
    } else {
      list = null;
      if (line.trim() === "") {
        continue;
      }
      const paragraph = document.createElement("p");
      appendInline(paragraph, line);
      container.append(paragraph);
    }
  }
}

// "Sources: 0:00 2:04 3:57", sorted by time, each one a link.
function buildSourcesLine(sources) {
  const starts = [...new Set(sources.map((s) => Math.floor(s.start)))].sort((a, b) => a - b);
  const line = document.createElement("div");
  line.className = "yt-rag-sources";
  line.append("Sources: ");
  for (const start of starts) {
    line.append(makeTimeButton(start), " ");
  }
  return line;
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
      if (point.timestamp_seconds != null) {
        item.append(makeTimeButton(point.timestamp_seconds), " ");
      }
      item.append(point.point);
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
// "status" is any element whose text we update with progress.
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



function scrollChatToEnd() {
  const body = document.getElementById("yt-rag-body");
  if (body) {
    body.scrollTop = body.scrollHeight;
  }
}



function addMessage(role, text) {
  const box = document.getElementById("yt-rag-messages");
  const element = document.createElement("div");
  element.className = `yt-rag-msg yt-rag-${role}`;
  element.textContent = text;
  box.append(element);
  scrollChatToEnd();
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
    // Progress messages ("Reading transcript...") appear inside the answer bubble.
    await withIngest(videoId, answerElement, () => {
      answerElement.textContent = "Thinking...";
      answer = "";
      return streamChat(
        { video_id: videoId, question, history: chatHistory.slice(-10) },
        (item) => {
          if (item.type === "sources") {
            sources = item.sources || [];
          } else if (item.type === "token") {
            answer += item.text;
            renderRichText(answerElement, answer);
            scrollChatToEnd();
          }
        }
      );
    });

    if (getVideoId() === videoId) {
      chatHistory.push({ role: "user", content: question });
      chatHistory.push({ role: "assistant", content: answer });
      if (sources.length > 0 && /\[\d{1,2}:\d{2}/.test(answer)) {
        answerElement.after(buildSourcesLine(sources));
        scrollChatToEnd();
      }
    }
  } catch (error) {
    // Show the problem inside the chat, where the person is looking.
    answerElement.textContent = answer ? `${answer}\n\n(${error.message})` : error.message;
    answerElement.classList.add("yt-rag-error");
  } finally {
    chatBusy = false;
    setChatDisabled(false);
    input.focus();
  }
}

function setCollapsed(collapsed) {
  panelCollapsed = collapsed;
  const panel = document.getElementById(PANEL_ID);
  if (!panel) {
    return;
  }
  panel.classList.toggle("yt-rag-collapsed", collapsed);
  const toggle = document.getElementById("yt-rag-toggle");
  toggle.textContent = collapsed ? "+" : "−";
  toggle.setAttribute("aria-label", collapsed ? "Expand" : "Minimize");
  toggle.setAttribute("aria-expanded", String(!collapsed));
}

function ensurePanel() {
  let panel = document.getElementById(PANEL_ID);
  if (!panel) {
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <div class="yt-rag-header" id="yt-rag-header">
        <span class="yt-rag-title"><span class="yt-rag-logo">✦</span>  Video Assistant</span>
        <button id="yt-rag-toggle" type="button" aria-label="Minimize" aria-expanded="true">−</button>
      </div>
      <div class="yt-rag-body" id="yt-rag-body">
        <div class="yt-rag-toolbar">
          <button id="yt-rag-summarize" type="button">Summarize video</button>
        </div>
        <p id="yt-rag-status"></p>
        <div id="yt-rag-result"></div>
        <div id="yt-rag-messages"></div>
      </div>
      <form id="yt-rag-form">
        <input id="yt-rag-input" type="text" maxlength="1000"
               placeholder="Ask about this video" autocomplete="off">
        <button id="yt-rag-send" type="submit" aria-label="Send">➤</button>
      </form>
    `;
    panel.querySelector("#yt-rag-header").addEventListener("click", (event) => {
      // minimized: clicking anywhere on the header expands; open: only the button minimizes
      if (panelCollapsed || event.target.closest("#yt-rag-toggle")) {
        setCollapsed(!panelCollapsed);
      }
    });
    panel.querySelector("#yt-rag-summarize").addEventListener("click", onSummarizeClick);
    panel.querySelector("#yt-rag-form").addEventListener("submit", onAsk);
    document.body.appendChild(panel);
    setCollapsed(panelCollapsed); // keep the minimized state if the panel is re-created
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
}

// YouTube changes videos without reloading the page, and fires this event when it does.
document.addEventListener("yt-navigate-finish", update);

update();