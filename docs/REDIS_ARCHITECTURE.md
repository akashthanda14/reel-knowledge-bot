# Redis Queue Architecture

## Why Redis was added

The previous architecture had `bot.py` importing `process_url()` from `agent.py` as a plain Python function. That meant they had to run in the same container — one process, tightly coupled.

```
Before (one container):
  bot.py → import agent.process_url() → server.py subprocess
  Everything lives in a single Python process. Cannot scale independently.
```

Redis adds a **message queue** between the two. Now they are genuinely independent services:

```
After (three containers):
  [bot]  →  RPUSH jobs:pending  →  [redis]  →  BLPOP  →  [agent]
  [bot]  ←  BLPOP result:{id}  ←  [redis]  ←  RPUSH  ←  [agent]
```

bot.py and agent.py have no import relationship. They only share Redis key names.

---

## The data flow step by step

```
1. User sends reel URL to Telegram
        │
        ▼
2. bot.py extracts URL, generates job_id = uuid4()
        │
        │  RPUSH jobs:pending  {"job_id": "abc123", "url": "https://..."}
        ▼
3. Redis holds the job in a list (FIFO queue)
        │
        │  BLPOP jobs:pending  (agent.py is blocking here)
        ▼
4. agent.py wakes up, deserialises the job, calls process_url(url)
        │   download → transcribe → classify → save to Notion
        │
        │  RPUSH result:abc123  {"text": "Topic: AI & ML\n• concept 1\n..."}
        ▼
5. Redis holds the result under a per-job key
        │
        │  BLPOP result:abc123  (bot.py is blocking here)
        ▼
6. bot.py wakes up, reads the result, replies to the Telegram user
```

---

## Redis commands used

| Command | Used by | What it does |
|---|---|---|
| `RPUSH key value` | bot.py (job), agent.py (result) | Append a value to the right end of a list |
| `BLPOP key timeout` | agent.py (job), bot.py (result) | Pop from the left end, blocking until something appears |
| `EXPIRE key seconds` | agent.py | Set a TTL on the result key so orphaned keys auto-delete |

### Why RPUSH + BLPOP (not PUBLISH/SUBSCRIBE)?

`PUBLISH/SUBSCRIBE` is fire-and-forget — if agent.py isn't listening when a message arrives, it's lost.

`RPUSH` + `BLPOP` on a list is a **persistent queue** — the job stays in the list until a consumer pops it. If agent.py crashes and restarts, the job is still there waiting.

---

## Key naming conventions

| Key | Written by | Read by | Format |
|---|---|---|---|
| `jobs:pending` | bot.py | agent.py | JSON: `{job_id, url}` |
| `result:{job_id}` | agent.py | bot.py | JSON: `{text}` |

The `jobs:pending` list can hold many jobs — they queue up and agent.py processes them one at a time (or you can run multiple agent containers to process in parallel).

Each `result:{job_id}` key is unique per request, so concurrent users don't see each other's results.

---

## What happens on failure

| Failure | What happens |
|---|---|
| **agent.py crashes mid-job** | Job is already popped from the queue — it is lost. Bot times out after 5 min. (For production, use `RPOPLPUSH` for reliable queuing.) |
| **bot.py crashes after pushing the job** | Agent finishes and writes the result. Bot never reads it. Result key expires after 10 min (RESULT_TTL). |
| **Redis crashes** | All queued jobs and in-flight results are lost if persistence is off. The named volume (`redis_data`) enables RDB snapshots, which recovers most data on restart. |
| **Timeout (5 min)** | bot.py stops waiting and sends a timeout message to the user. The agent may still finish and push a result — it just expires unread after 10 min. |

---

## How to scale

Because bot and agent are now decoupled, you can run multiple agent workers:

```bash
docker compose up --scale agent=3
```

Three agent containers all BLPOP from the same `jobs:pending` list.
Redis delivers each job to exactly one worker — no duplicates.
The bot container stays as one instance (Telegram polling doesn't scale horizontally).

---

## Environment variables added

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379` | Connection string for both bot and agent |
| `RESULT_TTL` | `600` (10 min) | Seconds before an unread result key auto-deletes |
| `RESULT_TIMEOUT` | `300` (5 min) | Seconds bot.py waits before giving up on a job |
