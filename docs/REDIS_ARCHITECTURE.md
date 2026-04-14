# Redis Queue Architecture
## Reel Knowledge Agent

---

## 1. Why Redis Was Added

The original design had `bot.py` directly importing `process_url()` from `agent.py`.
Both lived in one Python process, one container — tightly coupled.

```
  BEFORE — one container, one process
  ┌────────────────────────────────────────────────────────────┐
  │                    single container                        │
  │                                                            │
  │   bot.py  ──── import ────►  agent.process_url()          │
  │                                     │                      │
  │                                     ▼                      │
  │                               server.py subprocess         │
  └────────────────────────────────────────────────────────────┘

  Problems:
  ✗ One crash kills everything
  ✗ Cannot scale agent independently
  ✗ Bot blocks while agent works — can't accept new messages
  ✗ No job persistence — crash = lost request
```

Redis adds a message queue between them. Now they are fully independent services:

```
  AFTER — four containers, decoupled via Redis

  ┌──────────────────┐               ┌──────────────────┐
  │   bot container  │               │  agent container  │
  │                  │    RPUSH      │                   │
  │  bot.py          │──────────────►│                   │
  │  (job producer)  │               │    Redis          │
  │  (result reader) │◄──────────────│   (middle layer)  │
  │                  │    BLPOP      │                   │
  └──────────────────┘               │  agent.py         │
                                     │  (job consumer)   │
                                     │  (result writer)  │
                                     └──────────────────┘

  ✓ Each can crash and restart independently
  ✓ Jobs persist in Redis across agent restarts
  ✓ Bot stays responsive while agent processes
  ✓ Scale agents with --scale agent=N
```

bot.py and agent.py share **no Python imports**. The only shared contract is
two Redis key names: `jobs:pending` and `result:{job_id}`.

---

## 2. Redis as a Queue — Core Concept

Redis lists are ordered sequences. RPUSH adds to the right (tail), BLPOP removes
from the left (head). This gives you a FIFO queue with blocking consumers.

```
  RPUSH jobs:pending  job_A
  RPUSH jobs:pending  job_B
  RPUSH jobs:pending  job_C

  Redis list state:
  ┌───────────────────────────────────────────────┐
  │  jobs:pending                                 │
  │  HEAD ◄──────────────────────────── TAIL      │
  │  [ job_A ] [ job_B ] [ job_C ]               │
  │     ▲                    ▲                    │
  │  BLPOP pops here    RPUSH adds here            │
  └───────────────────────────────────────────────┘

  BLPOP returns job_A (FIFO — first in, first out)
  Remaining: [ job_B ] [ job_C ]
```

---

## 3. Data Flow — Step by Step

```
  USER                  bot.py              Redis              agent.py
   │                       │                  │                    │
   │  sends reel URL        │                  │                    │
   │──────────────────────►│                  │                    │
   │                       │                  │                    │
   │                       │  1. validate URL  │                    │
   │                       │  2. job_id=uuid4()│                    │
   │                       │  3. RPUSH ───────►│                    │
   │                       │  jobs:pending     │                    │
   │                       │  {"job_id":"abc", │                    │
   │                       │   "url":"https://"}│                   │
   │                       │                  │                    │
   │◄──"Got it! Processing"─│                  │                    │
   │                       │                  │                    │
   │                       │  4. BLPOP        │                    │
   │                       │  result:abc      │                    │
   │                       │  (waiting...)    │                    │
   │                       │                  │◄── BLPOP ──────────│
   │                       │                  │  jobs:pending      │
   │                       │                  │  (was blocking)    │
   │                       │                  │                    │
   │                       │                  │  5. job popped     │
   │                       │                  │  job_id="abc"      │
   │                       │                  │  url="https://..." │
   │                       │                  │                    │
   │                       │                  │  6. process_url()  │
   │                       │                  │  download → transcribe
   │                       │                  │  → classify        │
   │                       │                  │  → save Notion     │
   │                       │                  │  → embed Qdrant    │
   │                       │                  │                    │
   │                       │                  │  7. RPUSH ─────────►│
   │                       │                  │  result:abc        │
   │                       │                  │  {"text":"Topic..."}│
   │                       │                  │                    │
   │                       │                  │  8. EXPIRE         │
   │                       │                  │  result:abc 600    │
   │                       │                  │                    │
   │                       │◄─ BLPOP wakes up─┤                    │
   │                       │  result:abc      │                    │
   │                       │                  │                    │
   │◄─── summary reply ────│                  │                    │
   │                       │                  │                    │
```

---

## 4. Key Lifecycle

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  Key: jobs:pending                                              │
  │                                                                 │
  │  Created by: RPUSH (bot.py)                                     │
  │  Consumed by: BLPOP (agent.py)                                  │
  │  Lifetime: exists until BLPOP pops it                           │
  │  Multiple jobs: queue up in FIFO order                          │
  │                                                                 │
  │  ──── timeline ────────────────────────────────────────────►   │
  │  bot RPUSH ──► [job_A, job_B, job_C]                           │
  │  agent BLPOP ──► job_A consumed                                 │
  │                  [job_B, job_C] remain                          │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  Key: result:{job_id}   e.g. result:abc123                      │
  │                                                                 │
  │  Created by: RPUSH (agent.py)                                   │
  │  Consumed by: BLPOP (bot.py)                                    │
  │  Lifetime: deleted when bot BLPOPs it                           │
  │            OR auto-deleted after RESULT_TTL=600s (EXPIRE)       │
  │                                                                 │
  │  ──── timeline ────────────────────────────────────────────►   │
  │  agent RPUSH result:abc ──► key exists                          │
  │  bot BLPOP result:abc   ──► key deleted (normal path)           │
  │                                                                 │
  │  if bot timed out (5 min):                                      │
  │  key sits in Redis ──────────────────────────────────────────►  │
  │  EXPIRE fires at T+600s ──► key auto-deleted                    │
  └─────────────────────────────────────────────────────────────────┘
```

---

## 5. Redis Commands

| Command | Used By | What It Does |
|---|---|---|
| `RPUSH key value` | bot.py (job), agent.py (result) | Append to right end (tail) of list |
| `BLPOP key timeout` | agent.py (job), bot.py (result) | Pop from left end (head), block until available |
| `EXPIRE key seconds` | agent.py | Set TTL — key auto-deletes if unread |

---

## 6. Why RPUSH + BLPOP, Not Pub/Sub

```
  PUBLISH / SUBSCRIBE                  RPUSH + BLPOP
  ─────────────────────                ─────────────────────────────
  Fire-and-forget                      Persistent until consumed

  Publisher sends message              RPUSH writes to a list
        │                                    │
        ▼                                    ▼
  Subscribers receive it         Redis holds it in the list
  IF they are listening                       │
        │                                    ▼
  If agent.py is down          BLPOP reads it when agent is ready
  ────────────────────         ────────────────────────────────────
  ✗ message is LOST            ✓ job survives agent restart

  Result: Pub/Sub drops jobs    Result: RPUSH+BLPOP is reliable
  on agent crash/restart        — job stays queued, no data loss
```

---

## 7. Key Naming Convention

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  jobs:pending                                                        │
  │                                                                      │
  │  One shared list — all bot instances push here                       │
  │  All agent instances pop from here                                   │
  │  Redis delivers each job to exactly ONE agent (no duplicates)        │
  └──────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │  result:{job_id}   e.g.  result:f47ac10b-58cc-4372-a567-0e02b2c3d479│
  │                                                                      │
  │  One key per request — unique UUID prevents crosstalk                │
  │  User A bot waits on result:abc                                      │
  │  User B bot waits on result:xyz                                      │
  │  They never see each other's results                                 │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Timeout and TTL Interaction

```
  T=0     User sends reel URL
          bot RPUSH jobs:pending
          bot BLPOP result:{id}  timeout=300  ← starts 5-min clock

  T=~60s  agent finishes processing
          agent RPUSH result:{id}
          agent EXPIRE result:{id} 600         ← starts 10-min TTL

          bot BLPOP wakes up (normal path)
          bot sends reply to user
          result:{id} key deleted

  ─────── TIMEOUT SCENARIO ──────────────────────────────────────────

  T=0     User sends reel URL
          bot BLPOP result:{id}  timeout=300

  T=300   bot times out
          bot replies: "Processing timed out..."
          bot continues listening for new messages

  T=~360  agent finishes (late)
          agent RPUSH result:{id}
          agent EXPIRE result:{id} 600

          result:{id} exists in Redis but nobody reads it

  T=960   EXPIRE fires → result:{id} auto-deleted
          no leak

  ┌───────────────────────────────────────────────────────────────┐
  │  RESULT_TIMEOUT (bot)  = 300s   ← how long bot waits          │
  │  RESULT_TTL (agent)    = 600s   ← how long result survives    │
  │                                                               │
  │  TTL > TIMEOUT always — gives agent time to finish even        │
  │  if bot has already given up, then cleans up automatically.   │
  └───────────────────────────────────────────────────────────────┘
```

---

## 9. Failure Scenarios

```
  ┌──────────────────────────┬────────────────────────────┬───────────────────────────┐
  │  Failure                 │  What Happens              │  Recovery                 │
  ├──────────────────────────┼────────────────────────────┼───────────────────────────┤
  │  agent crashes mid-job   │  Job already popped —      │  Docker restarts agent.   │
  │                          │  lost for that request.    │  Bot times out at T+300s. │
  │                          │  Agent restarts, picks     │  Future jobs unaffected.  │
  │                          │  up next job from queue.   │                           │
  ├──────────────────────────┼────────────────────────────┼───────────────────────────┤
  │  bot crashes after RPUSH │  Job stays in queue.       │  Docker restarts bot.     │
  │  (before BLPOP)          │  Agent processes it.       │  Result key expires       │
  │                          │  No bot to receive result. │  after RESULT_TTL.        │
  ├──────────────────────────┼────────────────────────────┼───────────────────────────┤
  │  Redis crashes           │  jobs:pending and all      │  redis_data named volume  │
  │                          │  result:{id} keys gone.    │  provides RDB snapshot.   │
  │                          │                            │  Docker restarts Redis.   │
  │                          │                            │  Most data recovered.     │
  ├──────────────────────────┼────────────────────────────┼───────────────────────────┤
  │  Bot timeout (5 min)     │  Bot sends timeout msg.    │  Agent may still finish.  │
  │                          │  Result key expires after  │  Result auto-cleaned      │
  │                          │  10 min if unread.         │  by EXPIRE.               │
  └──────────────────────────┴────────────────────────────┴───────────────────────────┘
```

---

## 10. Horizontal Scaling

Because bot and agent are decoupled, you can run multiple agent workers with one command:

```
  docker compose up --scale agent=3

  ┌──────────────────────────────────────────────────────────────────────┐
  │                          jobs:pending                                │
  │  [job_A] [job_B] [job_C] [job_D] [job_E]                            │
  └──────────────┬───────────────┬───────────────┬───────────────────────┘
                 │               │               │
          BLPOP pops      BLPOP pops      BLPOP pops
                 │               │               │
                 ▼               ▼               ▼
          ┌──────────┐    ┌──────────┐    ┌──────────┐
          │ agent #1 │    │ agent #2 │    │ agent #3 │
          │ job_A    │    │ job_B    │    │ job_C    │
          └──────────┘    └──────────┘    └──────────┘

  Redis delivers each job to exactly ONE agent — no duplicate processing.
  bot.py stays as one instance (Telegram long-polling doesn't scale horizontally).
```

---

## 11. Environment Variables

| Variable | Default | Set In | Description |
|---|---|---|---|
| `REDIS_URL` | `redis://redis:6379` | `docker-compose.yml` | Connection string — uses Docker Compose service hostname |
| `RESULT_TTL` | `600` (10 min) | `agent.py` constant | Seconds before unread result key auto-deletes |
| `RESULT_TIMEOUT` | `300` (5 min) | `bot.py` constant | Seconds bot waits before giving up on a job |

`REDIS_URL` is injected by Docker Compose at runtime using the `redis` service name.
It does not go in `.env` — the default `redis://redis:6379` works on all machines.
