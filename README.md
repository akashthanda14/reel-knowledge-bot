# Reel Knowledge Bot

> Send an Instagram or YouTube reel link to a Telegram bot → get structured learning notes saved to Notion, with semantic search over everything you've stored.

---

## How it works

```
Telegram user
     │  sends reel URL
     ▼
  bot.py          ← Telegram interface — validates URL, pushes job to Redis
     │
     ▼
  Redis           ← job queue (jobs:pending list)
     │
     ▼
  agent.py        ← worker loop — pops job, runs MCP pipeline
     │  starts MCP server over stdio
     ▼
  server.py       ← MCP tool server
     ├── download_reel(url)             → yt-dlp → /tmp/reels/audio.mp3
     ├── transcribe_audio(path)         → local Whisper (OpenAI API fallback)
     ├── get_existing_topics()          → reads Notion DB
     ├── save_to_notion(...)            → writes structured notes to Notion
     ├── embed_and_store(text, meta)    → OpenAI embeddings → Qdrant
     └── get_similar_reels(query)       → Qdrant semantic search
```

The agent:
1. Downloads the audio from the reel using `yt-dlp`.
2. Transcribes it locally with OpenAI Whisper (falls back to the OpenAI API if needed).
3. Checks existing Notion topics so it reuses them rather than creating duplicates.
4. Extracts 3–7 key concepts, assigns a topic/subtopic, and writes the note to Notion.
5. Embeds the transcript and stores it in Qdrant for future semantic search.
6. Replies to Telegram with a bullet-point summary.

---

## Stack

| Layer | Technology |
|---|---|
| Telegram interface | `python-telegram-bot` |
| Job queue | Redis (`jobs:pending` list) |
| AI orchestration | OpenAI GPT-4o (tool calling) |
| Tool protocol | Anthropic MCP (stdio) |
| Audio download | `yt-dlp` + `ffmpeg` |
| Transcription | `openai-whisper` / OpenAI API |
| Knowledge store | Notion API |
| Vector store | Qdrant (semantic RAG search) |
| Runtime | Docker Compose (4 containers) |

---

## Quick start

### 1. Prerequisites

- Docker + Docker Compose
- A [Telegram bot token](https://core.telegram.org/bots#botfather)
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Notion integration token](https://www.notion.so/my-integrations) with access to your database

See [`docs/API_KEYS.md`](docs/API_KEYS.md) for step-by-step instructions on obtaining each key.

### 2. Configure environment

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

### 3. Set up Notion schema (one time)

```bash
python setup_notion.py
```

### 4. Start all containers

```bash
docker compose up --build
```

This starts 4 containers: `redis`, `qdrant`, `bot`, `agent`.

Send any Instagram reel or YouTube Shorts link to your bot in Telegram.

---

## Project structure

```
reel-knowledge-bot/
├── server.py          # MCP tool server — all tools live here
├── agent.py           # OpenAI agentic loop + Redis worker
├── bot.py             # Telegram bot — pushes jobs to Redis
├── qdrant_helper.py   # Qdrant client setup and collection init
├── setup_notion.py    # One-time Notion database setup
├── test_server.py     # Smoke tests for MCP tools
├── docker-compose.yml # 4-container runtime (redis, qdrant, bot, agent)
├── Dockerfile
├── requirements.txt
├── .env.example
└── docs/
    ├── topic-map.md               # Topic classification rules
    ├── API_KEYS.md                # How to obtain each API key
    ├── REDIS_ARCHITECTURE.md      # Why Redis queue was added
    ├── DOCKER_INTRO.md            # What Docker is and why it's used
    ├── COSINE_VS_EUCLIDEAN.md     # Qdrant distance metrics explained
    ├── SIMILARITY_SCORES.md       # How similarity scores work
    ├── PRD.md                     # Product requirements
    ├── HLD.md                     # High level design
    └── LLD.md                     # Low level design
```

---

## Topic classification

The agent uses [`docs/topic-map.md`](docs/topic-map.md) to assign a **topic** and **subtopic** to each reel.
Current top-level topics: Technology, Business & Finance, Science, Personal Development, Health & Fitness, Arts & Culture, Cooking & Food, Travel & Geography.

---

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o + Whisper fallback + embeddings) |
| `NOTION_TOKEN` | Notion integration secret |
| `NOTION_DATABASE_ID` | ID of the Notion database to write notes into |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |

`REDIS_URL` and `QDRANT_URL` are set automatically by Docker Compose and do not need to go in `.env`.

---

## License

MIT
