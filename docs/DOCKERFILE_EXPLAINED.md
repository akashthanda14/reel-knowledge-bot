# A 5-Line Dockerfile for a Python Project

## The Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["python", "bot.py"]
```

---

## Line by line

### Line 1 — `FROM python:3.11-slim`

```dockerfile
FROM python:3.11-slim
```

**What it does:** Sets the starting point for your image.

Every Dockerfile starts with `FROM`. You are saying:
> "Start with an existing image that already has Python 3.11 installed."

`python:3.11-slim` is an official image published on Docker Hub.
The `-slim` variant is a smaller version of the image — it strips out tools you don't need, keeping the final image lighter.

You are not installing Python yourself. You are inheriting it.

---

### Line 2 — `WORKDIR /app`

```dockerfile
WORKDIR /app
```

**What it does:** Sets the working directory inside the container.

All following commands (`COPY`, `RUN`, `CMD`) will run from `/app`.
If `/app` does not exist inside the container, Docker creates it automatically.

Think of it as `cd /app` — but it also creates the folder if needed.

---

### Line 3 — `COPY requirements.txt .`

```dockerfile
COPY requirements.txt .
```

**What it does:** Copies `requirements.txt` from your laptop into the container.

The format is `COPY <source> <destination>`.
- Source: `requirements.txt` on your local machine.
- Destination: `.` means the current working directory inside the container — which is `/app` (set in line 2).

This is done before installing packages so Docker can cache the install step. If `requirements.txt` hasn't changed, Docker skips re-running `pip install` on the next build.

---

### Line 4 — `RUN pip install -r requirements.txt`

```dockerfile
RUN pip install -r requirements.txt
```

**What it does:** Installs your Python dependencies inside the container.

`RUN` executes a shell command during the build step.
This bakes all your libraries into the image so the container doesn't need internet access when it starts.

---

### Line 5 — `CMD ["python", "bot.py"]`

```dockerfile
CMD ["python", "bot.py"]
```

**What it does:** Tells Docker what command to run when the container starts.

`CMD` is the default startup command. When you run `docker run <image>`, this is what executes.

The array format `["python", "bot.py"]` is preferred over a plain string — it avoids launching an unnecessary shell process in between.

---

## Summary table

| Line | Instruction | Plain English |
|---|---|---|
| 1 | `FROM python:3.11-slim` | Start with Python 3.11 already installed |
| 2 | `WORKDIR /app` | All commands run from the `/app` folder |
| 3 | `COPY requirements.txt .` | Bring your dependency list into the container |
| 4 | `RUN pip install -r requirements.txt` | Install those dependencies |
| 5 | `CMD ["python", "bot.py"]` | Start the app when the container runs |

---

## How to use it

```bash
# Build the image (run once, or when code changes)
docker build -t reel-knowledge-bot .

# Run the container
docker run --env-file .env reel-knowledge-bot
```

`--env-file .env` passes your API keys from `.env` into the container at runtime — they are never baked into the image.

---

## See also

- [`DOCKER_INTRO.md`](DOCKER_INTRO.md) — what Docker is and why it exists
