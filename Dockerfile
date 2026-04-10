# ── Base image ────────────────────────────────────────────────────────────────
# Start from the official Python 3.11 slim image.
# "slim" strips out compilers, man pages, and other build tools that aren't
# needed at runtime, keeping the final image smaller (~150MB vs ~1GB full).
FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# apt-get update refreshes the package list so apt knows what's available.
# apt-get install -y installs without prompting for confirmation.
#   ffmpeg   — required by yt-dlp to convert/mux audio after download,
#              and by openai-whisper to decode audio before transcription.
#   curl     — used below to download the Deno installer script.
#   unzip    — used by the Deno installer to unpack the binary archive.
# The final && rm -rf /var/lib/apt/lists/* deletes the package index cache
# that apt-get update created. Those files are no longer needed and would
# just add size to the image layer.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# ── Deno ──────────────────────────────────────────────────────────────────────
# Download and run the official Deno install script.
# -f   fail silently on server errors (no half-downloaded output)
# -s   silent mode (no progress bar)
# -S   show errors even in silent mode
# -L   follow redirects
# The script installs the Deno binary to /root/.deno/bin/deno by default.
RUN curl -fsSL https://deno.land/install.sh | sh

# Tell the shell where Deno lives.
# DENO_INSTALL is the root folder the installer created.
ENV DENO_INSTALL="/root/.deno"

# Prepend the Deno bin directory to PATH so every subsequent RUN, CMD, and
# ENTRYPOINT can find the `deno` command without a full path.
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

# ── Working directory ─────────────────────────────────────────────────────────
# Create (if it doesn't exist) and switch into /app inside the container.
# All COPY, RUN, and CMD instructions that follow use this as their base path.
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements.txt BEFORE copying the rest of the source code.
# Docker builds images in layers. If requirements.txt hasn't changed,
# Docker reuses the cached pip install layer and skips re-downloading
# all packages — this makes rebuilds much faster during development.
COPY requirements.txt .

# Install every package listed in requirements.txt.
# --no-cache-dir tells pip not to store downloaded wheels on disk.
# Inside a container there is no reason to cache them; skipping the cache
# keeps the image smaller.
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
# Copy everything that wasn't excluded by .dockerignore into /app.
# This happens after pip install so that changing your Python source files
# does not invalidate the (slow) package install layer.
COPY . .

# ── Runtime environment variables ─────────────────────────────────────────────
# Declare the four variables the app reads from .env.
# These are set to empty strings here — the real values are injected at
# runtime with: docker run --env-file .env ...
# NEVER hardcode actual secrets in a Dockerfile; the image would then
# contain them in its layer history, even if you later overwrite them.
ENV OPENAI_API_KEY=""
ENV NOTION_TOKEN=""
ENV NOTION_DATABASE_ID=""
ENV TELEGRAM_BOT_TOKEN=""

# ── Entry point ───────────────────────────────────────────────────────────────
# The command Docker runs when the container starts.
# Array ("exec") form is preferred over a plain string:
#   plain string → Docker wraps it in /bin/sh -c "python bot.py"
#   array form   → Docker runs python directly, no shell in between.
# This means Ctrl+C (SIGTERM) reaches the Python process instead of
# being swallowed by the shell — so graceful shutdown works correctly.
CMD ["python", "bot.py"]
