# Docker Compose — What it solves and how it works

## What a single Dockerfile cannot do

A Dockerfile describes **one container**. That's its limit.

Real applications are rarely one thing. This project has:
- A Telegram bot process
- An agent that orchestrates tool calls
- An MCP server that does the actual work
- External services (Notion, OpenAI, Telegram API)

Even if you kept everything in one container, you'd still face these problems:

| Problem | Single Dockerfile | Docker Compose |
|---|---|---|
| Running multiple services | You'd need a process manager inside the container (hacky) | Each service is its own container, managed cleanly |
| Shared config (env vars) | You'd pass `-e KEY=VAL` for every variable on every `docker run` | `env_file: .env` once, shared across all services |
| Automatic restarts | You'd write a shell loop or use a separate tool | `restart: unless-stopped` built in |
| Starting everything at once | Multiple terminal tabs, multiple commands | `docker compose up` — one command |
| Stopping everything at once | Hunt down each container and stop it | `docker compose down` — one command |
| Shared storage between containers | Manually create and mount volumes per `docker run` | Named volumes declared once, referenced by any service |

Docker Compose is a **declarative configuration file** for a group of containers that belong together.

---

## The two services in this project

### Why two services and not one?

`bot.py` imports `agent.py` directly as a Python module — they are not independent network services. The full runtime chain within the `bot` container looks like this:

```
bot container
└── python bot.py
    └── imports process_url() from agent.py
        └── spawns server.py as a stdio subprocess
            ├── calls yt-dlp
            ├── calls Whisper
            └── calls Notion API
```

The `bot` service handles everything when you're running the Telegram bot.

The `agent` service is a **separate container** that runs `agent.py` in CLI mode — useful for processing a URL directly without going through Telegram. It's the same image, different entry point, different purpose.

---

## Every line in docker-compose.yml

### `version: "3.9"`

The Compose file format version. Determines which features are available.
`3.9` is the most recent stable version and supports everything used here.

---

### `services:`

The top-level key that groups all container definitions.
Everything nested under it is a named service.

---

### `bot:` / `agent:`

The service name. This becomes:
- The container's hostname on the internal Docker network (containers can reach each other at `http://bot/` or `http://agent/`)
- The name you use in CLI commands: `docker compose logs bot`, `docker compose restart agent`

---

### `build: .`

Tells Compose to build the image from the `Dockerfile` in the current directory (`.`).
Both services use the same build, so Docker builds the image once and reuses it for both containers.

If you had a pre-built image on Docker Hub you'd write `image: yourname/reel-bot:latest` instead.

---

### `command: python bot.py` / `command: python agent.py`

Overrides the `CMD` instruction in the Dockerfile.
This makes it explicit in the Compose file which entry point each service uses,
even though the Dockerfile already defaults to `python bot.py`.

---

### `env_file: - .env`

Loads every `KEY=VALUE` line from `.env` into the container's environment.
The file is read at `docker compose up` time — it is never copied into the image.

Without this, you'd pass every secret with `-e` flags:
```bash
docker run -e OPENAI_API_KEY=sk-... -e NOTION_TOKEN=ntn_... ...
```
`env_file` does that for all four variables, for both services, automatically.

---

### `restart: unless-stopped` (bot) / `restart: "no"` (agent)

Controls what Docker does when a container exits.

| Value | Behaviour |
|---|---|
| `"no"` | Never restart (default) |
| `always` | Always restart, even after `docker compose stop` |
| `unless-stopped` | Restart on crash or reboot, but respect manual stops |
| `on-failure` | Restart only if the exit code is non-zero |

`bot` uses `unless-stopped` because it's a daemon — it should survive crashes and reboots.
`agent` uses `"no"` because it's a one-shot CLI tool — it exits after processing a URL,
and restarting it would just prompt for another URL indefinitely.

---

### `stdin_open: true` and `tty: true` (agent only)

`stdin_open` keeps the container's standard input open so you can type input to the process.
`tty` allocates a pseudo-terminal so output renders correctly (colours, progress bars from yt-dlp and Whisper).

Equivalent to `docker run -it` on the command line.
Without these, running `agent.py` without a URL argument would hang silently.

---

### `volumes: - audio_tmp:/tmp/reels`

Mounts the named volume `audio_tmp` at `/tmp/reels` inside each container.

`yt-dlp` downloads audio to `/tmp/reels/audio.mp3`.
Whisper reads it, then `transcribe_audio()` deletes it.

Using a named volume instead of the container's ephemeral storage means:
- The `/tmp/reels` directory survives container restarts
- If a crash happened mid-download, the directory still exists on the next start

---

### `volumes: audio_tmp:` (at the bottom)

Declares the named volume at the top level.
Docker creates and manages it. It persists across `docker compose down` (but not `docker compose down --volumes`).
Both services can mount it — if you ran bot and agent simultaneously, they'd share the same `/tmp/reels`.

---

## How to use it

```bash
# Build the image and start the bot in the background
docker compose up --build -d bot

# Watch live logs
docker compose logs -f bot

# Process one URL directly (no Telegram), then remove the container
docker compose run --rm agent python agent.py https://youtube.com/shorts/xxxx

# Stop the bot
docker compose stop bot

# Stop and remove containers (keeps the volume and image)
docker compose down

# Stop, remove containers, AND delete the audio volume
docker compose down --volumes
```

---

## The difference in one sentence

A **Dockerfile** describes how to build one container.
**Docker Compose** describes how to run, connect, and manage a group of containers as a single application.
