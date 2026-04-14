# High Level Design
## Reel Knowledge Agent

---

## 1. System Overview

Reel Knowledge Agent is a 4-container system that decouples user interaction from AI processing.
The Telegram bot (bot.py) receives reel URLs and pushes them to a Redis job queue. An AI worker
(agent.py) pulls jobs, runs a full MCP-based pipeline — download → transcribe → classify →
save to Notion → embed in Qdrant — then pushes the result back through Redis for the bot to
return to the user. All containers run locally via Docker Compose.

---

## 2. Container Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         Docker Compose Network                                   ║
║                                                                                  ║
║   ┌─────────────────────────────────┐   ┌──────────────────────────────────┐    ║
║   │          bot container          │   │         agent container          │    ║
║   │                                 │   │                                  │    ║
║   │  ┌──────────────────────────┐   │   │  ┌────────────────────────────┐  │    ║
║   │  │        bot.py            │   │   │  │        agent.py            │  │    ║
║   │  │                          │   │   │  │                            │  │    ║
║   │  │  - Receives Telegram msgs│   │   │  │  - Pops jobs from Redis    │  │    ║
║   │  │  - Validates URLs        │   │   │  │  - Runs OpenAI agent loop  │  │    ║
║   │  │  - Pushes jobs to Redis  │   │   │  │  - Starts server.py (MCP)  │  │    ║
║   │  │  - Waits for results     │   │   │  │  - Pushes results to Redis │  │    ║
║   │  │  - Sends Telegram reply  │   │   │  │                            │  │    ║
║   │  └──────────────────────────┘   │   │  └────────────┬───────────────┘  │    ║
║   └───────────┬─────────────────────┘   └───────────────┼──────────────────┘    ║
║               │                                         │ stdio subprocess      ║
║               │                                         ▼                       ║
║               │                         ┌──────────────────────────────────┐    ║
║               │                         │        server.py process         │    ║
║               │                         │         (MCP tool server)        │    ║
║               │                         │                                  │    ║
║               │                         │  download_reel    → yt-dlp       │    ║
║               │                         │  transcribe_audio → Whisper      │    ║
║               │                         │  get_existing_topics → Notion    │    ║
║               │                         │  save_to_notion  → Notion        │    ║
║               │                         │  embed_and_store → Qdrant        │    ║
║               │                         │  get_similar_reels → Qdrant      │    ║
║               │                         └──────────────────────────────────┘    ║
║               │                                                                  ║
║   ┌───────────┴─────────────────────────────────────────────────────────────┐   ║
║   │                                Redis                                    │   ║
║   │              jobs:pending (FIFO list)    result:{id} (ephemeral key)    │   ║
║   └─────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                  ║
║   ┌─────────────────────────────────────────────────────────────────────────┐   ║
║   │                               Qdrant                                    │   ║
║   │              "reels" collection — 1536-dim Cosine vectors               │   ║
║   └─────────────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════════════╝

Outside Docker:
  ┌───────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
  │ Telegram API  │   │  OpenAI API  │   │  Notion API  │   │  YouTube/Insta   │
  │  (long poll)  │   │  GPT-4o      │   │  REST v1     │   │  (yt-dlp target) │
  │               │   │  Whisper     │   │              │   │                  │
  │               │   │  Embeddings  │   │              │   │                  │
  └───────────────┘   └──────────────┘   └──────────────┘   └──────────────────┘
```

---

## 3. Container Startup Order

Docker Compose starts containers in dependency order. `bot` and `agent` both wait for
`redis` and `qdrant` to pass their health checks before starting.

```
  docker compose up --build
         │
         ▼
  ┌──────────────┐     ┌──────────────┐
  │    redis     │     │    qdrant    │
  │  starts up   │     │  starts up   │
  │              │     │              │
  │  health      │     │  health      │
  │  check: OK   │     │  check: OK   │
  └──────┬───────┘     └──────┬───────┘
         │                    │
         └──────────┬─────────┘
                    │ both healthy
                    ▼
         ┌──────────────────────────────┐
         │  bot  starts     agent starts │
         │  (depends_on:    (depends_on: │
         │   redis+qdrant)  redis+qdrant)│
         └──────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │  bot: polling Telegram       │
         │  agent: blocking on BLPOP    │
         │  System ready                │
         └──────────────────────────────┘
```

---

## 4. Ingest Flow — Reel URL to Notion + Qdrant

End-to-end path when a user sends a reel URL to the Telegram bot.

```
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  USER                                                                        │
  │  sends: https://youtube.com/shorts/abc123                                    │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │ Telegram message
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  bot.py                                                                      │
  │                                                                              │
  │  1. Extract text from Telegram update                                        │
  │  2. Match against URL_RE regex                                               │
  │     ┌─── no match ──► reply "Please send a valid reel link." → STOP         │
  │     │                                                                        │
  │  3. (match) url = regex match group(0)                                       │
  │  4. job_id = uuid4()                                                         │
  │  5. payload = {"job_id": job_id, "url": url}                                 │
  │  6. RPUSH  jobs:pending  payload          ──────────────────► Redis          │
  │  7. reply "Got it! Processing your reel..."                                  │
  │  8. BLPOP  result:{job_id}  timeout=300s  ◄────────────────── Redis          │
  │     ┌─── timeout ──► reply "Processing timed out." → STOP                   │
  │     │                                                                        │
  │  9. (result) send data["text"] to Telegram user                             │
  └──────────────────────────────────────────────────────────────────────────────┘
                         │ RPUSH / BLPOP
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  Redis  jobs:pending list                                                    │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │ BLPOP (agent was blocking)
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  agent.py  — process_url(url)                                                │
  │                                                                              │
  │  1. Start server.py as MCP stdio subprocess                                  │
  │  2. session.initialize()                                                     │
  │  3. tools = session.list_tools()   → 6 tool schemas                         │
  │  4. openai_tools = _mcp_tools_to_openai(tools)                               │
  │  5. messages = [system_prompt, user_url]                                     │
  │  6. Enter agentic loop  ──────────────────────────────────────────────────┐  │
  │     (see Section 4a below)                                                │  │
  │                                                                           │  │
  │  7. Push result to Redis   RPUSH result:{job_id}  {"text": "..."}  ◄─────┘  │
  │  8. EXPIRE result:{job_id} 600                                               │
  └──────────────────────────────────────────────────────────────────────────────┘
```

### 4a. Agentic Loop Inside agent.py

```
                    messages = [system, url]
                         │
                         ▼
              ┌─────────────────────┐
              │  OpenAI GPT-4o      │
              │  chat.completions   │
              │  .create(messages,  │
              │   tools=openai_tools│
              │   tool_choice=auto) │
              └──────────┬──────────┘
                         │
              ┌──────────┴─────────────────────────┐
              │                                    │
    tool_calls present                   no tool_calls (final)
              │                                    │
              ▼                                    ▼
  ┌──────────────────────┐            ┌───────────────────────────┐
  │ for each tool_call:  │            │ notion_saved == True?      │
  │                      │            │                            │
  │  name = call.name    │            │  YES → return msg.content  │
  │  args = call.args    │            │                            │
  │                      │            │  NO  → append              │
  │  result =            │            │   "You must call           │
  │  session.call_tool() │            │    save_to_notion first"   │
  │                      │            │   loop again ──────────────┼──► GPT-4o
  │  if name ==          │            └───────────────────────────┘
  │   "save_to_notion"   │
  │    → notion_saved=True
  │                      │
  │  if name ==          │
  │   "embed_and_store"  │
  │    → embedded=True   │
  │                      │
  │  append assistant msg│
  │  append tool result  │
  └──────────┬───────────┘
             │
             └──────────────────────────────────────────────► GPT-4o (next turn)
```

### 4b. server.py Tool Execution Chain

```
  GPT-4o decides:  download_reel
         │
         ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  download_reel(url)                                            │
  │  subprocess: yt-dlp -x --audio-format mp3 → /tmp/reels/audio  │
  │  returns: "/tmp/reels/audio.mp3"                               │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  GPT-4o decides:  transcribe_audio("/tmp/reels/audio.mp3")
                                  │
                                  ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  transcribe_audio(file_path)                                   │
  │                                                                │
  │  try:                                                          │
  │    whisper.load_model("base")                                  │
  │    model.transcribe(file_path)  → transcript text              │
  │  except:                                                       │
  │    openai.audio.transcriptions.create(gpt-4o-mini-transcribe)  │
  │  finally:                                                      │
  │    os.remove(file_path)         ← always deletes temp audio    │
  │                                                                │
  │  returns: full transcript text                                 │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  GPT-4o decides:  get_existing_topics()
                                  │
                                  ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  get_existing_topics()                                         │
  │  POST Notion API /databases/{id}/query                         │
  │  extract Topic + Subtopic from each page                       │
  │  returns: "Technology / AI\nBusiness / Investing\n..."         │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  GPT-4o reasons: picks topic/subtopic, extracts key concepts
                                  │
  GPT-4o decides:  save_to_notion(topic, subtopic, content)
                                  │
                                  ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  save_to_notion(topic, subtopic, content)                      │
  │  POST Notion API /pages  with Name, Topic, Subtopic, body      │
  │  returns: "https://notion.so/..."                              │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  GPT-4o decides:  embed_and_store(text, topic, subtopic, url, summary)
                                  │
                                  ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  embed_and_store(text, metadata)                               │
  │  → qdrant_helper.store_reel(text, metadata)                    │
  │    → embed_text(text)                                          │
  │        openai.embeddings.create(text-embedding-3-small)        │
  │        → 1536-dim float vector                                 │
  │    → qdrant.upsert(point_id=uuid4, vector, payload)            │
  │  returns: uuid string                                          │
  └───────────────────────────────┬────────────────────────────────┘
                                  │
  GPT-4o produces final text reply (no more tool_calls)
                                  │
                                  ▼
            agent.py RPUSH result:{job_id} → Redis → bot.py → Telegram
```

---

## 5. Retrieval Flow — Semantic Search

When a user asks a question about previously ingested reels.

```
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  USER                                                                        │
  │  asks: "What did I learn about habit formation?"                             │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │ Telegram message (same handler as ingest)
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  bot.py → Redis RPUSH → agent.py                                             │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  agent.py agentic loop                                                       │
  │                                                                              │
  │  GPT-4o interprets the message as a retrieval question                       │
  │  GPT-4o decides: get_similar_reels(query, limit=5)                           │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  get_similar_reels(query, limit=5)                                           │
  │                                                                              │
  │  qdrant_helper.search_reels(query, limit)                                    │
  │    embed_text(query) → 1536-dim query vector                                 │
  │    qdrant.query_points(collection="reels", query=vector, limit=5)            │
  │    → top-5 nearest neighbours by Cosine similarity                           │
  │                                                                              │
  │  format each result:                                                         │
  │    "Score: 0.92 | Technology / AI                                            │
  │     Summary: • LLMs use attention...                                         │
  │     Source: https://youtube.com/..."                                         │
  │                                                                              │
  │  returns: formatted string of top-5 hits                                     │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │  GPT-4o synthesises answer from returned context                             │
  │  produces: natural language answer with citations                            │
  └──────────────────────┬───────────────────────────────────────────────────────┘
                         │
                         ▼
              agent.py → Redis → bot.py → Telegram user
```

---

## 6. Redis Queue — Data Flow

```
  bot.py                    Redis                   agent.py
     │                        │                        │
     │  RPUSH jobs:pending     │                        │  BLPOP jobs:pending
     │  {"job_id":"abc",       │                        │  (blocking, timeout=0)
     │   "url":"https://..."}  │                        │
     │────────────────────────►│                        │
     │                        │◄───────────────────────│
     │                        │  job popped            │
     │                        │                        │  process...
     │                        │                        │
     │  BLPOP result:abc       │                        │  RPUSH result:abc
     │  (blocking, timeout=300)│                        │  {"text":"...summary..."}
     │◄────────────────────────│◄───────────────────────│
     │  wakes up with result   │                        │
     │                        │                        │  EXPIRE result:abc 600
     │                        │                        │────────────────────────►│
     │                        │                        │
  send to Telegram

  Key lifecycle:
  ┌──────────────────────────────────────────────────────────────┐
  │ jobs:pending    →  persists until BLPOP pops it              │
  │ result:{id}     →  created by agent; deleted by BLPOP in bot │
  │                    or auto-deleted after EXPIRE (600s)        │
  └──────────────────────────────────────────────────────────────┘
```

---

## 7. Component Responsibilities

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         Component Boundaries                            │
  │                                                                         │
  │  ┌──────────────────┐  Redis only  ┌───────────────────────────────┐   │
  │  │     bot.py       │◄────────────►│           agent.py            │   │
  │  │                  │              │                               │   │
  │  │ - Telegram I/O   │              │ - Redis consumer              │   │
  │  │ - URL validation │              │ - OpenAI orchestration        │   │
  │  │ - Job producer   │              │ - MCP client                  │   │
  │  │ - Result consumer│              │ - No Telegram, no Notion      │   │
  │  └──────────────────┘              └─────────────┬─────────────────┘   │
  │                                                  │ stdio               │
  │                                                  ▼                     │
  │                                   ┌──────────────────────────────┐    │
  │                                   │         server.py            │    │
  │                                   │                              │    │
  │                                   │ - 6 MCP tools                │    │
  │                                   │ - yt-dlp, Whisper            │    │
  │                                   │ - Notion API calls           │    │
  │                                   │ - No reasoning, no queuing   │    │
  │                                   └──────────────┬───────────────┘    │
  │                                                  │ import              │
  │                                                  ▼                     │
  │                                   ┌──────────────────────────────┐    │
  │                                   │      qdrant_helper.py        │    │
  │                                   │                              │    │
  │                                   │ - embed_text()               │    │
  │                                   │ - store_reel()               │    │
  │                                   │ - search_reels()             │    │
  │                                   │ - No business logic          │    │
  │                                   └──────────────────────────────┘    │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. External Integrations

| Service | Used By | Purpose | Protocol |
|---|---|---|---|
| Telegram Bot API | bot.py | Receive messages, send replies | Long polling (HTTP) |
| OpenAI GPT-4o | agent.py | Reasoning, concept extraction, tool orchestration | REST API |
| OpenAI Whisper API | server.py (fallback) | Transcription when local Whisper fails | REST API |
| OpenAI Embeddings | qdrant_helper.py | text-embedding-3-small → 1536-dim vector | REST API |
| Notion API v1 | server.py | Read topics, create pages | REST API (requests) |
| yt-dlp | server.py | Download audio from YouTube / Instagram | subprocess |
| ffmpeg | server.py (via yt-dlp) | Audio conversion/muxing | subprocess (via yt-dlp) |

---

## 9. Key Design Decisions

### D1 — Redis queue instead of direct Python import

```
  REJECTED approach:          CHOSEN approach:
  ┌──────────────────┐        ┌──────────┐    Redis    ┌───────────┐
  │ bot.py           │        │  bot.py  │◄───────────►│ agent.py  │
  │  imports agent.py│        └──────────┘             └───────────┘
  │  calls function  │
  └──────────────────┘        Why: crash isolation, FIFO persistence,
  Shared process = one         horizontal scale (--scale agent=N),
  crash kills both.            no shared code.
```

**Rationale:** RPUSH+BLPOP is a persistent queue — jobs survive agent restart. Pub/Sub
would be lossy. Explicit job_id → result key prevents concurrent users seeing wrong results.

---

### D2 — MCP (Model Context Protocol) for tools

```
  REJECTED approach:          CHOSEN approach:
  ┌──────────────────┐        ┌──────────────────┐  stdio  ┌────────────────┐
  │ agent.py         │        │    agent.py       │◄───────►│   server.py    │
  │  directly imports│        │  (MCP client)     │         │  (MCP server)  │
  │  and calls tools │        └──────────────────┘         └────────────────┘
  └──────────────────┘
  Bug in tool crashes          Subprocess boundary: tool bug cannot crash agent.
  the agent.                   Standard JSON tool schema passed directly to OpenAI.
```

---

### D3 — Local Whisper with OpenAI API fallback

```
  transcribe_audio() called
         │
         ▼
  ┌──────────────────────────┐
  │  try: whisper.load_model │     ← free, works offline, ~140MB base model
  │        .transcribe()     │
  └─────────────┬────────────┘
                │
       success? ├──► YES → return transcript
                │
               NO (SSL error, download failure, etc.)
                │
                ▼
  ┌──────────────────────────┐
  │  fallback:               │     ← costs ~$0.006/min, requires internet
  │  openai.audio.           │
  │  transcriptions.create() │
  └─────────────┬────────────┘
                │
                ▼
           return transcript
```

---

### D4 — Qdrant Cosine distance

```
  text-embedding-3-small produces vectors optimised for Cosine similarity.

  Cosine similarity: measures angle between vectors (ignores magnitude)
  → Short reel (brief transcript) vs long reel (detailed transcript)
    are fairly compared — length doesn't distort results.

  Euclidean distance: measures absolute distance between endpoints
  → Sensitive to vector magnitude (short vs long text = very different
    distances even for same topic).

  Choice: COSINE ✓   (correct for OpenAI embeddings)
          EUCLIDEAN ✗ (penalises short transcripts unfairly)
```

---

### D5 — Named Docker volumes

```
  ┌─────────────────────────────────────────────────────────────┐
  │  Named volumes (chosen)      Bind mounts (rejected)         │
  │                                                             │
  │  redis_data:/data            /Users/work/.../redis_data     │
  │  qdrant_data:/qdrant/storage /Users/work/.../qdrant_data    │
  │  audio_tmp:/tmp/reels        /Users/work/.../audio_tmp      │
  │                                                             │
  │  ✓ Docker manages path       ✗ Path must exist on every     │
  │  ✓ Works any OS, any clone     machine, breaks on Windows   │
  │  ✓ docker compose down         paths                        │
  │    does NOT delete data                                     │
  │  ✓ docker compose down                                      │
  │    --volumes for clean wipe                                 │
  └─────────────────────────────────────────────────────────────┘
```

---

## 10. Failure & Recovery

```
  ┌────────────────────┬──────────────────────────┬──────────────────────────────┐
  │  Failure           │  Impact                  │  Recovery                    │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ agent crashes      │ Job lost (already popped │ Docker restarts agent.        │
  │ mid-job            │ from Redis)              │ Bot times out → tells user.  │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ Redis crashes      │ Queued jobs + in-flight  │ Named volume redis_data      │
  │                    │ results lost             │ recovers RDB snapshot.       │
  │                    │                          │ Docker restarts Redis.       │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ Qdrant crashes     │ Search fails; no new     │ Named volume qdrant_data     │
  │                    │ embeddings               │ preserves vectors.           │
  │                    │                          │ Docker restarts Qdrant.      │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ Whisper fails      │ Local transcription      │ API fallback kicks in.       │
  │ (SSL/download)     │ fails                    │ Transparent to agent.        │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ Notion API error   │ Note not saved           │ Tool returns "Error:..."     │
  │                    │                          │ Agent includes error in reply│
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ yt-dlp fails       │ No audio = no pipeline   │ Tool returns "Error:..."     │
  │ (private video)    │                          │ Agent tells user immediately │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ bot crashes        │ No new messages          │ Docker restarts bot.         │
  │                    │                          │ Redis retains queued jobs.   │
  ├────────────────────┼──────────────────────────┼──────────────────────────────┤
  │ Result timeout     │ User sees timeout msg    │ Agent still finishes.        │
  │ (5 min)            │                          │ Result auto-expires (10 min) │
  └────────────────────┴──────────────────────────┴──────────────────────────────┘

  Key invariant: bot and agent are fully independent — each can crash and restart
  without affecting the other. Only data in Redis is at risk during a Redis crash.
```
