# Privacy

YouTube RAG Assistant is a learning project. This page explains exactly what it does with data.

## What the extension sends

Only when you click **Summarize video** or send a question in the panel, the extension sends to the project's server:

- the video's ID
- the video's transcript text with its timestamps (read from the YouTube page you have open)
- your question and up to the last 10 messages of the conversation

Nothing is sent when you just browse YouTube. The extension does not read your account, your history, cookies or any other page. It does not use analytics or trackers.

## What the server does

- Keeps the transcript, a search index of it, and the summary **in memory** so it can answer your questions. Up to 20 videos are kept, and everything is lost when the server restarts.
- Sends parts of the transcript and your question to **Groq**, an AI provider, to generate answers and summaries. Groq's own privacy policy applies to that data.
- Does not store your questions or the answers, and does not write transcripts to disk.
- Writes operational logs (request type, status, timing, text lengths). The logs do not contain transcript or question text, but the server's web logs can include your IP address.

## Connection

All traffic between the extension and the server uses HTTPS.

## Your control

Uninstalling the extension stops all data being sent. Data already in the server's memory disappears on the next restart.

## Contact

Open an issue on this repository.