# Running Qdrant Locally with Docker

## The exact command

```bash
docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant
```

Run this from the project root. It starts the Qdrant server and persists
all data to a `qdrant_data/` folder in your current directory.

---

## What each part does

### `docker run`
Start a new container from an image.

---

### `qdrant/qdrant`
The image to use — pulled from Docker Hub if not already local.
No version tag here means Docker fetches `latest`.
For reproducibility, pin it: `qdrant/qdrant:v1.14.0`

---

### `-p 6333:6333`
**Publish a port.** Format is `host_port:container_port`.

Qdrant inside the container listens on port 6333.
This flag maps that internal port to port 6333 on your laptop.

Without `-p`, the port is only reachable from inside Docker's internal
network — your Python code running locally cannot connect to it.
With `-p`, `http://localhost:6333` on your laptop reaches Qdrant.

```
Your laptop           Docker container
  localhost:6333  →→→  :6333 (Qdrant REST API)
```

---

### `-p 6334:6334`
Same idea for the gRPC port. Optional — only needed if you use
`qdrant-client` with `prefer_grpc=True`. Included here for completeness.

---

### `-v $(pwd)/qdrant_data:/qdrant/storage`

This is the `-v` flag — **volume mount**. The most important flag here.

#### Format: `-v source:destination`

| Part | Value | Meaning |
|---|---|---|
| source | `$(pwd)/qdrant_data` | A folder on **your laptop** |
| destination | `/qdrant/storage` | Where Qdrant reads/writes data **inside the container** |

#### What it does

Docker containers have their own isolated filesystem.
Any file written inside the container normally disappears when the
container stops — the filesystem is ephemeral.

`-v` punches a hole between the two filesystems.
Writes inside `/qdrant/storage` go directly to `./qdrant_data` on your laptop.
When the container stops and restarts, the data is still there.

```
Your laptop                    Docker container
./qdrant_data/  ←── synced ──→  /qdrant/storage/
  collections/                    collections/
    reels/                          reels/
      segments/                       segments/
```

#### Without -v

```bash
docker run -p 6333:6333 qdrant/qdrant   # no -v
```

Every time you stop and restart the container, all stored vectors,
collections, and search indexes are gone. You'd have to re-ingest
every reel from scratch.

#### With -v

```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant
```

Data lives on your laptop. Stop and restart the container as many
times as you want — all vectors and collections survive.

---

### `$(pwd)`

A shell expansion that inserts the current working directory as an
absolute path. Docker requires an absolute path for the source of a
bind mount — you cannot write `-v ./qdrant_data:/qdrant/storage`
directly (it won't work on all platforms).

`$(pwd)/qdrant_data` expands to something like:
`/Users/work/Desktop/reel-knowledge-agent/qdrant_data`

On Windows PowerShell, replace `$(pwd)` with `${PWD}`:
```
-v ${PWD}/qdrant_data:/qdrant/storage
```

---

## After running the command

```
...
           _                 _
  __ _  __| |_ __ __ _ _ __ | |_
 / _` |/ _` | '__/ _` | '_ \| __|
| (_| | (_| | | | (_| | | | | |_
 \__, |\__,_|_|  \__,_|_| |_|\__|
    |_|

Access web UI at http://localhost:6333/dashboard
```

- REST API: `http://localhost:6333`
- Web dashboard: `http://localhost:6333/dashboard` — browse collections and run searches in the browser
- gRPC: `localhost:6334`

Your Python code in `qdrant_helper.py` connects to `http://localhost:6333`
(the default when `QDRANT_URL` is not set in `.env`).

---

## Difference between -v and named volumes

| | Bind mount (`-v ./folder:/path`) | Named volume (`-v myvolume:/path`) |
|---|---|---|
| Storage location | A specific folder you choose on your laptop | Managed by Docker, hidden in Docker's internal storage |
| Visibility | `ls ./qdrant_data` — you can see and edit files | `docker volume inspect myvolume` — not directly accessible |
| Used in | Local development (this command) | docker-compose.yml in production |
| Portability | Tied to your directory structure | Self-contained, works anywhere |

`docker-compose.yml` uses a named volume (`qdrant_data:`) because Compose
manages the storage. This command uses a bind mount because you're running
directly with `docker run` and want to control exactly where the data lives.
