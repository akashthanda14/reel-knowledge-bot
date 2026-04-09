# Reel Knowledge Bot

> Send an Instagram or YouTube reel link to a Telegram bot → get structured learning notes saved automatically to Notion.

---

## How it works

```
Telegram user
     │  sends reel URL
     ▼
  bot.py          ← Telegram interface
     │
     ▼
  agent.py        ← OpenAI GPT-4o agentic loop
     │  starts MCP server over stdio
     ▼
  server.py       ← MCP tool server
     ├── download_reel(url)        → yt-dlp → /tmp/reels/audio.mp3
     ├── transcribe_audio(path)   → local Whisper (OpenAI API fallback)
     ├── get_existing_topics()    → reads Notion DB
     └── save_to_notion(...)      → writes structured notes to Notion
```

The agent:
1. Downloads the audio from the reel using `yt-dlp`.
2. Transcribes it locally with OpenAI Whisper (falls back to the OpenAI API if needed).
3. Checks existing Notion topics so it can reuse them rather than create duplicates.
4. Extracts 3–7 key concepts, assigns a topic/subtopic, and writes the note to Notion.
5. Replies to Telegram with a bullet-point summary.

---

## Stack

| Layer | Technology |
|---|---|
| Telegram interface | `python-telegram-bot` |
| AI orchestration | OpenAI GPT-4o (tool calling) |
| Tool protocol | Anthropic MCP (stdio) |
| Audio download | `yt-dlp` + `ffmpeg` |
| Transcription | `openai-whisper` / OpenAI API |
| Knowledge store | Notion API |

---

## Quick start

### 1. Prerequisites

- Python 3.10+
- `ffmpeg` installed and on `PATH` (`brew install ffmpeg` on macOS)
- A [Telegram bot token](https://core.telegram.org/bots#botfather)
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Notion integration token](https://www.notion.so/my-integrations) with access to your database

### 2. Clone & install

```bash
git clone https://github.com/akashthanda14/reel-knowledge-bot.git
cd reel-knowledge-bot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-...
```

### 4. Set up Notion

Create a Notion database (or use an existing one) and share it with your integration.
Then run the one-time setup script to add the required `Topic` and `Subtopic` fields:

```bash
python setup_notion.py
```

### 5. Start the bot

```bash
python bot.py
```

Send any Instagram reel or YouTube Shorts link to your bot in Telegram.

---

## Project structure

```
reel-knowledge-bot/
├── server.py          # MCP tool server — all four tools live here
├── agent.py           # OpenAI agentic loop — orchestrates the tools
├── bot.py             # Telegram bot — entry point for users
├── setup_notion.py    # One-time Notion database setup
├── test_server.py     # Smoke tests for MCP tools
├── topic-map.md       # Topic classification rules used by the agent
├── requirements.txt
├── .env.example
└── docs/
    ├── ARCHITECTURE_DIAGRAMS.md
    ├── TEACHING_GUIDE.md
    └── STUDENT_REFERENCE.md
```

---

## Topic classification

The agent uses `topic-map.md` to assign a **topic** and **subtopic** to each reel.
Current top-level topics:

- Technology
- Business & Finance
- Science
- Personal Development
- Health & Fitness
- Arts & Culture
- Cooking & Food
- Travel & Geography

See [`topic-map.md`](topic-map.md) for the full classification rules.

---

## Architecture details

See [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) for sequence diagrams and the agentic loop walkthrough.

---

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o + Whisper fallback) |
| `NOTION_TOKEN` | Notion integration secret |
| `NOTION_DATABASE_ID` | ID of the Notion database to write notes into |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |

---

## Running without Telegram

You can run the agent directly from the command line:

```bash
python agent.py https://www.youtube.com/shorts/XXXXXXXXXXX
```

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit your changes
4. Open a pull request

---

## License

MIT
