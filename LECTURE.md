# Lecture: Building the Reel Knowledge Agent
### A Complete System Design & Engineering Walkthrough

---

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                          WHAT YOU WILL LEARN                               │
  │                                                                             │
  │  1. Why this system was designed the way it was                             │
  │  2. How four containers talk to each other                                  │
  │  3. How a Telegram message becomes a Notion note                            │
  │  4. What Redis, MCP, Qdrant, and Docker actually do here                    │
  │  5. How to think about every architectural decision made                    │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## LECTURE 1 — The Problem

### What pain are we solving?

Every day you watch YouTube Shorts and Instagram Reels. Some are educational — about AI,
business, health, finance. You learn something, you keep scrolling, and you forget it
within 24 hours.

There is no system that captures that knowledge automatically.

```
  THE LOOP MOST PEOPLE ARE IN:

  Watch reel ──► Learn something ──► Keep scrolling ──► Forget it
       ▲                                                      │
       └──────────────────────────────────────────────────────┘
                         infinite scroll, zero retention
```

### The solution we are building

You send a reel link to a Telegram bot. The bot:
1. Downloads the audio
2. Transcribes it into text
3. Uses AI to extract the key ideas
4. Saves a structured note to Notion
5. Stores the knowledge in a searchable vector database
6. Replies with a clean summary

```
  WHAT WE WANT:

  Watch reel ──► Send link to bot ──► Get structured note in Notion
                                             │
                                             ▼
                                    Searchable forever
                                    by meaning, not keyword
```

### The shift in thinking

This is not a chatbot. This is a **personal knowledge pipeline**.

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │   INPUT              PROCESS                   OUTPUT                   │
  │                                                                         │
  │  Reel URL    ──►   Download audio      ──►   Notion note               │
  │  (unstructured)    Transcribe text             (structured)             │
  │                    Extract concepts                                     │
  │                    Classify topic        ──►   Qdrant vector            │
  │                    Save + embed                (searchable)             │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## LECTURE 2 — The Architecture

### The big picture first

Before writing a single line of code, you think about what components you need
and how they communicate. This is called system design.

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                       FULL SYSTEM MAP                                    │
  │                                                                          │
  │   YOU                                                                    │
  │    │  send reel URL                                                      │
  │    ▼                                                                     │
  │  ┌──────────────┐          ┌─────────────────────────────────────────┐  │
  │  │   TELEGRAM   │          │            DOCKER NETWORK               │  │
  │  │   (cloud)    │◄────────►│                                         │  │
  │  └──────────────┘          │  ┌──────────┐        ┌──────────────┐  │  │
  │                            │  │  bot.py  │        │  agent.py    │  │  │
  │                            │  │          │◄──────►│              │  │  │
  │                            │  └──────────┘ Redis  └──────┬───────┘  │  │
  │                            │                             │           │  │
  │                            │                             │ MCP stdio  │  │
  │                            │                             ▼           │  │
  │                            │                      ┌──────────────┐  │  │
  │                            │                      │  server.py   │  │  │
  │                            │                      └──┬───────────┘  │  │
  │                            │                         │              │  │
  │                            │              ┌──────────┼──────────┐   │  │
  │                            │              ▼          ▼          ▼   │  │
  │                            │           Notion     OpenAI     Qdrant  │  │
  │                            └─────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────────────────┘
```

### Why four separate containers?

The first instinct is to put everything in one Python program. That is the wrong instinct.

```
  WRONG APPROACH — one big program:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │   main.py                                                               │
  │     receive Telegram message                                            │
  │     download audio                                                      │
  │     transcribe (takes 30–90 seconds)  ← Telegram freezes here          │
  │     classify with GPT-4o                                                │
  │     save to Notion                                                      │
  │     save to Qdrant                                                      │
  │     send reply                                                          │
  └─────────────────────────────────────────────────────────────────────────┘

  Problems:
  ✗ One crash kills everything — bot goes offline
  ✗ Bot can't receive new messages while processing old ones
  ✗ Can't scale — the AI work is slow, you'd need to duplicate the whole thing
  ✗ Tightly coupled — you can't update the AI logic without risking the bot
```

```
  RIGHT APPROACH — four containers:

  ┌──────────────┐   ┌───────────┐   ┌───────────────┐   ┌────────────┐
  │     bot      │   │   redis   │   │     agent     │   │   qdrant   │
  │              │   │           │   │               │   │            │
  │  receive msg │   │  job queue│   │  AI pipeline  │   │  vectors   │
  │  push to     │──►│           │──►│  slow work    │──►│            │
  │  Redis       │   │           │   │  here         │   │            │
  │  wait for    │◄──│           │◄──│  push result  │   │            │
  │  result      │   │           │   │               │   │            │
  └──────────────┘   └───────────┘   └───────────────┘   └────────────┘

  ✓ Bot crash doesn't stop agent from finishing jobs
  ✓ Bot stays responsive — accepts new messages while agent works
  ✓ Scale agent independently: --scale agent=3
  ✓ Update agent without touching the bot
```

### The principle behind this

**Separation of concerns.** Each container does exactly one thing.

```
  ┌────────────────┬──────────────────────────────────────────────────────┐
  │  Container     │  Does                    │  Does NOT do              │
  ├────────────────┼──────────────────────────┼───────────────────────────┤
  │  bot           │  Telegram I/O            │  AI, Notion, Qdrant       │
  │  redis         │  Queue jobs and results  │  Any business logic       │
  │  agent         │  Run the full pipeline   │  Telegram messages        │
  │  qdrant        │  Store/search vectors    │  Application code         │
  └────────────────┴──────────────────────────┴───────────────────────────┘
```

---

## LECTURE 3 — Docker and Docker Compose

### What is Docker?

A Docker container is a lightweight isolated environment. It is like a computer
inside your computer — it has its own filesystem, its own processes, its own
network interface.

```
  WITHOUT DOCKER:

  Your Mac
  ├── Python 3.11
  ├── ffmpeg 5.1
  ├── yt-dlp 2026.3
  ├── redis (running as a macOS service)
  └── qdrant (running as a macOS service)

  Problem: "Works on my machine" — setting this up on another machine is painful.
           Version conflicts. macOS vs Linux differences. Missing system libraries.

  WITH DOCKER:

  Your Mac
  └── Docker Desktop
        ├── container: redis      (exact version, isolated)
        ├── container: qdrant     (exact version, isolated)
        ├── container: bot        (Python 3.11 + ffmpeg + yt-dlp, isolated)
        └── container: agent      (same as bot, same image)

  Benefit: identical on any machine. One command starts everything.
```

### What is Docker Compose?

Docker Compose is a tool that defines and runs multi-container applications.
Instead of running four `docker run` commands manually, you describe everything
in one `docker-compose.yml` file.

```
  docker compose up --build

  reads docker-compose.yml
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  starts containers in dependency order:                      │
  │                                                              │
  │  1. redis starts    ──► passes healthcheck ──► READY         │
  │  2. qdrant starts   ──► passes healthcheck ──► READY         │
  │                              │                               │
  │                              │ both healthy                  │
  │                              ▼                               │
  │  3. bot starts      ──► connects to redis ──► polling        │
  │  4. agent starts    ──► connects to redis ──► waiting        │
  └──────────────────────────────────────────────────────────────┘
```

### The healthcheck

A healthcheck is a test that Docker runs every N seconds to decide if a container
is "healthy". Other containers with `depends_on: condition: service_healthy` will
not start until the check passes.

```
  redis healthcheck:
  ┌────────────────────────────────────────────────────┐
  │  test: redis-cli ping                              │
  │  expected response: PONG                           │
  │  run every: 5 seconds                              │
  │  fail after: 5 consecutive failures                │
  └────────────────────────────────────────────────────┘

  qdrant healthcheck:
  ┌────────────────────────────────────────────────────┐
  │  test: bash -c '</dev/tcp/localhost/6333'           │
  │  (open a TCP socket to port 6333)                  │
  │  if Qdrant is up, socket opens → exit 0 → healthy  │
  │  run every: 10 seconds                             │
  └────────────────────────────────────────────────────┘
```

Why not use `curl` for Qdrant? Because `curl` is not installed inside the Qdrant image.
The TCP socket check uses only bash — which is always available.

### Named volumes

Persistent storage for containers. When a container restarts, its filesystem resets.
Named volumes survive restarts.

```
  Without volumes:
  ┌──────────────────┐  restart  ┌──────────────────┐
  │   qdrant         │ ─────────► │   qdrant         │
  │   stored vectors │           │   EMPTY           │  ← all data gone
  └──────────────────┘           └──────────────────┘

  With named volumes:
  ┌──────────────────┐  restart  ┌──────────────────┐
  │   qdrant         │ ─────────► │   qdrant         │
  │   stored vectors │           │   stored vectors  │  ← data safe
  └────────┬─────────┘           └────────┬──────────┘
           │                              │
           └──────── qdrant_data ─────────┘
                     (Docker managed)
```

---

## LECTURE 4 — Redis: The Job Queue

### The problem Redis solves

bot.py and agent.py need to hand off work. bot.py gets the URL, agent.py processes it.
How do they pass data without being in the same process?

```
  OPTION 1: Direct function call (what we rejected)

  bot.py imports agent.py
  bot.py calls agent.process_url(url)
  bot.py blocks for 60-90 seconds
  bot.py gets the result

  Problem: bot is frozen. Can't receive another message.
           One crash brings both down.

  OPTION 2: Redis queue (what we built)

  bot.py pushes job to Redis   → bot is free immediately
  agent.py pops job from Redis → agent processes in background
  agent.py pushes result       → bot wakes up and reads it
```

### How Redis lists work

Redis is an in-memory data store. We use its List data type as a queue.

```
  LIST OPERATIONS:

  RPUSH key value    →  adds value to the RIGHT end (tail) of the list
  BLPOP key timeout  →  removes value from the LEFT end (head), blocks if empty

  This gives FIFO (First In, First Out) — first job in is first job processed.

  ┌─────────────────────────────────────────────────────────────┐
  │  jobs:pending                                               │
  │                                                             │
  │  RPUSH ─────────────────────────────────────────► RPUSH     │
  │  (jobs added here, right side)                              │
  │                                                             │
  │  HEAD                                              TAIL      │
  │  [ job_A ] [ job_B ] [ job_C ] [ job_D ]                   │
  │      ▲                                                      │
  │  BLPOP pops here (left side)                                │
  └─────────────────────────────────────────────────────────────┘

  Job A was pushed first → processed first.
  This is fair ordering — users don't jump the queue.
```

### The BLPOP behaviour

BLPOP is special. It is a **blocking** pop. If the list is empty, it waits.

```
  agent.py starts up:

  await redis.blpop("jobs:pending", timeout=0)
                                    ↑
                              0 means: wait forever

  ┌───────────────────────────────────────────────────────┐
  │  TIME                                                 │
  │  ──►                                                  │
  │                                                       │
  │  T=0    agent starts    BLPOP called   agent blocks   │
  │                                           │           │
  │                                           │ waiting   │
  │                                           │           │
  │  T=30   user sends link  bot does RPUSH   │           │
  │                                           │ wakes up  │
  │                                           ▼           │
  │  T=30   agent gets job   starts processing            │
  └───────────────────────────────────────────────────────┘

  No polling loop. No CPU wasted. Agent sleeps until work arrives.
```

### The full Redis data flow

```
  bot.py                      Redis                    agent.py
     │                          │                          │
     │  job = {                 │                          │  BLPOP jobs:pending
     │    job_id: "abc",        │                          │  (blocking, waiting...)
     │    url: "https://..."    │                          │
     │  }                       │                          │
     │  RPUSH jobs:pending ────►│                          │
     │                          │──── job delivered ──────►│
     │                          │                          │
     │  BLPOP result:abc        │                          │  process_url(url)
     │  (blocking, 5 min max)   │                          │  ... 60-90 seconds ...
     │                          │                          │
     │                          │◄──── RPUSH result:abc ───│
     │                          │      {"text": "..."}     │
     │◄─── result delivered ────│                          │
     │                          │                          │  EXPIRE result:abc 600
     │  send to Telegram        │                          │
```

### Why not Pub/Sub?

Redis also has a Publish/Subscribe system. We deliberately chose NOT to use it.

```
  PUB/SUB:
  publisher sends message ──► subscribers receive it IF they are connected
                               ▲
                               └── if agent was restarting when message arrived?
                                   MESSAGE IS LOST

  RPUSH + BLPOP:
  bot RPUSH ──► message stays in the list until consumed
                ▲
                └── agent restarts? job is still in the list. Nothing lost.

  Rule: for critical work handoff, always use persistent queues, not Pub/Sub.
```

---

## LECTURE 5 — MCP: The Tool Protocol

### What is MCP?

MCP stands for Model Context Protocol. It is a standard way for an AI agent to
call tools defined in a separate server. Think of it as a contract between
the AI brain (agent.py) and the tools (server.py).

```
  WITHOUT MCP:
  ┌──────────────────────────────────────────────────────────────┐
  │  agent.py                                                    │
  │    from server import download_reel, transcribe_audio        │
  │    from server import save_to_notion, embed_and_store        │
  │                                                              │
  │  If any tool has a bug that crashes Python, agent.py dies.   │
  │  If you change server.py, you restart the entire agent.      │
  └──────────────────────────────────────────────────────────────┘

  WITH MCP:
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  agent.py (parent process)     server.py (child process)    │
  │                          stdio                               │
  │  ClientSession     ◄──────────────────────►  FastMCP        │
  │  (sends tool calls)           pipes          (handles them)  │
  │                                                              │
  │  If server.py crashes: agent catches the error.              │
  │  If you change server.py: just restart the MCP process.      │
  └──────────────────────────────────────────────────────────────┘
```

### How agent.py starts the MCP server

```
  agent.py                                   server.py
     │                                            │
     │  StdioServerParameters(                    │
     │    command="python",                       │
     │    args=["server.py"]                      │
     │  )                                         │
     │                                            │
     │  async with stdio_client(...):             │
     │  ── spawns server.py as subprocess ───────►│
     │                                            │  FastMCP starts
     │  session.initialize()                      │  registers all tools
     │  ◄─── handshake complete ─────────────────│
     │                                            │
     │  tools = session.list_tools()             │
     │  ◄─── [{name, description, schema}, ...] ─│
     │                                            │
     │  (converts to OpenAI format)               │
     │  openai_tools = _mcp_tools_to_openai(tools)│
     │                                            │
     │  (starts GPT-4o loop with these tools)     │
```

### How a tool call happens

```
  agent.py (agentic loop)             OpenAI          server.py (MCP)
       │                                │                   │
       │─── messages + tools ──────────►│                   │
       │                                │                   │
       │◄── tool_call:                  │                   │
       │    name="download_reel"        │                   │
       │    args={"url": "https://..."}│                   │
       │                                │                   │
       │─── session.call_tool(name, args) ────────────────►│
       │                                │                   │  runs download_reel()
       │                                │                   │  yt-dlp downloads audio
       │◄── result.content[0].text ─────────────────────── │
       │    "/tmp/reels/audio.mp3"      │                   │
       │                                │                   │
       │  append result to messages     │                   │
       │─── messages + tools ──────────►│                   │
       │    (GPT-4o sees the result     │                   │
       │     and decides next step)     │                   │
```

### The 6 tools in server.py

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  TOOL                     INPUT              OUTPUT                     │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  download_reel            url                /tmp/reels/audio.mp3       │
  │  transcribe_audio         file_path          full transcript text       │
  │  get_existing_topics      (none)             "Topic / Subtopic\n..."    │
  │  save_to_notion           topic,subtopic,    notion page URL            │
  │                           content                                       │
  │  embed_and_store          text, topic,       UUID of stored point       │
  │                           subtopic, url,                                │
  │                           summary                                       │
  │  get_similar_reels        query, limit       formatted search results   │
  └─────────────────────────────────────────────────────────────────────────┘

  Rule: every tool returns a string. Errors are returned as "Error: ..."
        Nothing ever raises an exception to the MCP layer.
        The agent handles error strings gracefully.
```

---

## LECTURE 6 — The OpenAI Agentic Loop

### What is an agentic loop?

Traditional AI: you send a prompt, you get a response. Done.

Agentic AI: you send a prompt, the AI decides what actions to take,
takes them, sees results, decides again — until the task is complete.

```
  TRADITIONAL LLM CALL:

  User prompt ──► GPT-4o ──► Answer
  (one round trip)

  AGENTIC LOOP:

  System + URL ──► GPT-4o ──► "I'll call download_reel"
                      ▲            │
                      │            ▼
                      │       tool executes
                      │            │
                      │            ▼
                  GPT-4o ◄─── tool result
                      │
                      ▼
                  "Now I'll call transcribe_audio"
                      │
                     ...repeats until task is complete...
                      │
                      ▼
                  Final answer (no more tool calls)
```

### The loop in detail

```
  ╔═══════════════════════════════════════════════════════════════════╗
  ║  messages = [system_prompt, user_url]                             ║
  ║                                                                   ║
  ║  LOOP:                                                            ║
  ║                                                                   ║
  ║    response = GPT-4o(messages, tools=openai_tools)                ║
  ║    msg = response.choices[0].message                              ║
  ║                                                                   ║
  ║    ┌──────────────────────────────────────────────────────────┐  ║
  ║    │  Does msg have tool_calls?                               │  ║
  ║    │                                                          │  ║
  ║    │  YES                          NO (text response)         │  ║
  ║    │   │                            │                         │  ║
  ║    │   ▼                            ▼                         │  ║
  ║    │  for each tool_call:    Was save_to_notion called?       │  ║
  ║    │    call the tool        Was embed_and_store called?      │  ║
  ║    │    get result           │                                │  ║
  ║    │    append to messages   │  NO → nudge the model          │  ║
  ║    │    loop again           │      append reminder message   │  ║
  ║    │                         │      loop again                │  ║
  ║    │                         │                                │  ║
  ║    │                         │  YES → return final text       │  ║
  ║    └──────────────────────────────────────────────────────────┘  ║
  ╚═══════════════════════════════════════════════════════════════════╝
```

### Why the enforcement checks?

GPT-4o is instructed to follow 7 steps. But LLMs can skip steps.
We add hard enforcement for the two most critical ones.

```
  HARD enforcement — save_to_notion:
  If GPT-4o tries to give a final answer WITHOUT calling save_to_notion first:

  agent.py intercepts it and appends:
  "You must call save_to_notion before finishing."

  GPT-4o receives this as a user message, understands it missed a step,
  and calls the tool.

  SOFT enforcement — embed_and_store:
  If GPT-4o gives a final answer without embed_and_store:

  agent.py appends:
  "You still need to call embed_and_store to save to the vector database."

  Why soft? Because a Notion note with no vector is still useful.
  A job with no Notion note is a complete failure.
```

### Why GPT-4o for this task?

```
  What we need from the model:

  1. Read a transcript (may be 500–3000 words)
  2. Understand the topic and domain
  3. Extract the key concepts (not just keywords — concepts)
  4. Classify into the right topic/subtopic
  5. Reuse existing topics (read from get_existing_topics)
  6. Orchestrate all 6 tool calls in the right order

  This requires:
  ✓ Long context window     (long transcripts)
  ✓ Strong reasoning        (concept extraction, not just summarisation)
  ✓ Tool calling            (structured function invocation)
  ✓ Instruction following   (7-step pipeline, must not skip steps)

  GPT-4o satisfies all four. Smaller models skip steps or extract poor concepts.
```

---

## LECTURE 7 — Whisper: Transcription

### Local vs API transcription

```
  TWO PATHS:

  ┌────────────────────────────────────────────────────────────────┐
  │  PATH 1 — Local Whisper (preferred)                            │
  │                                                                │
  │  whisper.load_model("base")                                    │
  │  model.transcribe(audio_file)                                  │
  │                                                                │
  │  Cost:    FREE                                                 │
  │  Speed:   ~30–60s for a 60s reel on CPU                       │
  │  Privacy: audio never leaves your machine                      │
  │  Model:   ~140MB, downloaded once and cached                   │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │  PATH 2 — OpenAI API (fallback)                                │
  │                                                                │
  │  openai.audio.transcriptions.create(                           │
  │      model="gpt-4o-mini-transcribe",                           │
  │      file=audio_file                                           │
  │  )                                                             │
  │                                                                │
  │  Cost:    ~$0.006 per minute of audio                          │
  │  Speed:   ~3–5 seconds                                         │
  │  Privacy: audio sent to OpenAI servers                         │
  │  When:    local Whisper fails (SSL cert error, cache issue)    │
  └────────────────────────────────────────────────────────────────┘
```

### The try/except/finally pattern

```
  transcribe_audio(file_path):

  try:
      ─── try the fast free path ─────────────────────────────────
      model = whisper.load_model("base")
      result = model.transcribe(file_path)
      return result["text"]
      ────────────────────────────────────────────────────────────

  except Exception:
      ─── fallback to the API ────────────────────────────────────
      with open(file_path, "rb") as f:
          response = openai.audio.transcriptions.create(...)
      return response.text
      ────────────────────────────────────────────────────────────

  finally:
      ─── ALWAYS runs, regardless of success or failure ──────────
      if os.path.exists(file_path):
          os.remove(file_path)   ← delete temp audio file
      ────────────────────────────────────────────────────────────

  Why finally?
  Without it: if transcription fails, the audio file stays on disk forever.
  /tmp/reels is a shared Docker volume. Stale files accumulate and waste disk.
  finally guarantees cleanup no matter what happens.
```

---

## LECTURE 8 — Notion: Structured Storage

### Why Notion?

Notion is the output layer — where structured knowledge lives permanently.

```
  Alternative options considered:

  ┌────────────────┬──────────────────────────────────────────┐
  │  Option        │  Why not used                            │
  ├────────────────┼──────────────────────────────────────────┤
  │  Google Docs   │  No database features; no structured     │
  │                │  properties (Topic, Subtopic)            │
  ├────────────────┼──────────────────────────────────────────┤
  │  SQLite        │  Not human-friendly; no nice interface    │
  ├────────────────┼──────────────────────────────────────────┤
  │  Markdown file │  No search; not organised; no properties │
  ├────────────────┼──────────────────────────────────────────┤
  │  Notion        │  ✓ Database with properties              │
  │                │  ✓ Human-readable and editable           │
  │                │  ✓ API to write from code                │
  │                │  ✓ Already where knowledge workers live  │
  └────────────────┴──────────────────────────────────────────┘
```

### The page structure

```
  NOTION PAGE CREATED FOR EACH REEL:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Name:      Technology — AI & Machine Learning                  │  ← title property
  │  Topic:     Technology                                          │  ← rich_text property
  │  Subtopic:  AI & Machine Learning                               │  ← rich_text property
  │                                                                 │
  │  Body:                                                          │
  │    • Transformers use attention to weight important words        │
  │    • Pre-training on large corpora enables transfer learning     │
  │    • Fine-tuning adapts a base model to specific tasks          │
  │    • RLHF aligns model outputs with human preferences           │
  └─────────────────────────────────────────────────────────────────┘

  The Name is constructed from topic + subtopic.
  The body is the bullet-point summary that GPT-4o generates.
```

### Topic reuse — why it matters

```
  WHAT HAPPENS WITHOUT REUSE:

  Reel 1: topic="AI"                  ─┐
  Reel 2: topic="Artificial Intel."   ─┤  These are all the same thing.
  Reel 3: topic="A.I."               ─┘  Notion treats them as different.

  Your database becomes a mess. Filtering by topic is useless.

  WHAT WE DO:

  Before classification:
  agent calls get_existing_topics() → returns ["Technology / AI & Machine Learning", ...]

  GPT-4o instruction:
  "Reuse an existing topic/subtopic when it fits. Match exactly — Notion is case-sensitive."

  Result: every reel about AI gets "Technology / AI & Machine Learning" — consistent, clean.
```

---

## LECTURE 9 — Qdrant: Semantic Search

### What is a vector database?

A regular database stores text and searches by exact match or keyword.
A vector database stores numbers (vectors) that represent meaning.

```
  KEYWORD SEARCH (what regular databases do):

  Query: "habit formation"
  Search: find documents containing the word "habit" or "formation"

  Miss: document about "building routines for behaviour change"
        ← has the same meaning but different words

  SEMANTIC SEARCH (what Qdrant does):

  Query: "habit formation"
  Convert to vector: [0.021, -0.043, 0.009, ..., 0.017]  (1536 numbers)

  Compare: measure how similar this vector is to every stored vector
  Find: documents whose vectors point in a similar direction

  Hit: "building routines for behaviour change"
       ← same meaning = similar vector = found
```

### How text becomes a vector

OpenAI's text-embedding-3-small model converts any text into 1536 numbers.
Similar texts produce similar number patterns.

```
  TEXT                           VECTOR (simplified to 3 dimensions for illustration)

  "habit formation"         →    [0.8,  0.2,  0.1]
  "building routines"       →    [0.7,  0.3,  0.1]   ← similar direction
  "quantum entanglement"    →    [0.1, -0.9,  0.5]   ← very different direction
  "behaviour change"        →    [0.75, 0.25, 0.15]  ← similar direction

  In 1536 dimensions, this comparison is extremely precise.
  Same concept = vectors point in the same direction.
```

### Cosine similarity: how we measure "similar"

```
  COSINE SIMILARITY measures the angle between two vectors.

  Same direction   →  angle = 0°   →  similarity = 1.0  (identical)
  90 degrees apart →  angle = 90°  →  similarity = 0.0  (unrelated)
  Opposite         →  angle = 180° →  similarity = -1.0 (opposite meaning)

  ┌───────────────────────────────────────────────────────────────┐
  │  Score    Meaning                                             │
  ├───────────────────────────────────────────────────────────────┤
  │  0.90 – 1.00   Near-identical topic and intent               │
  │  0.75 – 0.89   Clearly related, same domain                  │
  │  0.60 – 0.74   Related but broader topic                     │
  │  below 0.60    Weak or incidental match                       │
  └───────────────────────────────────────────────────────────────┘

  WHY COSINE and not Euclidean distance?

  A 30-second reel has a short transcript → small vector magnitude
  A 5-minute reel has a long transcript  → large vector magnitude

  Euclidean distance is affected by magnitude.
  A short transcript on AI and a long transcript on AI might appear far apart.

  Cosine only measures direction, not magnitude.
  Both transcripts about AI point in the same direction → correctly identified as similar.
```

### The Qdrant data flow

```
  INGEST (storing a reel):

  transcript text
       │
       ▼
  embed_text(text)
  openai.embeddings.create(model="text-embedding-3-small", input=text)
       │
       ▼
  [0.021, -0.043, ..., 0.017]   ← 1536 floats
       │
       ▼
  qdrant.upsert(
    collection="reels",
    point_id = uuid4(),
    vector   = [1536 floats],
    payload  = {text, topic, subtopic, source_url, summary}
  )

  ─────────────────────────────────────────────────────────────────

  RETRIEVAL (searching):

  query: "What did I learn about attention mechanisms?"
       │
       ▼
  embed_text(query)  → query vector [1536 floats]
       │
       ▼
  qdrant.query_points(
    collection="reels",
    query=query_vector,
    limit=5
  )
       │
       ▼
  top-5 points sorted by cosine similarity
  → each has: score, text, topic, subtopic, source_url, summary
       │
       ▼
  GPT-4o synthesises answer from these 5 context chunks
```

---

## LECTURE 10 — The Full Pipeline, End to End

### Every step, no abstraction

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  YOU                                                                     │
  │  Open Telegram. Find your bot. Send:                                     │
  │  https://www.youtube.com/shorts/abc123                                   │
  └──────────────────────────────────┬───────────────────────────────────────┘
                                     │ Telegram delivers message to bot.py
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  bot.py — handle_message()                                               │
  │                                                                          │
  │  1. Extract text from update.message.text                                │
  │  2. Run regex: does it look like a YouTube or Instagram URL?             │
  │     → No match: reply "Please send a valid reel link." STOP             │
  │     → Match: proceed                                                     │
  │  3. url = "https://www.youtube.com/shorts/abc123"                        │
  │  4. job_id = str(uuid4())  → e.g. "f47ac10b-..."                        │
  │  5. payload = {"job_id": "f47ac10b-...", "url": "https://..."}           │
  │  6. RPUSH jobs:pending payload  ──────────────────────────────► Redis    │
  │  7. reply "Got it! Processing your reel..."                              │
  │  8. BLPOP result:f47ac10b  timeout=300  ← wait for agent (max 5 min)   │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │ Redis delivers job to agent
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  agent.py — worker() loop                                                │
  │                                                                          │
  │  BLPOP wakes up: job_id="f47ac10b", url="https://..."                   │
  │  calls process_url(url)                                                  │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  agent.py — process_url()                                                │
  │                                                                          │
  │  Starts server.py as MCP subprocess                                      │
  │  Gets 6 tool schemas from server.py                                      │
  │  Converts schemas to OpenAI format                                       │
  │  Builds initial messages: [system_prompt, url]                           │
  │  Enters agentic loop                                                     │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │ GPT-4o reads system prompt + URL
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — TURN 1                                                   │
  │                                                                          │
  │  GPT-4o: "Step 1 says download_reel. I'll call it."                     │
  │  tool_call: download_reel(url="https://youtube.com/shorts/abc123")       │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  server.py — download_reel()                                             │
  │                                                                          │
  │  subprocess: yt-dlp -x --audio-format mp3                                │
  │              → downloads audio stream from YouTube                       │
  │              → converts to MP3 using ffmpeg                              │
  │              → saves to /tmp/reels/audio.mp3                             │
  │  returns: "/tmp/reels/audio.mp3"                                         │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │ result appended to messages
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — TURN 2                                                   │
  │                                                                          │
  │  GPT-4o sees: download succeeded, path=/tmp/reels/audio.mp3             │
  │  GPT-4o: "Step 2 says transcribe_audio. I'll call it."                  │
  │  tool_call: transcribe_audio(file_path="/tmp/reels/audio.mp3")           │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  server.py — transcribe_audio()                                          │
  │                                                                          │
  │  try: whisper.load_model("base").transcribe(audio_file)                  │
  │  → "Attention mechanisms allow transformers to weigh..."                  │
  │  finally: os.remove("/tmp/reels/audio.mp3")                              │
  │  returns: full transcript text                                           │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — TURN 3                                                   │
  │                                                                          │
  │  GPT-4o: "Step 3: get existing topics."                                  │
  │  tool_call: get_existing_topics()                                        │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  server.py — get_existing_topics()                                       │
  │                                                                          │
  │  POST Notion API /databases/{id}/query                                   │
  │  reads every page's Topic and Subtopic properties                        │
  │  returns: "Technology / AI & Machine Learning\nBusiness / Investing\n..."│
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — TURN 4 (reasoning, no tool call)                         │
  │                                                                          │
  │  GPT-4o reads transcript + existing topics                               │
  │  "This is about transformers and attention → Technology / AI & ML"       │
  │  "That topic already exists in Notion → I'll reuse it exactly"           │
  │  "Key concepts: attention, pre-training, fine-tuning, RLHF..."           │
  │                                                                          │
  │  GPT-4o: "Step 5: save_to_notion."                                       │
  │  tool_call: save_to_notion(                                              │
  │    topic="Technology",                                                   │
  │    subtopic="AI & Machine Learning",                                     │
  │    content="• Attention mechanisms weigh tokens by relevance\n..."       │
  │  )                                                                       │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  server.py — save_to_notion()                                            │
  │                                                                          │
  │  POST Notion API /pages                                                  │
  │  creates page: Name="Technology — AI & Machine Learning"                 │
  │                Topic="Technology", Subtopic="AI & Machine Learning"      │
  │                body = bullet-point summary                               │
  │  returns: "https://notion.so/page/..."                                   │
  │                                                                          │
  │  ← agent marks notion_saved = True                                       │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — TURN 5                                                   │
  │                                                                          │
  │  GPT-4o: "Step 6: embed_and_store."                                      │
  │  tool_call: embed_and_store(                                             │
  │    text=<full transcript>,                                               │
  │    topic="Technology",                                                   │
  │    subtopic="AI & Machine Learning",                                     │
  │    source_url="https://youtube.com/shorts/abc123",                       │
  │    summary="• Attention mechanisms...\n..."                              │
  │  )                                                                       │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  server.py → qdrant_helper.py — embed_and_store()                        │
  │                                                                          │
  │  embed_text(transcript) → 1536-dim vector via text-embedding-3-small     │
  │  qdrant.upsert(                                                          │
  │    id=uuid4(), vector=[...], payload={text, topic, subtopic, url, summary}
  │  )                                                                       │
  │  returns: "f47ac10b-..."  (UUID of stored point)                         │
  │                                                                          │
  │  ← agent marks embedded_in_qdrant = True                                 │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  AGENTIC LOOP — FINAL TURN                                               │
  │                                                                          │
  │  GPT-4o: notion_saved=True, embedded=True, all steps done                │
  │  Produces final text response (no tool_calls):                           │
  │                                                                          │
  │  "Topic: Technology / AI & Machine Learning                              │
  │                                                                          │
  │   Key concepts:                                                          │
  │   • Transformers use attention to weigh token importance                 │
  │   • Pre-training on large corpora enables transfer learning              │
  │   • Fine-tuning adapts a base model to specific downstream tasks         │
  │   • RLHF aligns model outputs with human preference"                    │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  agent.py — worker()                                                     │
  │                                                                          │
  │  RPUSH result:f47ac10b  {"text": "Topic: Technology / AI...\n..."}      │
  │  EXPIRE result:f47ac10b 600                                              │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │ Redis delivers result to bot
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  bot.py — handle_message() (was blocked on BLPOP)                        │
  │                                                                          │
  │  BLPOP wakes up: data["text"] = "Topic: Technology / AI...\n..."         │
  │  await update.message.reply_text(data["text"])                           │
  └──────────────────────────────────────────────────────────────────────────┘
                                     │ Telegram delivers message
                                     ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  YOU                                                                     │
  │  Receive in Telegram:                                                    │
  │                                                                          │
  │  Topic: Technology / AI & Machine Learning                               │
  │                                                                          │
  │  Key concepts:                                                           │
  │  • Transformers use attention to weigh token importance                  │
  │  • Pre-training on large corpora enables transfer learning               │
  │  • Fine-tuning adapts a base model to specific downstream tasks          │
  │  • RLHF aligns model outputs with human preference                       │
  │                                                                          │
  │  A new page also appears in your Notion database.                        │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## LECTURE 11 — Key Design Decisions Explained

### Why each decision was made

```
  DECISION 1: Redis queue between bot and agent
  ─────────────────────────────────────────────
  Alternative: direct Python import
  Why rejected: shared process = shared crash, bot freezes while agent works
  Why chosen: RPUSH/BLPOP is persistent, decoupled, horizontally scalable

  DECISION 2: MCP for tool execution
  ───────────────────────────────────
  Alternative: agent.py imports tools directly from server.py
  Why rejected: tool bug crashes the agent; tight coupling
  Why chosen: subprocess boundary isolates failures; standard JSON tool schema

  DECISION 3: Local Whisper + API fallback
  ─────────────────────────────────────────
  Alternative: always use OpenAI API
  Why rejected: costs money; audio goes to OpenAI servers; depends on internet
  Why chosen: local is free and private; API fallback handles edge cases

  DECISION 4: Cosine distance in Qdrant
  ──────────────────────────────────────
  Alternative: Euclidean distance
  Why rejected: penalises short transcripts; magnitude-sensitive
  Why chosen: text-embedding-3-small is optimised for cosine; magnitude-insensitive

  DECISION 5: Named Docker volumes
  ─────────────────────────────────
  Alternative: bind mounts (host directory paths)
  Why rejected: path must exist on every machine; breaks on Windows
  Why chosen: Docker manages lifecycle; portable; survives plain docker compose down

  DECISION 6: Secrets in .env, not in image
  ──────────────────────────────────────────
  Alternative: hardcode in Dockerfile or code
  Why rejected: image layers are permanent; secrets would leak via docker history
  Why chosen: .env is in .dockerignore; never enters the image; safe to share image
```

---

## LECTURE 12 — Error Handling Philosophy

### The rule: tools never crash the agent

Every tool in server.py follows one rule: catch every exception, return it as a string.

```
  WRONG pattern:

  def download_reel(url):
      result = subprocess.run(["yt-dlp", ...], check=True)
      return result.stdout          ← if yt-dlp fails, raises CalledProcessError
                                      this crashes the MCP layer
                                      agent.py loses the whole job

  RIGHT pattern:

  def download_reel(url):
      try:
          result = subprocess.run(["yt-dlp", ...], check=True)
          return result.stdout
      except FileNotFoundError:
          return "Error: yt-dlp not found. Is it installed?"
      except subprocess.CalledProcessError as e:
          return f"Error downloading: {e.stderr}"
```

### What the agent does with errors

```
  Tool returns "Error: yt-dlp not found"
       │
       ▼
  GPT-4o sees the error string in its context
       │
       ▼
  GPT-4o decides: "I cannot continue without the audio. I'll tell the user."
       │
       ▼
  Final response: "Failed to download the reel: yt-dlp is not installed.
                   Please check the Docker container has yt-dlp."
       │
       ▼
  agent.py pushes this error text to Redis
       │
       ▼
  bot.py sends it to the Telegram user

  Result: user sees a useful error message. Nothing crashes. Pipeline is clean.
```

### Outer safety net

agent.py's worker loop has its own try/except wrapping process_url():

```
  try:
      result_text = await process_url(url)
  except Exception as e:
      result_text = f"Error processing reel: {e}"

  await redis.rpush(f"result:{job_id}", json.dumps({"text": result_text}))
```

Even if an unhandled exception escapes every inner try/except, the worker catches it,
formats it as a user-readable error, and pushes it to Redis.

The bot **always** gets a response. It never hangs indefinitely.

---

## SUMMARY — The Mental Model

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │  LAYER           TECHNOLOGY        RESPONSIBILITY                       │
  │  ─────────────────────────────────────────────────────────────────────  │
  │  Interface       Telegram          Receive URLs, send summaries         │
  │  Queue           Redis             Decouple bot from agent, job buffer  │
  │  Intelligence    OpenAI GPT-4o     Reason, decide, orchestrate tools    │
  │  Download        yt-dlp + ffmpeg   Pull audio from YouTube/Instagram    │
  │  Transcription   Whisper + API     Convert audio to text                │
  │  Classification  GPT-4o + topics   Assign topic, extract key concepts   │
  │  Storage         Notion API        Write structured notes               │
  │  Vectors         Qdrant            Store and search by meaning          │
  │  Runtime         Docker Compose    Isolate, connect, persist everything  │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘

  THE DATA JOURNEY:

  URL string
    → audio file (/tmp/reels/audio.mp3)
    → transcript text (1000 words)
    → structured note (topic + subtopic + 5 concepts)
    → Notion page (human-readable, permanent)
    → 1536 numbers (machine-searchable, semantic)
    → Telegram message (instant summary back to you)

  WHAT MAKES THIS SYSTEM GOOD:

  1. Decoupled  — each component fails independently, does not take others down
  2. Persistent — Redis volumes, Qdrant volumes; nothing lost on container restart
  3. Fallbacks  — Whisper fails → API; tool errors → agent handles gracefully
  4. Enforced   — agent cannot skip save_to_notion; embed_and_store is nudged
  5. Scalable   — --scale agent=3 processes 3 reels in parallel
  6. Secure     — no secrets in Docker images; all from .env at runtime
```

---

## FURTHER READING

| Topic | File |
|---|---|
| Architecture overview | `docs/HLD.md` |
| Component-level design | `docs/LLD.md` |
| Redis queue deep dive | `docs/REDIS_ARCHITECTURE.md` |
| Product requirements | `docs/PRD.md` |
| Topic classification rules | `docs/topic-map.md` |
| Step-by-step setup | `QUICKSTART.md` |
| Beginner walkthrough | `GUIDE.md` |
