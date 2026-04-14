# Product Requirements Document
## Reel Knowledge Agent

---

## 1. Product Overview

**Reel Knowledge Agent** is a Telegram bot that acts as a personal second brain for video content.
Send it any YouTube or Instagram reel link — it downloads the audio, transcribes it, extracts
structured knowledge using AI, saves the notes to your Notion database, and makes everything
searchable via semantic (meaning-based) queries.

**One-line pitch:**
> Turn any reel or video into a structured Notion note and query everything you've ever saved — from Telegram.

---

## 2. Problem Statement

```
┌─────────────────────────────────────────────────────────────────────┐
│                         THE PROBLEM                                 │
│                                                                     │
│   You watch 10 reels today          You remember 0 of them tomorrow │
│                                                                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│   │  Reel 1  │    │  Reel 2  │    │  Reel 3  │    │  Reel N  │     │
│   │ Tutorial │    │  Insight │    │   Tip    │    │  Talk    │     │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
│        │               │               │               │            │
│        └───────────────┴───────────────┴───────────────┘            │
│                                    │                                │
│                                    ▼                                │
│                          ┌──────────────────┐                       │
│                          │   Your Brain     │                       │
│                          │  (forgets 90%    │                       │
│                          │   in 24 hours)   │                       │
│                          └──────────────────┘                       │
│                                                                     │
│   Root causes:                                                      │
│   • No frictionless way to capture what was learned                 │
│   • Manual note-taking from video is slow and disruptive            │
│   • Even saved notes are hard to find by meaning (not keyword)      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         THE SOLUTION                                │
│                                                                     │
│   You watch a reel  →  Send the link  →  Get structured notes      │
│                                                                     │
│   ┌──────────┐                                  ┌───────────────┐  │
│   │  Reel    │──── 1 message in Telegram ───────▶│ Notion Note   │  │
│   │  Link    │                                  │ Topic         │  │
│   └──────────┘                                  │ Subtopic      │  │
│                                                  │ Key Concepts  │  │
│                                                  └───────────────┘  │
│                                                         +           │
│                                                  ┌───────────────┐  │
│                                                  │ Qdrant Vector │  │
│                                                  │ (searchable   │  │
│                                                  │  by meaning)  │  │
│                                                  └───────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Objectives

| # | Objective | Success Metric |
|---|---|---|
| O1 | Capture knowledge from any reel with zero manual effort | User sends one URL, receives structured notes |
| O2 | Organise notes consistently across sessions | All notes have Topic + Subtopic; reuse existing categories |
| O3 | Make stored knowledge retrievable by meaning | Semantic search returns relevant past reels for any question |
| O4 | Run entirely on the user's own machine | No cloud accounts beyond the 4 required API keys |
| O5 | Stay resilient under failures | System recovers from crashes; no data loss across restarts |

---

## 4. Users & Use Cases

### Primary User
A developer, student, or knowledge worker who:
- Consumes YouTube / Instagram content regularly
- Uses Notion as their primary knowledge base
- Prefers Telegram as a low-friction interface
- Wants to avoid manual copy-paste workflows

---

### Use Case 1 — Ingest a YouTube or Instagram Reel

```
  USER                        SYSTEM                        OUTPUTS
  ────                        ──────                        ───────

  Finds a useful reel
        │
        │  Sends URL to Telegram bot
        ▼
  ┌─────────────┐
  │  Telegram   │──── "Got it! Processing..." ────────────▶ User sees
  │    Bot      │                                           acknowledgement
  └──────┬──────┘
         │
         │  Downloads audio (yt-dlp)
         │  Transcribes speech (Whisper)
         │  Extracts key concepts (GPT-4o)
         │
         ├──────────────────────────────────────────────▶ ┌─────────────┐
         │                                                 │Notion Note  │
         │  Saves structured note                         │─────────────│
         │                                                │Topic        │
         │                                                │Subtopic     │
         │                                                │Key Concepts │
         │                                                │Summary      │
         │                                                └─────────────┘
         │
         ├──────────────────────────────────────────────▶ ┌─────────────┐
         │                                                 │Qdrant Vector│
         │  Stores embedding                              │(searchable  │
         │                                                │ by meaning) │
         │                                                └─────────────┘
         │
         │  Sends summary back
         ▼
  ┌─────────────┐
  │  Telegram   │◀─── Topic, Subtopic, Bullet Points ─────  User gets
  │    Bot      │                                           summary reply
  └─────────────┘
```

---

### Use Case 2 — Query Saved Knowledge (RAG)

```
  USER                        SYSTEM                        OUTPUTS
  ────                        ──────                        ───────

  Wants to recall something
        │
        │  Asks question in Telegram
        │  e.g. "What did I learn about habits?"
        ▼
  ┌─────────────┐
  │  Telegram   │
  │    Bot      │
  └──────┬──────┘
         │
         │  Converts question to vector
         │  Searches Qdrant by meaning
         │
         │  ┌─────────────────────────────────────────┐
         │  │ Qdrant returns top-5 similar reels      │
         │  │                                         │
         │  │  Score 0.91 — Habits & Routines         │
         │  │  Score 0.87 — Personal Development      │
         │  │  Score 0.74 — Mindset & Psychology      │
         │  └─────────────────────────────────────────┘
         │
         │  GPT-4o reads context and writes answer
         │
         ▼
  ┌─────────────┐
  │  Telegram   │◀─── Synthesised answer + sources ──── User gets
  │    Bot      │                                        relevant answer
  └─────────────┘
```

---

## 5. Functional Requirements

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     FUNCTIONAL REQUIREMENTS MAP                         │
│                                                                         │
│  ┌──────────┐  FR1  ┌──────────┐  FR2  ┌──────────┐  FR3  ┌─────────┐ │
│  │  User    │──────▶│ Validate │──────▶│ Download │──────▶│Transcrib│ │
│  │ sends URL│       │  URL     │       │  Audio   │       │  Audio  │ │
│  └──────────┘       │ (regex)  │       │ (yt-dlp) │       │(Whisper)│ │
│                     └──────────┘       └──────────┘       └────┬────┘ │
│                                                                 │      │
│                          FR8           FR4                      │      │
│                     ┌──────────┐  ┌──────────────┐             │      │
│                     │ Reuse    │  │  Extract     │◀────────────┘      │
│                     │ existing │  │  concepts,   │                    │
│                     │ topics   │  │  topic,      │                    │
│                     │(Notion)  │  │  subtopic    │                    │
│                     └────┬─────┘  │  (GPT-4o)    │                    │
│                          └────────▶└──────┬───────┘                   │
│                                           │                           │
│                          ┌────────────────┴────────────────┐          │
│                          │                                 │          │
│                    FR5   ▼                           FR6   ▼          │
│               ┌──────────────────┐         ┌──────────────────┐       │
│               │  Save to Notion  │         │  Embed in Qdrant │       │
│               │  (Name, Topic,   │         │  (vector for     │       │
│               │   Subtopic,      │         │   semantic       │       │
│               │   Summary)       │         │   search)        │       │
│               └──────────────────┘         └──────────────────┘       │
│                          │                                 │          │
│                          └────────────┬────────────────────┘          │
│                                       │                               │
│                                FR9    ▼                               │
│                          ┌────────────────────┐                       │
│                          │  Send summary back │                       │
│                          │  to Telegram user  │                       │
│                          │  (async via Redis) │                       │
│                          └────────────────────┘                       │
│                                                                       │
│  FR7: get_similar_reels() — used for retrieval queries (separate flow)│
└─────────────────────────────────────────────────────────────────────────┘
```

| ID | Requirement | Implemented In |
|---|---|---|
| FR1 | Accept YouTube and Instagram reel URLs sent via Telegram | `bot.py` — URL_RE regex |
| FR2 | Download audio from URL using yt-dlp; save to `/tmp/reels/audio.mp3` | `server.py` → `download_reel()` |
| FR3 | Transcribe audio using local Whisper model; fall back to OpenAI API on failure | `server.py` → `transcribe_audio()` |
| FR4 | Extract 3–7 key concepts, a topic, and a subtopic from transcript using GPT-4o | `agent.py` → agentic loop |
| FR5 | Save structured note to Notion with Name, Topic, Subtopic, and bullet-point body | `server.py` → `save_to_notion()` |
| FR6 | Embed transcript into Qdrant vector store for future semantic retrieval | `server.py` → `embed_and_store()` |
| FR7 | Return semantically similar past reels given a natural-language query | `server.py` → `get_similar_reels()` |
| FR8 | Read existing Notion topics before classifying; reuse matching topic/subtopic | `server.py` → `get_existing_topics()` |
| FR9 | Process jobs asynchronously — bot stays responsive while agent works | `bot.py` + Redis queue + `agent.py` |

---

## 6. Non-Functional Requirements

```
┌─────────────────────────────────────────────────────────────────────┐
│                   NON-FUNCTIONAL REQUIREMENTS                       │
│                                                                     │
│  NFR1 LOCAL-FIRST                                                   │
│  ┌─────────────────────────────────────────────┐                   │
│  │  Your Machine                               │                   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐ │                   │
│  │  │ Redis  │ │ Qdrant │ │  Bot   │ │Agent │ │                   │
│  │  │(Docker)│ │(Docker)│ │(Docker)│ │(Dock)│ │                   │
│  │  └────────┘ └────────┘ └────────┘ └──────┘ │                   │
│  └─────────────────────────────────────────────┘                   │
│  Only 4 external APIs needed. No cloud infra.                      │
│                                                                     │
│  NFR2 RESILIENT                                                     │
│  ┌──────────────────────────────────┐                              │
│  │  Container crashes → auto-restart│                              │
│  │  Tool fails → error string back  │                              │
│  │  Timeout → user notified         │                              │
│  └──────────────────────────────────┘                              │
│                                                                     │
│  NFR3 PERSISTENT                                                    │
│  ┌──────────────────────────────────┐                              │
│  │  redis_data volume  → queue safe │                              │
│  │  qdrant_data volume → RAG safe   │                              │
│  │  docker compose down → data kept │                              │
│  └──────────────────────────────────┘                              │
│                                                                     │
│  NFR4 DECOUPLED                                                     │
│  ┌──────────────────────────────────┐                              │
│  │  bot.py  ──Redis──▶ agent.py     │                              │
│  │  No shared code. No imports.     │                              │
│  │  Only shared: Redis key names    │                              │
│  └──────────────────────────────────┘                              │
│                                                                     │
│  NFR5 SECURE                                                        │
│  ┌──────────────────────────────────┐                              │
│  │  .env never copied into image    │                              │
│  │  Secrets injected at runtime     │                              │
│  │  .dockerignore excludes .env     │                              │
│  └──────────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

| ID | Requirement | How It Is Met |
|---|---|---|
| NFR1 | **Local-first** — system runs on developer's machine with no cloud infra | 4-container Docker Compose; Redis and Qdrant run locally |
| NFR2 | **Resilient** — individual component failures do not crash the whole system | `restart: unless-stopped` on all containers; worker catches exceptions |
| NFR3 | **Persistent** — stored knowledge survives container restarts | Named Docker volumes for `redis_data` and `qdrant_data` |
| NFR4 | **Decoupled** — bot and agent share no code or process boundary | Bot and agent communicate only via Redis list keys |
| NFR5 | **Secure** — no API secrets baked into Docker image | Secrets loaded from `.env` at runtime; never in Dockerfile |
| NFR6 | **Idempotent setup** — one-time Notion schema setup is safe to re-run | `setup_notion.py` checks existing properties before adding |
| NFR7 | **Scalable worker** — can process multiple jobs in parallel if needed | Agent is stateless; `docker compose up --scale agent=N` works |

---

## 7. Out of Scope

```
┌─────────────────────────────────────────────────────┐
│                   OUT OF SCOPE                      │
│                                                     │
│   ✗  Web UI or dashboard                           │
│   ✗  Multi-user support / authentication           │
│   ✗  Cloud deployment (AWS, GCP, Railway, etc.)    │
│   ✗  Audio file uploads directly to Telegram       │
│   ✗  Plain text input (no URL)                     │
│   ✗  Scheduled / batch ingestion                   │
│   ✗  Notion database creation (user creates it)    │
│   ✗  Editing or deleting existing Notion notes     │
└─────────────────────────────────────────────────────┘
```

---

## 8. Assumptions & Constraints

| Assumption / Constraint | Detail |
|---|---|
| Docker is installed | `docker compose up` is the only run command |
| 4 API keys are available | OpenAI, Notion token, Notion DB ID, Telegram bot token |
| Notion DB is pre-created | `setup_notion.py` adds fields; it does not create the database |
| One agent worker by default | One job processes at a time; scale with `--scale agent=N` |
| Audio must be downloadable by yt-dlp | Private/DRM-protected content will fail at download step |
| First Whisper run downloads ~140 MB | `base` model downloads once and is cached |
| yt-dlp + ffmpeg must be present | Installed in Dockerfile; not required on host |

---

## 9. Tech Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TECH STACK                                  │
│                                                                     │
│  INTERFACE LAYER                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Telegram Bot API  +  python-telegram-bot 22.7             │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│  QUEUE LAYER                 ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Redis 7 (Alpine)  —  RPUSH / BLPOP job queue              │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│  AI LAYER                    ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  OpenAI GPT-4o  —  reasoning, tool calling, extraction     │    │
│  │  Anthropic MCP (FastMCP 1.27.0)  —  tool protocol          │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│  MEDIA LAYER                 ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  yt-dlp 2026.3.17 + ffmpeg  —  audio download              │    │
│  │  openai-whisper 20250625   —  local transcription           │    │
│  │  OpenAI Whisper API        —  fallback transcription        │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│  STORAGE LAYER               ▼                                      │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  Notion API v1              │  │  Qdrant v1.14.0             │  │
│  │  Structured notes           │  │  Vector embeddings (1536d)  │  │
│  │  (Title, Topic, Subtopic)   │  │  Cosine similarity search   │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  RUNTIME                                                            │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Docker Compose 3.9  —  4 containers, local orchestration  │    │
│  │  Python 3.11                                               │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Version | Role |
|---|---|---|---|
| Interface | Telegram Bot API | — | User-facing input/output |
| Bot framework | python-telegram-bot | 22.7 | Polling, message handling |
| Job queue | Redis | 7 (Alpine) | Async decoupling of bot and agent |
| AI orchestration | OpenAI GPT-4o | gpt-4o | Reasoning, concept extraction, tool calling |
| Tool protocol | Anthropic MCP (FastMCP) | 1.27.0 | Standardised tool interface between agent and server |
| Audio download | yt-dlp + ffmpeg | 2026.3.17 | Extract audio from YouTube / Instagram |
| Transcription | openai-whisper (local) + OpenAI API | 20250625 | Speech-to-text with fallback |
| Embeddings | OpenAI text-embedding-3-small | — | 1536-dim vectors for semantic search |
| Knowledge store | Notion API | v1 (2022-06-28) | Persistent structured notes |
| Vector store | Qdrant | v1.14.0 | Semantic search over stored transcripts |
| Runtime | Docker Compose | 3.9 | 4-container local orchestration |
| Language | Python | 3.11 | All application code |
