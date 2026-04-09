# How to Run — Reel Knowledge Agent

## What this does
Send an Instagram or YouTube reel link to your Telegram bot.
It downloads the audio, transcribes it, extracts key concepts using GPT-4o,
and saves structured notes to your Notion database automatically.

---

## Prerequisites

- Python 3.10 or higher
- `ffmpeg` installed on your system
- All four API keys filled in `.env`

---

## Step 1 — Install ffmpeg

**macOS**
```bash
brew install ffmpeg
```

**Ubuntu / Debian**
```bash
sudo apt install ffmpeg
```

**Windows**
Download from https://ffmpeg.org/download.html and add it to your PATH.

---

## Step 2 — Create and activate virtual environment

```bash
cd /Users/work/Desktop/reel-knowledge-agent
python -m venv venv
```

**macOS / Linux**
```bash
source venv/bin/activate
```

**Windows**
```bash
venv\Scripts\activate
```

---

## Step 3 — Install dependencies

```bash
pip install mcp openai yt-dlp openai-whisper python-dotenv requests python-telegram-bot
```

---

## Step 4 — Fill in .env

Open `.env` and make sure all four values are present:

```
OPENAI_API_KEY=sk-...
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
```

See `API_KEYS.md` for instructions on obtaining each key.

---

## Step 5 — Share Notion database with your integration

This step is required before the bot can write to Notion.

1. Open your Notion database.
2. Click the `...` menu in the top-right corner.
3. Click **Connections** → **Add connection**.
4. Select your integration (the one you created in API_KEYS.md).
5. Click **Confirm**.

---

## Step 6 — Set up Notion database fields

Run this once to add the required `Topic` and `Subtopic` fields:

```bash
python setup_notion.py
```

Expected output:
```
Connected to database: <your database name>
Existing fields: ['Name']
Adding fields: ['Topic', 'Subtopic']
Done! Notion database is ready.
```

If you see an error, follow the instructions printed in the terminal.

---

## Step 7 — Test the agent (optional but recommended)

Before starting the bot, verify the full pipeline works:

```bash
python agent.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Watch the logs — it should:
1. `[agent] calling download_reel(...)` — downloads audio
2. `[agent] calling transcribe_audio(...)` — transcribes (first run downloads ~140MB Whisper model, takes a minute)
3. `[agent] calling get_existing_topics(...)` — reads Notion
4. `[agent] calling save_to_notion(...)` — saves the note
5. Print a bullet-point summary of key concepts

Then check your Notion database — a new page should appear.

---

## Step 8 — Start the Telegram bot

```bash
python bot.py
```

You should see:
```
Bot is running. Press Ctrl+C to stop.
```

Open Telegram, find your bot by its username, and send any YouTube or Instagram reel link:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

The bot will reply:
1. `Got it! Processing your reel...`
2. A structured summary with topic, subtopic, and key concepts

---

## Stopping the bot

Press `Ctrl+C` in the terminal.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `yt-dlp: command not found` | `pip install yt-dlp` |
| `ffmpeg not found` | Install ffmpeg (Step 1) |
| Whisper takes a long time on first run | It's downloading the model (~140MB) — wait it out |
| `Notion token is invalid` | Share the database with your integration (Step 5) |
| `Database not found` | Double-check `NOTION_DATABASE_ID` in `.env` |
| Bot doesn't respond on Telegram | Make sure `bot.py` is still running in the terminal |
| `OPENAI_API_KEY` error | Check the key is correct and billing is set up at platform.openai.com |

---

## File overview

```
reel-knowledge-agent/
├── server.py          # MCP server — download, transcribe, Notion tools
├── agent.py           # OpenAI agentic loop — drives the full pipeline
├── bot.py             # Telegram bot — receives links, calls agent
├── setup_notion.py    # One-time script — adds fields to Notion database
├── topic-map.md       # Topic classification rules used by the agent
├── API_KEYS.md        # How to obtain each API key
├── RUN.md             # This file
└── .env               # Your secret keys (never commit this)
```
