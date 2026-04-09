# Student Reference — Reel Knowledge Agent

Quick reference for implementation and debugging.

Diagrams: [README.md](README.md)

---

## Environment variables (`.env`)

Required:
- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `TELEGRAM_BOT_TOKEN`

---

## Required dependencies

Python packages:
- `mcp`
- `openai`
- `yt-dlp`
- `openai-whisper`
- `python-dotenv`
- `requests`
- `python-telegram-bot`

System dependency:
- `ffmpeg`

---

## Run sequence

1. **One-time Notion schema setup**
   - `python setup_notion.py`

2. **Single URL local test**
   - `python agent.py "<youtube_or_instagram_url>"`

3. **Telegram bot mode**
   - `python bot.py`

---

## Runtime call graph

`Telegram message`
→ `bot.handle_message()`
→ `agent.process_url(url)`
→ model tool-calls MCP tools in `server.py`
→ `save_to_notion(...)`
→ final message returned to Telegram

---

## Core files and purpose

- `bot.py`
  - Telegram polling and message handling.

- `agent.py`
  - OpenAI + MCP orchestration loop.
  - Enforces save attempt before final answer.

- `server.py`
  - MCP tools for download/transcribe/Notion read/write.

- `setup_notion.py`
  - Creates required Notion properties if missing.

---

## Tool signatures

- `download_reel(url: str) -> str`
- `transcribe_audio(file_path: str) -> str`
- `get_existing_topics() -> str`
- `save_to_notion(topic: str, subtopic: str, content: str) -> str`

---

## Notion schema expected

Database properties:
- `Name` (title)
- `Topic` (rich_text)
- `Subtopic` (rich_text)

---

## What happens if transcription fails locally?

`server.transcribe_audio()` tries:
1. Local Whisper model (`base`)
2. OpenAI transcription fallback (`gpt-4o-mini-transcribe`)

So the pipeline can still continue if local model download fails.

---

## Common issues and fixes

1. **Transcription works but not saved to Notion**
   - Check agent output for `save_to_notion` error.
   - Verify `NOTION_DATABASE_ID` matches shared DB.

2. **Notion 401 unauthorized**
   - Token invalid or integration not connected.

3. **Notion 404 database not found**
   - Wrong DB id format/value.

4. **Download fails**
   - Check `yt-dlp` and URL validity.

5. **Audio processing fails**
   - Ensure `ffmpeg` is installed.

---

## Minimal teaching pseudocode

1. Receive URL
2. Download audio
3. Transcribe text
4. Infer topic/subtopic and concepts
5. Save to Notion
6. Return confirmation

---

## Suggested improvements (student tasks)

- Add `Source URL` + `Created At` properties in Notion.
- Save transcript snippet in page body.
- Add retries around Notion API calls.
- Add timeout + cancellation handling in long tasks.
