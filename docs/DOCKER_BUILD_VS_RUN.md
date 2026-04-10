# docker build vs docker run

## The one-line difference

| Command | What it does | When you run it |
|---|---|---|
| `docker build` | Reads the Dockerfile, executes each instruction, and produces a saved **image** | Once — or whenever code changes |
| `docker run` | Takes an existing image and starts a live **container** from it | Every time you want to run the app |

An image is a frozen snapshot. A container is that snapshot brought to life.

---

## Analogy

- `docker build` = baking a cake from a recipe. The cake is the image.
- `docker run` = slicing and serving a piece of that cake. The slice is the container.

You bake once, serve many times.

---

## docker build — step by step

When you run:

```bash
docker build -t reel-knowledge-bot .
```

Here is exactly what happens, in order:

---

### Step 1 — Read the build context

The `.` at the end tells Docker: "the build context is this directory."

Docker sends every file in that directory (minus anything in `.dockerignore`) to the Docker daemon. The daemon is the background process that actually does the building.

This is why `.dockerignore` matters — if you forget it, Docker ships your entire `venv/` folder (hundreds of MB) to the daemon before even starting.

---

### Step 2 — Parse the Dockerfile

Docker reads the Dockerfile top to bottom and identifies each instruction:
`FROM`, `RUN`, `COPY`, `ENV`, `CMD`, etc.

---

### Step 3 — Execute each instruction as a layer

Every instruction creates a new **layer** — a thin, read-only slice stacked on top of the previous one.

```
Layer 0  FROM python:3.11-slim          ← pulled from Docker Hub
Layer 1  RUN apt-get install ffmpeg...  ← ffmpeg + curl + unzip added
Layer 2  RUN curl ... deno install      ← deno binary added
Layer 3  ENV DENO_INSTALL ...           ← metadata only, no filesystem change
Layer 4  ENV PATH ...                   ← metadata only
Layer 5  WORKDIR /app                   ← /app directory created
Layer 6  COPY requirements.txt .        ← requirements.txt appears in /app
Layer 7  RUN pip install ...            ← packages installed into site-packages
Layer 8  COPY . .                       ← your source files appear in /app
Layer 9  ENV OPENAI_API_KEY="" ...      ← metadata only
Layer 10 CMD ["python", "bot.py"]       ← metadata only (no filesystem change)
```

Each layer only stores the *diff* from the layer below it — like git commits.

---

### Step 4 — Check the cache before each layer

Before executing a layer, Docker checks: "have I built this exact layer before?"

- If yes → **cache hit**: skip the work, reuse the saved layer instantly.
- If no → **cache miss**: execute the instruction, build the new layer.

Cache is invalidated when:
- The instruction text changes
- For `COPY`: the file contents change
- Any layer above was a cache miss (everything below it re-runs)

This is why the Dockerfile copies `requirements.txt` before copying source code:

```dockerfile
COPY requirements.txt .        # only invalidates if requirements change
RUN pip install ...            # reused from cache on most rebuilds
COPY . .                       # invalidates on every source change
```

If you swapped the order, every source code change would re-trigger `pip install`.

---

### Step 5 — Tag the final image

The `-t reel-knowledge-bot` flag gives the finished image a human-readable name.

Without `-t`, the image is only addressable by its SHA256 hash (ugly, hard to use).

---

### Step 6 — Image is stored locally

The image now lives in Docker's local storage on your machine.

```bash
docker images          # see all local images
docker image ls        # same thing
```

Nothing is running yet. The image is inert until you `docker run` it.

---

## docker run — what happens

```bash
docker run --env-file .env reel-knowledge-bot
```

1. Docker finds the image named `reel-knowledge-bot` in local storage.
2. Creates a new **container** — a writable layer on top of the image's read-only layers.
3. Injects environment variables from `--env-file .env` into the container's environment.
4. Executes the `CMD` instruction: `python bot.py`.
5. The container runs until the process exits or you press Ctrl+C.

The image is never modified. You can run ten containers from the same image simultaneously and they are completely isolated from each other.

---

## Side-by-side summary

```
docker build                          docker run
─────────────────────────────────     ──────────────────────────────────
Reads Dockerfile                      Reads a built image
Executes RUN/COPY/ENV instructions    Executes CMD instruction
Produces a saved image                Produces a running container
Uses your source files                Uses the snapshot baked into image
Runs once per code change             Runs every time you start the app
Nothing is "live" after it            App is live until process exits
```

---

## Common mistakes

**Editing a file and running `docker run` without rebuilding**
Your change is not in the image. The container runs the old code.
Always `docker build` first if source files changed.

**Not using `.dockerignore`**
`venv/` alone can be 500MB+ — Docker sends all of it to the daemon on every build even though it's never used.

**Putting `COPY . .` before `pip install`**
Every source file change busts the pip cache layer, causing a full package reinstall on every build.
