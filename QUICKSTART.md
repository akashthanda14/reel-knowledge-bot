# Quickstart — Reel Knowledge Agent

---

## Step 1 — Get 4 API keys

You need exactly four keys. Nothing runs without them.

---

**OpenAI API Key**
- Go to platform.openai.com → click your avatar → API keys → Create new secret key
- Copy immediately — you won't see it again
- Add billing at Settings → Billing → Add payment method (processing a reel costs cents)
- Why: GPT-4o does the thinking. Whisper does the transcription. Embeddings power search. All three go through this one key.

---

**Notion Token**
- Go to notion.so/my-integrations → New integration → give it any name → Submit
- Click Show under "Internal Integration Secret" → copy the `ntn_...` token
- Why: this is the password that lets the bot write notes into your Notion workspace.

---

**Notion Database ID**
- In Notion, create a new full-page Table (not inline)
- Open it in the browser — the URL looks like:
  `https://notion.so/YourName/THIS-PART-IS-THE-ID?v=...`
- Copy the 32-character string between the last `/` and the `?`
- Then: open the database → `...` (top right) → Connections → Add connection → pick your integration
- Why: the token proves who you are; the database ID tells the bot where to write. The connection step gives it permission to actually do it.

---

**Telegram Bot Token**
- Open Telegram → search @BotFather → send `/newbot`
- Give it a name and a username (must end in `bot`)
- BotFather sends a token like `123456789:ABCdef-...` → copy it
- Why: this token is how your bot authenticates with Telegram's servers to receive messages and send replies.

---

## Step 2 — Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in the four values:

```
OPENAI_API_KEY=sk-...
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdef-...
```

Why: the app reads secrets from this file at startup. It never gets baked into the Docker image — kept on your machine only. Never commit this file to git.

---

## Step 3 — Set up Notion schema (run once)

```bash
pip install requests python-dotenv
python setup_notion.py
```

Expected output:
```
Connected to database: <your db name>
Adding fields: ['Topic', 'Subtopic']
Done! Notion database is ready.
```

Why: the bot saves a Topic and Subtopic for every reel. Notion databases don't have these columns by default — this script adds them. You only do this once.

Common errors:
- `401 Unauthorized` → you forgot to connect the integration to the database (Step 1, Notion Database ID, last bullet)
- `404 Not Found` → your `NOTION_DATABASE_ID` is wrong

---

## Step 4 — Start everything

```bash
docker compose up --build
```

This starts 4 containers:
- `redis` — the job queue between bot and agent
- `qdrant` — the vector database for semantic search
- `bot` — your Telegram bot, listening for messages
- `agent` — the AI worker that processes each reel

First run takes 2–5 minutes (builds the image, pulls redis and qdrant).

When ready you'll see:
```
bot_1    | Bot is running. Press Ctrl+C to stop.
agent_1  | [worker] Listening for jobs on 'jobs:pending' ...
```

Why `--build`: tells Docker to (re)build the image from the Dockerfile. Required on first run and any time you change code.

---

## Step 5 — Send a reel

Open Telegram → find your bot → send any YouTube Shorts or Instagram reel link:
```
https://www.youtube.com/shorts/abc123
```

Bot replies: `"Got it! Processing your reel..."`

Wait 30–90 seconds. First run is slower because Whisper downloads its transcription model (~140 MB) and caches it — every run after is faster.

Bot sends back:
```
Topic: Technology / AI & Machine Learning

Key concepts:
• Transformers use attention to weigh important words
• Pre-training on large corpora enables transfer learning
• Fine-tuning adapts a base model to specific tasks
```

A new page also appears in your Notion database.

---

## Day-to-day commands

```bash
# Stop all containers
docker compose down

# Start again (no code changes)
docker compose up

# Start again after changing code
docker compose up --build

# Watch what the AI worker is doing
docker compose logs -f agent

# Watch everything
docker compose logs -f
```

---

## Troubleshooting

**Bot doesn't reply**
```bash
docker compose ps   # all four services should show "Up"
```
If not — check your `TELEGRAM_BOT_TOKEN` in `.env`.

**Processing timed out**
The video is too long or the agent crashed. Check:
```bash
docker compose logs agent
```

**Notion save fails**
Almost always means the integration is not connected to the database.
Fix: open Notion DB → `...` → Connections → Add connection → pick your integration.

**First message is very slow**
Normal. Whisper model downloading. Future runs are fast.
