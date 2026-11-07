# YouTube RAG Assistant

A Chrome extension that adds a chat panel to YouTube. It can **summarize a video** and **answer questions about it**, with answers that link back to the exact moment in the video. It reads the transcript from the page, and a small backend does the retrieval and calls an LLM.

Built as a learning project: LangChain, RAG, FastAPI, Docker, CI, and deployment on AWS.


<p align="center">
  <img src="docs/extension_yt.png" alt="The assistant panel next to a YouTube video" width="90%">
  <br>
  <sub>Ask a question about a video. Answers cite the exact moments, and the timestamps jump the video there.</sub>
</p>

<table>
  <tr>
    <td width="50%"><img src="docs/extension.png" alt="The extension installed in Chrome"></td>
    <td width="50%"><img src="docs/api.png" alt="The backend API documentation page"></td>
  </tr>
  <tr>
    <td align="center"><sub>Installed in Chrome</sub></td>
    <td align="center"><sub>Backend API running on AWS (FastAPI docs)</sub></td>
  </tr>
</table>

## Features

- Summary with key points and clickable timestamps (long videos use map-reduce)
- Streaming chat answers with `[m:ss]` citations that jump the video to that moment
- Follow-up questions (the last 10 messages are sent as history)
- Minimizable panel that follows YouTube's light and dark theme

## How it works

```mermaid
flowchart LR
  A[Extension: content script on youtube.com] --> B[Background worker]
  B -->|HTTPS| C[Caddy reverse proxy]
  C --> D[FastAPI in Docker]
  D --> E[(FAISS index, in memory)]
  D --> F[Groq LLM]
```

1. The content script reads the transcript from the YouTube page.
2. The backend splits it into time-aware chunks (about 1000 characters, 200 overlap), embeds them locally with `all-MiniLM-L6-v2`, and keeps a FAISS index per video.
3. For a question, it retrieves 10 candidates, reranks them with a cross-encoder (`ms-marco-MiniLM-L-6-v2`), and gives the best 5 to the LLM (`openai/gpt-oss-120b` on Groq), which must answer only from those excerpts.
4. Answers stream back as NDJSON. Summaries use structured output; long videos are summarized in batches and then merged.

### The RAG pipeline in detail

```mermaid
flowchart TD
  subgraph ingest["1. Ingest (once per video)"]
    T["Transcript lines from the YouTube page<br/>(text, start, duration)"] --> C["Time-aware chunking<br/>~1000 chars, 200 overlap<br/>keeps start and end time"]
    C --> EM["Embeddings<br/>all-MiniLM-L6-v2, run locally"]
    EM --> IDX[("FAISS index<br/>in memory, one per video")]
  end

  subgraph ask["2. Ask a question"]
    Q["Question + last 10 messages"] --> R["Retrieve 10 candidates<br/>by vector similarity"]
    IDX --> R
    R --> RR["Rerank with a cross-encoder<br/>keep the best 5"]
    RR --> P["Prompt: answer only from the excerpts<br/>history + excerpts with timestamps"]
    P --> L["LLM on Groq<br/>gpt-oss-120b"]
    L --> S["Stream tokens as NDJSON<br/>normalize odd characters"]
    S --> U["Panel shows the answer<br/>m:ss citations become links"]
  end

  subgraph sum["3. Summary"]
    C --> B["Group chunks into batches<br/>about 12,000 characters"]
    B --> M["Map: summarize each batch"]
    M --> RD["Reduce: merge the partial summaries<br/>as structured output"]
    RD --> V["Summary + key points + topics"]
  end
```

| Stage | Code |
|---|---|
| Chunking with timestamps | `backend/app/chunking.py` |
| Embeddings and FAISS store (LRU cache) | `backend/app/store.py` |
| Retrieval, prompt, LLM chain | `backend/app/rag.py` |
| Reranker | `backend/app/rerank.py` |
| Summaries (map-reduce, structured output) | `backend/app/summarize.py` |
| API, streaming, rate limits | `backend/app/main.py` |
| Evaluation (hit rate, MRR) | `backend/app/evaluation.py`, `eval/` |

## Retrieval quality

Measured on a hand-written set of 20 questions (with the time window where each answer lives) on one 51-minute video:

| Setup | Hit rate | MRR |
|---|---|---|
| 1000-char chunks, top 5 (baseline) | 0.95 | 0.718 |
| top 10 | 1.00 | 0.727 |
| 500-char chunks, top 5 | 0.95 | 0.739 |
| 1500-char chunks, top 5 | 1.00 | 0.760 |
| **1000-char chunks + reranker (10 candidates)** | **1.00** | **0.942** |

The reranker is on by default. Caveats: 20 questions on one video is a small sample, and a "hit" is any overlap with the answer window, which is lenient.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env        # then put your GROQ_API_KEY in .env
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Tests (offline, no API key needed): `cd backend && python -m pytest -q`

To use the extension against your local backend, set `API_BASE` in `extension/background.js` to `http://localhost:8000` and add that address to `host_permissions` in `extension/manifest.json`, then load the `extension/` folder with **Load unpacked** in `chrome://extensions`.

## Docker

```bash
cd backend
docker build -t yt-rag-backend .
docker run --rm -p 8000:7860 --env-file ../.env yt-rag-backend
```

## Deployment

- GitHub Actions runs the tests and lint, builds the image, smoke-tests `/health`, and pushes it to Docker Hub on every push to `main`.
- The image runs on an AWS EC2 Ubuntu instance behind Caddy, which provides HTTPS automatically.
- The server is switched on only for demos. To update it: `docker pull`, then re-create the container.

## Install the extension

Download the zip from the [Releases](../../releases) page, unzip it, open `chrome://extensions`, enable **Developer mode**, and choose **Load unpacked**.

## Limitations

- Reads the transcript from YouTube's page structure, which is unofficial and may break when YouTube changes its layout.
- Uses a shared free-tier Groq key, so a long summary can take minutes because of rate limits.
- Transcripts live in the server's memory only (up to 20 videos) and are lost on restart.
- "List everything mentioned" questions are a known weakness of retrieval-based answers.
- The demo server is off by default.

## Privacy

See [PRIVACY.md](PRIVACY.md).