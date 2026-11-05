// Everything that depends on YouTube's page structure lives in THIS file.
// If YouTube redesigns the page, this should be the only file that needs fixing.

const SELECTORS = {
  segment: "ytd-transcript-segment-renderer",
  timestamp: ".segment-timestamp",
  text: ".segment-text",
  showTranscriptButton: "ytd-video-description-transcript-section-renderer button",
  expandDescription: "ytd-watch-metadata #expand, #description #expand",
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Keep checking until check() gives a real value, or give up after timeoutMs.
async function waitFor(check, timeoutMs = 8000, stepMs = 250) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = check();
    if (value) {
      return value;
    }
    await sleep(stepMs);
  }
  return null;
}

// "1:05" -> 65, "1:02:05" -> 3725
function parseTimestamp(text) {
  return text.split(":").reduce((total, part) => total * 60 + Number(part), 0);
}

// Seconds -> "1:05" (used for display)
function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

// Read whatever transcript lines are in the page right now.
function readSegmentsFromPage() {
  const seen = new Set();
  const rows = [];

  for (const element of document.querySelectorAll(SELECTORS.segment)) {
    const time = element.querySelector(SELECTORS.timestamp)?.textContent.trim();
    const text = element.querySelector(SELECTORS.text)?.textContent.trim();
    if (!time || !text) {
      continue;
    }
    const start = parseTimestamp(time);
    if (Number.isNaN(start)) {
      continue;
    }
    const key = `${start}|${text}`;
    if (seen.has(key)) {
      continue; // the page can contain the same list more than once
    }
    seen.add(key);
    rows.push({ text, start });
  }

  // The page gives only start times, so a line lasts until the next one starts.
  return rows.map((row, i) => ({
    text: row.text,
    start: row.start,
    duration: i + 1 < rows.length ? Math.max(rows[i + 1].start - row.start, 0) : 5,
  }));
}

// Open the transcript panel if needed, wait for it, and return the segments.
async function loadTranscript() {
  let segments = readSegmentsFromPage();
  if (segments.length > 0) {
    return segments;
  }

  let button = document.querySelector(SELECTORS.showTranscriptButton);
  if (!button) {
    document.querySelector(SELECTORS.expandDescription)?.click();
    button = await waitFor(() => document.querySelector(SELECTORS.showTranscriptButton), 3000);
  }
  if (!button) {
    throw new Error("No transcript button found. This video may have no captions.");
  }

  button.click();
  await waitFor(() => document.querySelector(SELECTORS.segment));
  await sleep(500); // give the rest of the lines a moment to appear

  segments = readSegmentsFromPage();
  if (segments.length === 0) {
    throw new Error("The transcript did not load.");
  }
  return segments;
}