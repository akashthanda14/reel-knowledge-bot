# Teaching Guide — Reel Knowledge Agent

## Goal of this project
Convert a reel/video link (YouTube or Instagram) into structured learning notes, then store those notes in Notion.

---

## 1) Big-picture architecture

See diagrams in [README.md](README.md).

There are 3 runtime layers:

1. **Telegram interface**
   - File: `bot.py`
   - Receives a user message, extracts URL, sends result back.

2. **AI orchestration layer**
   - File: `agent.py`
   - Uses OpenAI chat + tool-calling loop.
   - Decides which tool to call and in what order.

3. **Tool execution layer (MCP server)**
   - File: `server.py`
   - Implements tools:
     - `download_reel(url)`
     - `transcribe_audio(file_path)`
     - `get_existing_topics()`
     - `save_to_notion(topic, subtopic, content)`

Support file:
- `setup_notion.py`: one-time schema bootstrap for Notion fields.

---

## 2) End-to-end flow to teach (request lifecycle)

Use this as your classroom script.

1. Student sends a reel URL to Telegram bot.
2. `bot.py` calls `process_url(url)` from `agent.py`.
3. `agent.py` starts MCP server process (`server.py`) over stdio.
4. Agent asks MCP for available tools (`list_tools`).
5. OpenAI model receives:
   - System instructions (how to process)
   - Tool definitions (function schemas)
   - User URL
6. Model selects and calls tools in sequence:
   - Download audio
   - Transcribe audio
   - Read existing topics from Notion
   - Save structured summary into Notion
7. Tool outputs are appended to message history.
8. Agent loop continues until no more tool calls.
9. Final response is sent back to Telegram.
10. User sees confirmation + key concepts.

---

## 3) Why MCP is used here

MCP gives a clean contract:
- Agent focuses on **reasoning/orchestration**.
- Tools focus on **side effects/integrations**.

This separation makes the app easier to teach, test, and replace parts independently.

---

## 4) File-by-file teaching notes

## `bot.py`
Responsibilities:
- Validate incoming text contains a supported URL.
- Acknowledge the user quickly.
- Forward URL to agent and return result.

Teaching point:
- This file has no Notion/OpenAI logic directly. It is just interface + error handling.

## `agent.py`
Responsibilities:
- Start local MCP tool server.
- Convert MCP tools into OpenAI function format.
- Maintain conversation state and tool outputs.
- Enforce `save_to_notion` before final answer.

Teaching point:
- This is an **agentic loop** pattern:
  - Ask model
  - Execute tools
  - Feed tool result back
  - Repeat

## `server.py`
Responsibilities:
- Implement the real work via tools.
- Handle integration errors defensively.
- Clean temporary files.

Tool details:
- `download_reel`: wraps `yt-dlp`.
- `transcribe_audio`: tries local Whisper first, then OpenAI fallback.
- `get_existing_topics`: reads Notion DB entries for topic reuse.
- `save_to_notion`: writes page with Name/Topic/Subtopic + summary content.

## `setup_notion.py`
Responsibilities:
- Verifies connectivity to Notion DB.
- Adds required properties (`Topic`, `Subtopic`) once.

---

## 5) Data contracts to explain

## Input contract
- User sends URL that matches regex in `bot.py`.

## Internal tool contracts
- `download_reel(url) -> str`
  - returns local path or error string.
- `transcribe_audio(file_path) -> str`
  - returns transcript or error string.
- `get_existing_topics() -> str`
  - returns existing topic list text or error.
- `save_to_notion(topic, subtopic, content) -> str`
  - returns saved URL or error.

## Output contract
- Final text summary to Telegram.
- New Notion page persisted.

---

## 6) Reliability and failure handling

Current protections:
- Missing env vars return explicit errors.
- Transcription has local + API fallback.
- Audio temp file is deleted in `finally`.
- Agent blocks final response until `save_to_notion` is attempted.

Common failure modes:
- Invalid/expired `NOTION_TOKEN`
- Wrong `NOTION_DATABASE_ID`
- `yt-dlp`/`ffmpeg` missing
- Network/SSL issues

---

## 7) Demo plan (10–15 minutes)

1. Show architecture diagram verbally (bot → agent → MCP tools → Notion).
2. Open `bot.py`, show URL parsing and message handling.
3. Open `agent.py`, walk through agentic loop and forced save guard.
4. Open `server.py`, explain each tool and fallback logic.
5. Run one reel link live.
6. Show final Telegram response and Notion entry.

---

## 8) Suggested classroom exercises

1. Add support for another URL format in regex.
2. Add a `Source URL` field in Notion and save it.
3. Add latency logging for each tool call.
4. Add duplicate detection before creating a new Notion page.

---

## 9) Key vocabulary for students

- MCP (Model Context Protocol)
- Tool calling
- Agentic loop
- Orchestration vs execution
- Structured persistence
- Graceful fallback

---

## 10) One-sentence summary

This project is a practical AI agent pipeline where Telegram is the UI, OpenAI is the reasoning engine, MCP tools perform external actions, and Notion is the persistent memory layer.
