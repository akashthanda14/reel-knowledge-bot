# Complete Guide — Reel Knowledge Agent
### From zero to a running bot, explained like you've never done this before

---

## What does this project actually do?

You send a YouTube or Instagram reel link to a Telegram bot.

The bot:
1. Downloads the audio from the video
2. Transcribes the audio into text (like subtitles)
3. Uses AI to read the transcript and pull out the key ideas
4. Saves a structured note to your Notion database (topic, subtopic, key concepts)
5. Also saves the knowledge to a search database so you can find it later by meaning

That's it. You send a link. You get a Notion note and a summary back — automatically.

---

## What you need before you start

You need four things installed on your computer:

| What | Why | How to get it |
|---|---|---|
| **Docker Desktop** | Runs the whole system — no manual installs needed | docker.com/products/docker-desktop |
| **Git** | To download this project | git-scm.com |
| **A terminal** | To type commands | Already on your computer (Terminal on Mac, Command Prompt on Windows) |
| **A text editor** | To edit one config file | VS Code, Notepad, anything |

You also need four accounts / API keys:

| What | Why it's needed | Where to get it |
|---|---|---|
| **OpenAI API key** | Powers the AI brain (GPT-4o) and transcription | platform.openai.com |
| **Notion account** | Where your notes are saved | notion.so |
| **Notion integration** | Gives the bot permission to write to your Notion | notion.so/my-integrations |
| **Telegram account** | The chat interface you'll use | Telegram app |

---

## Step 1 — Download the project

Open your terminal and run:

```bash
git clone https://github.com/your-username/reel-knowledge-agent.git
cd reel-knowledge-agent
```

> What this does: Downloads all the project files to your computer and moves you into that folder.

---

## Step 2 — Get your API keys

You need to collect four keys. Do this before touching any code.

---

### Key 1: OpenAI API Key

1. Go to **platform.openai.com** and sign in (or create a free account)
2. Click your profile picture (top right) → **API keys**
3. Click **"+ Create new secret key"**
4. Give it any name (like "reel-bot") and click **Create**
5. **Copy the key immediately** — it starts with `sk-` and you won't see it again
6. Make sure you have billing set up: go to **Settings → Billing → Add payment method**
   > The API is not free, but processing a few reels costs cents.

---

### Key 2 & 3: Notion Token + Database ID

**First — create a Notion database:**

1. Open **Notion** (notion.so) in your browser
2. Click **"+ New page"** in the left sidebar
3. Choose **"Table"** (full-page database, not inline)
4. Name it something like "Reel Knowledge"
5. The page is now a database — this is where all your notes will be saved

**Second — create a Notion integration:**

1. Go to **notion.so/my-integrations** in your browser
2. Click **"+ New integration"**
3. Give it a name like "Reel Bot"
4. Select your workspace
5. Click **Submit**
6. On the next page, click **"Show"** under "Internal Integration Secret"
7. **Copy the token** — it starts with `ntn_`

**Third — connect the integration to your database:**

1. Open the Notion database you just created
2. Click the **"..."** (three dots) button in the top right corner
3. Click **"Connections"**
4. Click **"Add connection"**
5. Search for your integration name ("Reel Bot") and click it
6. Click **"Confirm"**

> If you skip this step, the bot gets a "401 Unauthorized" error when trying to save notes.

**Fourth — get the Database ID:**

1. Open your Notion database
2. Look at the URL in your browser address bar:
   ```
   https://www.notion.so/YourWorkspace/THIS-IS-THE-DATABASE-ID?v=...
   ```
3. The database ID is the **32-character string** between the last `/` and the `?`
4. It looks like: `a1b2c3d4e5f6789012345678901234ab`
5. Copy it

---

### Key 4: Telegram Bot Token

1. Open the **Telegram app** on your phone or desktop
2. Search for **@BotFather** (the official Telegram bot)
3. Start a chat with it and send: `/newbot`
4. It will ask for a name — type anything (like "My Reel Bot")
5. It will ask for a username — must end in "bot" (like "myreel_knowledge_bot")
6. BotFather sends you a token that looks like: `123456789:ABCdef-GHI...`
7. **Copy it**

---

## Step 3 — Create your `.env` file

The `.env` file is where you store all your secret keys. The project reads from this file automatically.

In your terminal, inside the project folder:

```bash
cp .env.example .env
```

> This copies the example file to a real `.env` file.

Now open `.env` in your text editor. It looks like this:

```
OPENAI_API_KEY=sk-...
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdef-...
```

Replace each placeholder with your real values:

```
OPENAI_API_KEY=sk-abc123yourrealkeyhere
NOTION_TOKEN=ntn_yourrealnotiontoken
NOTION_DATABASE_ID=a1b2c3d4e5f6789012345678901234ab
TELEGRAM_BOT_TOKEN=123456789:ABCdef-GHIjkl
```

Save the file.

> **Important:** Never share this file with anyone. Never commit it to git. It contains your private API keys.

---

## Step 4 — Set up the Notion database fields (one time only)

Run this command once. It adds the "Topic" and "Subtopic" columns to your Notion database:

```bash
python setup_notion.py
```

You should see:
```
Connected to database: Reel Knowledge
Existing fields: ['Name']
Adding fields: ['Topic', 'Subtopic']
Done! Notion database is ready.
```

If you see an error:
- `401 Unauthorized` → You forgot to connect the integration to the database (Step 2, "Third")
- `404 Not Found` → Your `NOTION_DATABASE_ID` is wrong — double-check it

> Note: To run this you need Python installed locally. Only needed once. After this, everything runs inside Docker.

---

## Step 5 — Start the system

Run one command:

```bash
docker compose up --build
```

This does a lot automatically:
- Downloads and builds everything needed (takes 2–5 minutes the first time)
- Starts **4 containers** (mini-programs running inside Docker):
  - `redis` — a fast memory store that passes jobs between the bot and the AI
  - `qdrant` — a special database that stores knowledge for search
  - `bot` — your Telegram bot, listening for messages
  - `agent` — the AI worker that processes reels

When it's ready, you'll see something like:
```
bot_1    | Bot is running. Press Ctrl+C to stop.
agent_1  | [worker] Listening for jobs on 'jobs:pending' ...
```

The system is now live.

---

## Step 6 — Send your first reel

1. Open Telegram
2. Find the bot you created (search for the username you gave it)
3. Send it a YouTube or Instagram reel link, for example:
   ```
   https://www.youtube.com/shorts/abc123
   ```
4. The bot replies: **"Got it! Processing your reel..."**
5. Wait 30–90 seconds (the first run downloads the Whisper transcription model ~140MB)
6. The bot replies with a summary like:
   ```
   Topic: Technology / AI & Machine Learning
   
   Key concepts:
   • Transformers use attention mechanisms to weigh important words
   • Pre-training on large text corpora enables transfer learning
   • Fine-tuning adapts a base model to specific tasks
   ```
7. Check your Notion database — a new page has been created with the full note

---

## How it works (plain English)

When you send a link, here's exactly what happens behind the scenes:

```
You (Telegram)
    ↓ send link
Bot receives it
    ↓ puts job in Redis queue
AI Worker picks up the job
    ↓
  1. yt-dlp downloads the audio as an MP3
    ↓
  2. Whisper converts the audio to text (transcription)
    ↓
  3. Bot reads your existing Notion topics (to avoid duplicates)
    ↓
  4. GPT-4o reads the transcript and decides:
       - What topic is this? (e.g. "Technology")
       - What subtopic? (e.g. "AI & Machine Learning")
       - What are the 3–7 key concepts?
    ↓
  5. Saves structured note to Notion
    ↓
  6. Saves the transcript to Qdrant (search database)
    ↓
AI Worker sends result back through Redis
    ↓
Bot sends you the summary in Telegram
```

The whole thing is automatic. You send one link, you get a structured note.

---

## File structure (what each file does)

```
reel-knowledge-agent/
│
├── bot.py              ← The Telegram bot. Receives your links, sends replies.
├── agent.py            ← The AI brain. Downloads, transcribes, classifies, saves.
├── server.py           ← The tool box. Each action (download, transcribe, save) lives here.
├── qdrant_helper.py    ← Handles saving and searching the vector knowledge database.
├── setup_notion.py     ← One-time setup script for your Notion database.
│
├── docker-compose.yml  ← Tells Docker which containers to run and how they connect.
├── Dockerfile          ← Recipe for building the bot and agent containers.
├── requirements.txt    ← List of Python packages needed.
├── .env                ← YOUR secret keys (never share this file).
├── .env.example        ← Template showing what .env should look like.
│
└── docs/               ← Detailed documentation
    ├── PRD.md          ← What the product does and why
    ├── HLD.md          ← How the system is designed at a high level
    ├── LLD.md          ← Detailed technical design of every component
    ├── topic-map.md    ← The list of topics the AI uses to classify reels
    ├── API_KEYS.md     ← Step-by-step guide to getting each API key
    └── ...
```

---

## Stopping the system

Press `Ctrl+C` in the terminal where Docker is running.

Or from another terminal:
```bash
docker compose down
```

Your data (Qdrant vectors, Redis queue) is saved in Docker volumes and will be there when you start again.

---

## Starting again after a stop

```bash
docker compose up
```

No `--build` needed unless you changed code. If you changed code:
```bash
docker compose up --build
```

---

## Troubleshooting

### The bot doesn't reply

**Check 1:** Is Docker still running?
```bash
docker compose ps
```
All four services should show `Up`.

**Check 2:** Did you make a typo in `TELEGRAM_BOT_TOKEN`?
Open `.env` and double-check the token matches exactly what BotFather sent you.

**Check 3:** Are you messaging the right bot?
Make sure you're messaging the bot with the exact username you created with BotFather.

---

### "Processing timed out" message

The video is too long or your internet is slow. Try a shorter video (under 5 minutes).

Also check that the agent container is running:
```bash
docker compose logs agent
```

---

### Notion save fails (you see an error about Notion)

**Most common cause:** The integration is not connected to your database.

Fix:
1. Open your Notion database
2. Click **"..."** → **Connections** → **Add connection** → select your integration
3. Try sending the link again

---

### "Error: yt-dlp" or download fails

Some videos are private or geo-restricted — yt-dlp can't download those. Try a different public video.

---

### First message takes a long time

Normal. The first time `transcribe_audio` runs, it downloads the Whisper model (~140 MB).
After that first download it's cached and future transcriptions are much faster.

---

### How to see what's happening

To watch all container logs:
```bash
docker compose logs -f
```

To watch just the AI worker:
```bash
docker compose logs -f agent
```

You'll see lines like:
```
[worker] job=abc123... url=https://youtube.com/shorts/...
[agent] calling download_reel(...)
[agent] calling transcribe_audio(...)
[agent] calling get_existing_topics(...)
[agent] calling save_to_notion(...)
[agent] calling embed_and_store(...)
[worker] job=abc123... done
```

---

## Topic classification

The AI uses a built-in list of topics to categorise every reel. Top-level topics:

- Technology
- Business & Finance
- Science
- Personal Development
- Health & Fitness
- Arts & Culture
- Cooking & Food
- Travel & Geography

Each has subtopics. For example, "Technology" has: AI & Machine Learning, Software Engineering, Web Development, Cybersecurity, etc.

The full list is in `docs/topic-map.md`.

The AI always tries to reuse an existing topic/subtopic from your Notion database before creating a new one — this keeps your notes consistently organised.

---

## Environment variables reference

| Variable | What it is | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI secret key | platform.openai.com/api-keys |
| `NOTION_TOKEN` | Your Notion integration secret | notion.so/my-integrations |
| `NOTION_DATABASE_ID` | The ID of your Notion database | From the database URL |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | @BotFather on Telegram |

These two are set automatically by Docker — do not add them to `.env`:
- `REDIS_URL` — Docker sets this to `redis://redis:6379`
- `QDRANT_URL` — Docker sets this to `http://qdrant:6333`

---

## Quick-start checklist

Use this to make sure you haven't missed anything:

- [ ] Docker Desktop installed and running
- [ ] Project downloaded (`git clone ...`)
- [ ] `OPENAI_API_KEY` copied into `.env`
- [ ] Notion database created
- [ ] Notion integration created at notion.so/my-integrations
- [ ] Integration connected to the database (⋯ → Connections → Add connection)
- [ ] `NOTION_TOKEN` copied into `.env`
- [ ] `NOTION_DATABASE_ID` copied into `.env`
- [ ] Telegram bot created via @BotFather
- [ ] `TELEGRAM_BOT_TOKEN` copied into `.env`
- [ ] `python setup_notion.py` run successfully
- [ ] `docker compose up --build` run
- [ ] Bot replied "Got it! Processing your reel..." to your test link
- [ ] New page appeared in your Notion database

If all boxes are checked — you're done. The bot is running.
