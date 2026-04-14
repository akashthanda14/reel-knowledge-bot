# Low Level Design
## Reel Knowledge Agent

---

## 1. Module Map

```
  reel-knowledge-agent/
  │
  ├── bot.py
  │     Telegram interface
  │     Validates URLs, enqueues jobs to Redis (RPUSH),
  │     waits for results (BLPOP), sends Telegram reply.
  │
  ├── agent.py
  │     Redis worker + OpenAI agentic loop
  │     Pops jobs (BLPOP), starts server.py as MCP stdio subprocess,
  │     runs GPT-4o tool-calling loop, pushes results to Redis (RPUSH).
  │
  ├── server.py
  │     MCP tool server (FastMCP)
  │     6 tools: download_reel, transcribe_audio, get_existing_topics,
  │     save_to_notion, embed_and_store, get_similar_reels.
  │     All tools return strings — never raise exceptions to the MCP layer.
  │
  ├── qdrant_helper.py
  │     Qdrant vector DB interface
  │     embed_text(), store_reel(), search_reels().
  │     Initialises "reels" collection on import.
  │
  ├── setup_notion.py
  │     One-time Notion schema setup script.
  │     Adds Topic + Subtopic properties to the Notion database.
  │     Run once before docker compose up.
  │
  └── docs/topic-map.md
        Topic taxonomy (8 top-level topics, ~40 subtopics)
        Read by GPT-4o via system prompt context during classification.
```

---

## 2. bot.py

### Constants

```python
JOB_QUEUE      = "jobs:pending"      # Redis list — agent reads from here
RESULT_TIMEOUT = 300                 # seconds bot waits for agent (5 min)
URL_RE         = re.compile(
    r"https?://(www\.)?(youtube\.com|youtu\.be|instagram\.com)/\S+"
)
```

### Environment Variables

| Variable | Required | Default | Used In |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | ApplicationBuilder |
| `REDIS_URL` | No | `redis://redis:6379` | aioredis.from_url() |

---

### handle_message() — Decision Flow

```
  Telegram update arrives
          │
          ▼
  ┌───────────────────────────────────┐
  │  extract text from update.message │
  └───────────────────┬───────────────┘
                      │
                      ▼
            URL_RE.search(text)?
                      │
            ┌─────────┴──────────┐
           YES                   NO
            │                    │
            │                    ▼
            │          reply: "Please send a valid
            │                  YouTube or Instagram
            │                  reel link."
            │                  RETURN
            │
            ▼
  ┌──────────────────────────────────────────────────┐
  │  url     = match.group(0)                        │
  │  job_id  = str(uuid.uuid4())                     │
  │  payload = json.dumps({"job_id": ..., "url": ...})│
  └──────────────────────┬───────────────────────────┘
                         │
                         ▼
         RPUSH  jobs:pending  payload
                         │
                         ▼
  reply: "Got it! Processing your reel..."
                         │
                         ▼
         BLPOP  result:{job_id}  timeout=300
                         │
              ┌──────────┴──────────┐
           response                None
           received               (timeout)
              │                    │
              │                    ▼
              │          reply: "Processing timed out..."
              │                  RETURN
              │
              ▼
  data = json.loads(response[1])
  reply: data["text"]   ──────────────────────────► Telegram user
```

---

### Lifecycle Functions

#### `post_init(application)`
Called once after app is built, before polling starts.
```
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
application.bot_data["redis"] = redis_client
```
One shared Redis connection stored in bot_data — all handlers reuse it.

#### `post_shutdown(application)`
Called once on Ctrl+C / SIGTERM.
```
await application.bot_data["redis"].aclose()
```
Prevents resource leak warnings on graceful shutdown.

#### `main()`
```
ApplicationBuilder()
  .token(TELEGRAM_BOT_TOKEN)
  .post_init(post_init)
  .post_shutdown(post_shutdown)
  .build()
add_handler: MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
run_polling()
```

---

## 3. agent.py

### Constants

```python
MODEL      = "gpt-4o"       # OpenAI model for reasoning + tool orchestration
JOB_QUEUE  = "jobs:pending" # Must match bot.py — shared Redis key name
RESULT_TTL = 600            # seconds before orphaned result auto-deletes (10 min)
```

### Environment Variables

| Variable | Required | Default | Used In |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI() client |
| `REDIS_URL` | No | `redis://redis:6379` | aioredis.from_url() |

---

### System Prompt (full text)

```
You are a knowledge extraction agent.
Given a reel URL you must follow these steps in order:

1. Call download_reel to download the audio.
2. Call transcribe_audio with the returned file path.
3. Call get_existing_topics to see what topics already exist in Notion.
4. Analyse the transcript: extract 3–7 key concepts, determine the best topic
   and subtopic (reuse an existing topic/subtopic when it fits, otherwise
   create a new one).
5. Call save_to_notion with topic, subtopic, and a clean structured summary
   of the key concepts.
6. Call embed_and_store with:
   - text: the full transcript
   - topic: same topic you used in save_to_notion
   - subtopic: same subtopic
   - source_url: the original reel URL the user sent
   - summary: the same bullet-point summary you saved to Notion
   This stores the knowledge in the vector search database for future retrieval.
7. Reply with a short confirmation: topic, subtopic, and bullet-point key concepts.

Format the content you pass to save_to_notion as plain text bullet points.
```

---

### process_url() — Full Agentic Loop

```
  process_url(url) called
        │
        ▼
  StdioServerParameters(command="python", args=["server.py"])
  async with stdio_client → (read, write)
  async with ClientSession → session
        │
        ▼
  session.initialize()
  tools   = session.list_tools()
  openai_tools = _mcp_tools_to_openai(tools)   # convert MCP → OpenAI format
        │
        ▼
  messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user",   "content": url}
  ]
  notion_saved    = False
  embedded_in_qdrant = False
        │
        ▼
  ╔═══════════════════════════════════════════════════════════════╗
  ║  AGENTIC LOOP                                                 ║
  ║                                                               ║
  ║  response = client.chat.completions.create(                   ║
  ║      model=MODEL,                                             ║
  ║      tools=openai_tools,                                      ║
  ║      tool_choice="auto",                                      ║
  ║      messages=messages                                        ║
  ║  )                                                            ║
  ║  msg = response.choices[0].message                            ║
  ║                                                               ║
  ║  msg.tool_calls is None?                                      ║
  ║      │                                                        ║
  ║  ┌───┴────────────────────┐                                   ║
  ║  YES                      NO                                  ║
  ║  (final response)         (tool calls present)                ║
  ║  │                        │                                   ║
  ║  ▼                        ▼                                   ║
  ║  notion_saved?     for each tool_call:                        ║
  ║  │                   name = tool_call.function.name           ║
  ║  ├── NO →             args = json.loads(tool_call.args)       ║
  ║  │   append "You      result = session.call_tool(name, args)  ║
  ║  │   must call        tool_output = result.content[0].text    ║
  ║  │   save_to_notion"  │                                       ║
  ║  │   continue loop    if name == "save_to_notion":            ║
  ║  │                      if output.startswith("Error"):        ║
  ║  └── YES →               return f"Failed: {output}"           ║
  ║      embedded?           notion_saved = True                  ║
  ║      │                                                        ║
  ║      ├── NO →          if name == "embed_and_store":          ║
  ║      │   append "You     embedded_in_qdrant = True            ║
  ║      │   still need                                           ║
  ║      │   embed_and_store"append msg to messages               ║
  ║      │   continue loop  append tool_result to messages        ║
  ║      │                                                        ║
  ║      └── YES →          loop again ──────────────────────────►║
  ║          return msg.content                                   ║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

### worker() — Redis Consumer Loop

```
  asyncio.run(worker())
        │
        ▼
  redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        │
        ▼
  ╔═══════════════════════════════════════════════════════════════╗
  ║  INFINITE LOOP                                                ║
  ║                                                               ║
  ║  response = await redis.blpop(JOB_QUEUE, timeout=0)          ║
  ║                  (blocks here indefinitely until job arrives) ║
  ║                                                               ║
  ║  _, raw = response                                            ║
  ║  job = json.loads(raw)                                        ║
  ║  job_id = job["job_id"]                                       ║
  ║  url    = job["url"]                                          ║
  ║                                                               ║
  ║  try:                                                         ║
  ║      result_text = await process_url(url)   ← full pipeline   ║
  ║  except Exception as e:                                       ║
  ║      result_text = f"Error processing reel: {e}"             ║
  ║                                                               ║
  ║  await redis.rpush(f"result:{job_id}",                        ║
  ║                    json.dumps({"text": result_text}))         ║
  ║  await redis.expire(f"result:{job_id}", RESULT_TTL)           ║
  ║                                                               ║
  ║  loop back to BLPOP ─────────────────────────────────────────►║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

### _mcp_tools_to_openai(tools)

Converts MCP tool list into OpenAI function-calling format.

```
  Input:  list of MCP Tool objects
            .name         →  string
            .description  →  string
            .inputSchema  →  JSON Schema dict

  Output: list of OpenAI tool dicts
  [
    {
      "type": "function",
      "function": {
        "name":        tool.name,
        "description": tool.description,
        "parameters":  tool.inputSchema
      }
    }
  ]

  Called once per process_url() call, after session.list_tools().
```

---

## 4. server.py — MCP Tool Contracts

FastMCP wraps each Python function as a callable MCP tool. agent.py receives tool schemas
via `list_tools()` and calls them via `call_tool(name, args)`.

**Invariant:** All tools return strings. On failure, they return `"Error: ..."`.
They never raise exceptions to the MCP layer.

---

### Tool 1 — download_reel

```
  Input:   url (str) — YouTube or Instagram reel URL
  Returns: "/tmp/reels/audio.mp3"  on success
           "Error: yt-dlp not found"  if yt-dlp is missing
           "Error downloading: <stderr>"  on download failure

  Logic:
  ┌────────────────────────────────────────────────────────────────┐
  │  os.makedirs("/tmp/reels", exist_ok=True)                      │
  │  output_path = "/tmp/reels/audio.mp3"                          │
  │                                                                │
  │  subprocess.run([                                              │
  │    "yt-dlp",                                                   │
  │    "-x",                          ← extract audio only         │
  │    "--audio-format", "mp3",       ← convert to mp3             │
  │    "-o", output_path,             ← fixed output path          │
  │    "--force-overwrites",          ← overwrite stale file       │
  │    url                                                         │
  │  ], capture_output=True, text=True, check=True)                │
  │                                                                │
  │  return output_path                                            │
  └────────────────────────────────────────────────────────────────┘

  Why fixed path: agent always passes the same path to transcribe_audio.
  Why --force-overwrites: prevents stale files from prior failed runs.
```

---

### Tool 2 — transcribe_audio

```
  Input:   file_path (str) — path returned by download_reel
  Returns: full transcript text  on success
           "Error transcribing: <detail>"  if both paths fail

  Logic:
  ┌────────────────────────────────────────────────────────────────┐
  │  try:                                                          │
  │    model  = whisper.load_model("base")   ← ~140MB, downloaded  │
  │    result = model.transcribe(file_path)    once and cached      │
  │    return result["text"]                                       │
  │                                                                │
  │  except Exception:           ← SSL error, model download fail  │
  │    with open(file_path, "rb") as f:                            │
  │      response = openai_client.audio.transcriptions.create(     │
  │          model="gpt-4o-mini-transcribe",                       │
  │          file=f                                                │
  │      )                                                         │
  │    return response.text                                        │
  │                                                                │
  │  finally:                    ← always runs                     │
  │    if os.path.exists(file_path):                               │
  │      os.remove(file_path)    ← clean up temp audio             │
  └────────────────────────────────────────────────────────────────┘
```

### Transcription Fallback Decision

```
  transcribe_audio(file_path) called
           │
           ▼
  ┌────────────────────────────────┐
  │  whisper.load_model("base")    │  ← try local first (free, offline)
  │  model.transcribe(file_path)   │
  └──────────────┬─────────────────┘
                 │
       success? ─┼── YES → transcript ready
                 │
                NO (network issue, SSL cert error,
                    model cache corrupted, etc.)
                 │
                 ▼
  ┌────────────────────────────────┐
  │  openai.audio.transcriptions   │  ← fallback (costs ~$0.006/min)
  │  .create(gpt-4o-mini-transcribe│
  │          file=audio_file)      │
  └──────────────┬─────────────────┘
                 │
       success? ─┼── YES → transcript ready
                 │
                NO → "Error transcribing: <detail>"
                 │
                 ▼
  [finally block always runs]
  os.remove(file_path)   ← temp audio deleted regardless of outcome
```

---

### Tool 3 — get_existing_topics

```
  Input:   none
  Returns: "Technology / AI & Machine Learning\nBusiness / Investing\n..."
           "No topics yet."  if database is empty
           "Error fetching topics: <detail>"  on Notion API failure

  Logic:
  ┌────────────────────────────────────────────────────────────────┐
  │  POST https://api.notion.com/v1/databases/{ID}/query           │
  │  Headers: Authorization: Bearer {NOTION_TOKEN}                 │
  │           Notion-Version: 2022-06-28                           │
  │                                                                │
  │  For each page in response["results"]:                         │
  │    topic    = _extract_text(page["properties"]["Topic"])       │
  │    subtopic = _extract_text(page["properties"]["Subtopic"])    │
  │    if topic and subtopic:                                      │
  │      collect "{topic} / {subtopic}"                            │
  │                                                                │
  │  return "\n".join(collected)  or  "No topics yet."             │
  └────────────────────────────────────────────────────────────────┘

  Purpose: Agent reads existing topics before classifying so it reuses
  exact spellings. Notion is case-sensitive — "AI" ≠ "Ai".
```

---

### Tool 4 — save_to_notion

```
  Input:   topic (str), subtopic (str), content (str — bullet-point summary)
  Returns: "https://notion.so/..."  on success
           "Error saving to Notion: <detail>"  on failure

  Notion page created:
  ┌────────────────────────────────────────────────────────────────┐
  │  {                                                             │
  │    "parent": {"database_id": NOTION_DATABASE_ID},             │
  │    "properties": {                                             │
  │      "Name":     {"title":     [{"text": {"content":          │
  │                    "{topic} — {subtopic}"}}]},                 │
  │      "Topic":    {"rich_text": [{"text": {"content": topic}}]},│
  │      "Subtopic": {"rich_text": [{"text": {"content":subtopic}}]}
  │    },                                                          │
  │    "children": [{                                              │
  │      "object": "block", "type": "paragraph",                  │
  │      "paragraph": {                                            │
  │        "rich_text": [{"type": "text",                          │
  │                       "text": {"content": content}}]           │
  │      }                                                         │
  │    }]                                                          │
  │  }                                                             │
  └────────────────────────────────────────────────────────────────┘

  Returns response["url"] — the direct Notion page link.
```

---

### Tool 5 — embed_and_store

```
  Input:   text (str), topic (str), subtopic (str),
           source_url (str), summary (str)
  Returns: UUID string of stored Qdrant point
           "Error embedding: <detail>"  on failure

  Logic:
  ┌────────────────────────────────────────────────────────────────┐
  │  metadata = {                                                  │
  │    "topic":      topic,                                        │
  │    "subtopic":   subtopic,                                     │
  │    "source_url": source_url,                                   │
  │    "summary":    summary                                       │
  │  }                                                             │
  │  point_id = store_reel(text, metadata)  ← qdrant_helper        │
  │  return point_id                                               │
  └────────────────────────────────────────────────────────────────┘

  Full flow inside qdrant_helper:
  text → embed_text() → 1536-dim vector → qdrant.upsert(point)
```

---

### Tool 6 — get_similar_reels

```
  Input:   query (str), limit (int, default=5)
  Returns: formatted result string
           "No similar reels found."  if collection is empty or no match
           "Error searching: <detail>"  on Qdrant failure

  Logic:
  ┌────────────────────────────────────────────────────────────────┐
  │  hits = search_reels(query, limit)   ← qdrant_helper           │
  │                                                                │
  │  for hit in hits:                                              │
  │    format as:                                                  │
  │      "Score: {hit['score']:.2f} | {hit['topic']} / {subtopic} │
  │       Summary: {hit['summary']}                                │
  │       Source: {hit['source_url']}"                             │
  │                                                                │
  │  return "\n\n".join(formatted) or "No similar reels found."   │
  └────────────────────────────────────────────────────────────────┘
```

---

### Helper — _extract_text(prop)

```python
items = prop.get("title") or prop.get("rich_text") or []
return "".join(item["plain_text"] for item in items)
```
Parses Notion property dicts (either title or rich_text type) into plain text.

---

## 5. qdrant_helper.py

### Configuration

```python
COLLECTION_NAME = "reels"               # Qdrant collection name
VECTOR_SIZE     = 1536                  # text-embedding-3-small output dimension
QDRANT_URL      = os.getenv("QDRANT_URL", "http://localhost:6333")
```

### Module-Level Initialisation (runs on import)

```
  import qdrant_helper
        │
        ▼
  openai_client = OpenAI(api_key=OPENAI_API_KEY)
  qdrant = QdrantClient(url=QDRANT_URL)
        │
        ▼
  qdrant.collection_exists("reels")?
        │
  ┌─────┴──────┐
  YES          NO
  │            │
  │            ▼
  │    qdrant.create_collection(
  │      "reels",
  │      VectorParams(size=1536, distance=COSINE)
  │    )
  │
  ▼
  module ready — embed_text(), store_reel(), search_reels() available
```

Why on import: collection must exist before any tool calls are made.
`collection_exists` check is idempotent — repeated imports never wipe data.

---

### embed_text(text) → list[float]

```
  text (str) — any length transcript or query
        │
        ▼
  openai_client.embeddings.create(
      model="text-embedding-3-small",
      input=text
  )
        │
        ▼
  response.data[0].embedding
        │
        ▼
  list[float] — exactly 1536 values, range roughly -1.0 to +1.0
```

**Why text-embedding-3-small:** 1536 dims; balance of cost, speed, quality.
**Critical:** same model at ingest AND query time. Mismatched models = incomparable vectors.

---

### store_reel(text, metadata) → str

```
  text (str), metadata (dict)
        │
        ▼
  point_id = str(uuid.uuid4())    ← fresh UUID for each ingest
  vector   = embed_text(text)     ← 1536 floats
  payload  = {
    "text":       text,
    "topic":      metadata.get("topic", ""),
    "subtopic":   metadata.get("subtopic", ""),
    "source_url": metadata.get("source_url", ""),
    "summary":    metadata.get("summary", "")
  }
        │
        ▼
  qdrant.upsert(
      collection_name="reels",
      points=[PointStruct(id=point_id, vector=vector, payload=payload)]
  )
        │
        ▼
  return point_id   (UUID string)
```

**Why upsert:** safe to call multiple times. If the same URL is ingested twice,
it creates a second point — no automatic deduplication at storage level.

---

### search_reels(query, limit=5) → list[dict]

```
  query (str) — natural language question or topic
        │
        ▼
  query_vector = embed_text(query)    ← same model as ingest
        │
        ▼
  qdrant.query_points(
      collection_name="reels",
      query=query_vector,
      limit=limit
  )
        │
        ▼
  for each point in results.points:
    {
      "text":       point.payload["text"],
      "topic":      point.payload["topic"],
      "subtopic":   point.payload["subtopic"],
      "source_url": point.payload["source_url"],
      "summary":    point.payload["summary"],
      "score":      point.score        ← cosine similarity 0.0–1.0
    }
        │
        ▼
  return list[dict]
```

---

## 6. Data Schemas

### 6.1 Redis — Job Payload

```
  Written by: bot.py    Read by: agent.py

  Key:   jobs:pending         (Redis FIFO list)
  Value: JSON string

  {
    "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",   ← uuid4
    "url":    "https://www.youtube.com/shorts/abc123"
  }
```

### 6.2 Redis — Result Payload

```
  Written by: agent.py   Read by: bot.py

  Key:   result:{job_id}    (unique per request; expires after RESULT_TTL=600s)
  Value: JSON string

  {
    "text": "Topic: Technology / AI & Machine Learning\n• LLMs use...\n• ..."
  }
```

### 6.3 Notion — Page Schema

```
  ┌──────────────────────────────────────────────────────────────┐
  │  Notion Database Page                                        │
  │                                                              │
  │  Name       (title)      "Technology — AI & Machine Learning"│
  │  Topic      (rich_text)  "Technology"                        │
  │  Subtopic   (rich_text)  "AI & Machine Learning"             │
  │                                                              │
  │  Body (paragraph block):                                     │
  │    • LLMs use attention mechanisms to weigh key words        │
  │    • Pre-training on large corpora enables transfer learning  │
  │    • Fine-tuning adapts the model to specific tasks          │
  └──────────────────────────────────────────────────────────────┘

  Name = f"{topic} — {subtopic}"   (constructed in save_to_notion, not by agent)
```

### 6.4 Qdrant — Point Schema

```
  Collection:  "reels"
  Vector size: 1536
  Distance:    COSINE

  ┌──────────────────────────────────────────────────────────────┐
  │  Point                                                       │
  │                                                              │
  │  id:      "f47ac10b-58cc-4372-a567-0e02b2c3d479"  (UUID)    │
  │  vector:  [0.021, -0.043, 0.009, ..., 0.017]      (1536 ×)  │
  │  payload: {                                                  │
  │    "text":       "Full raw transcript text...",              │
  │    "topic":      "Technology",                               │
  │    "subtopic":   "AI & Machine Learning",                    │
  │    "source_url": "https://youtube.com/shorts/abc123",        │
  │    "summary":    "• LLMs use attention...\n• Pre-training..."│
  │  }                                                           │
  └──────────────────────────────────────────────────────────────┘
```

### 6.5 Environment Variables

| Variable | Required | Set In | Default | Description |
|---|---|---|---|---|
| `OPENAI_API_KEY` | Yes | `.env` | — | GPT-4o, Whisper fallback, embeddings |
| `NOTION_TOKEN` | Yes | `.env` | — | Notion integration secret |
| `NOTION_DATABASE_ID` | Yes | `.env` | — | Target Notion database UUID |
| `TELEGRAM_BOT_TOKEN` | Yes | `.env` | — | BotFather token |
| `REDIS_URL` | No | `docker-compose.yml` | `redis://redis:6379` | Auto-set by Compose |
| `QDRANT_URL` | No | `docker-compose.yml` | `http://localhost:6333` | Auto-set by Compose |

`REDIS_URL` and `QDRANT_URL` use Docker Compose service hostnames.
They do not belong in `.env`.

---

## 7. Full Ingest Sequence

```
 User      Telegram    bot.py       Redis       agent.py    server.py   Notion  Qdrant
  │            │          │            │             │            │         │       │
  │─send URL──►│          │            │             │            │         │       │
  │            │─update──►│            │             │            │         │       │
  │            │          │─RPUSH─────►│             │            │         │       │
  │            │          │            │             │            │         │       │
  │            │          │◄─"Got it"  │             │            │         │       │
  │◄─"Got it"─│          │            │             │            │         │       │
  │            │          │─BLPOP(300s)►│             │            │         │       │
  │            │          │  (waiting) │─BLPOP(0)───►│            │         │       │
  │            │          │            │             │─start stdio►│         │       │
  │            │          │            │             │─list_tools─►│         │       │
  │            │          │            │             │◄─6 schemas──│         │       │
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: tool_call download_reel    │       │
  │            │          │            │             │─call_tool──►│         │       │
  │            │          │            │             │             │─yt-dlp  │       │
  │            │          │            │             │◄─/tmp/audio─│         │       │
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: tool_call transcribe_audio │       │
  │            │          │            │             │─call_tool──►│         │       │
  │            │          │            │             │             │─Whisper │       │
  │            │          │            │             │◄─transcript─│         │       │
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: tool_call get_existing_topics      │
  │            │          │            │             │─call_tool──►│         │       │
  │            │          │            │             │             │─GET────►│       │
  │            │          │            │             │◄─topics─────│◄─topics─│       │
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: reasons (picks topic/subtopic)     │
  │            │          │            │  GPT-4o: tool_call save_to_notion  │        │
  │            │          │            │             │─call_tool──►│         │       │
  │            │          │            │             │             │─POST───►│       │
  │            │          │            │             │◄─page URL───│◄─URL────│       │
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: tool_call embed_and_store  │       │
  │            │          │            │             │─call_tool──►│         │       │
  │            │          │            │             │             │─embed───────────►│
  │            │          │            │             │◄─uuid───────│◄─stored─────────│
  │            │          │            │             │             │         │       │
  │            │          │            │  GPT-4o: final reply (no tool_calls)        │
  │            │          │            │◄─RPUSH result:{id}────────│         │       │
  │            │          │◄─BLPOP─────│             │            │         │       │
  │            │◄─summary─│            │             │            │         │       │
  │◄─summary──│          │            │             │            │         │       │
```

---

## 8. Error Handling Matrix

```
  ┌──────────────────────┬──────────────────────────────┬──────────────────────────────┐
  │  Tool                │  Failure Mode                │  What Happens                │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  download_reel       │  yt-dlp not installed        │  "Error: yt-dlp not found"   │
  │                      │                              │  → agent includes in reply   │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  download_reel       │  Private/unavailable video   │  "Error downloading: <stderr>"│
  │                      │                              │  → pipeline halts            │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  transcribe_audio    │  Local Whisper fails         │  API fallback kicks in        │
  │                      │                              │  → transparent to agent      │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  transcribe_audio    │  Both local and API fail     │  "Error transcribing: ..."   │
  │                      │                              │  → agent includes in reply   │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  get_existing_topics │  Notion auth failure         │  "Error fetching topics: ..." │
  │                      │                              │  → agent classifies without  │
  │                      │                              │    existing context          │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  save_to_notion      │  Notion 401 (bad token)      │  "Error saving to Notion: ..." │
  │                      │  Notion 404 (wrong DB ID)    │  → agent.py returns error    │
  │                      │                              │    text; marks save failed   │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  embed_and_store     │  Qdrant unreachable          │  "Error embedding: ..."      │
  │                      │                              │  → included in reply         │
  │                      │                              │  → Notion save still succeeds│
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  get_similar_reels   │  No results found            │  "No similar reels found."   │
  │                      │                              │  → agent tells user          │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  get_similar_reels   │  Qdrant unreachable          │  "Error searching: ..."      │
  │                      │                              │  → included in reply         │
  ├──────────────────────┼──────────────────────────────┼──────────────────────────────┤
  │  Any tool            │  Uncaught exception          │  Exception message returned  │
  │                      │                              │  as string to agent          │
  └──────────────────────┴──────────────────────────────┴──────────────────────────────┘

  Key invariant: tools NEVER raise exceptions to the MCP layer.
  All errors are return values. The agent loop never crashes on tool failure.

  agent.py worker() outer try/except catches any exception from process_url()
  and pushes the error text as the result — bot always gets a response.
```

---

## 9. Topic Classification Logic

```
  transcript ready
       │
       ▼
  get_existing_topics() called
       │
       ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  existing = ["Technology / AI & Machine Learning",             │
  │              "Business / Investing", ...]                      │
  └───────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
  GPT-4o applies these rules (from system prompt + topic-map.md context):

  ┌──────────────────────────────────────────────────────────────────┐
  │  Rule 1: Prefer specificity                                      │
  │    "AI & Machine Learning" over "Technology"                     │
  │    when content is clearly about AI.                             │
  │                                                                  │
  │  Rule 2: Reuse existing first                                    │
  │    Match existing topic/subtopic EXACTLY (case-sensitive).       │
  │    Only create new if no existing fits.                          │
  │                                                                  │
  │  Rule 3: One topic, one subtopic                                 │
  │    Never assign multiple categories to a single reel.            │
  │                                                                  │
  │  Rule 4: Short subtopic labels                                   │
  │    Keep under 30 characters.                                     │
  │                                                                  │
  │  Rule 5: Unknown content                                         │
  │    Use topic "Uncategorised" / subtopic "Review Needed"          │
  │    for unclear transcripts.                                      │
  └──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  topic    = "Technology"                                         │
  │  subtopic = "AI & Machine Learning"                              │
  └──────────────────────────────────────────────────────────────────┘
       │                              │
       ▼                              ▼
  save_to_notion(topic,          embed_and_store(text, topic,
    subtopic, content)             subtopic, source_url, summary)

  Available top-level topics:
  Technology | Business & Finance | Science | Personal Development
  Health & Fitness | Arts & Culture | Cooking & Food | Travel & Geography

  Full subtopic list: docs/topic-map.md
```
