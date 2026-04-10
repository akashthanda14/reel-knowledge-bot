# What is a Dockerfile?

## The problem it solves

You build a Python project on your laptop. It works perfectly.
You send it to a friend. It breaks — wrong Python version, missing library, different OS.

A Dockerfile solves this by packaging your app and everything it needs into one portable unit called a **container**.

---

## A simple mental model

Think of it like this:

| Concept | Real-world analogy |
|---|---|
| **Dockerfile** | A recipe |
| **Image** | A cake baked from that recipe |
| **Container** | The cake being served (running) |

- The **Dockerfile** is a plain text file with step-by-step instructions.
- Docker reads those instructions and builds an **image** — a frozen snapshot of your app + its environment.
- When you run that image, it becomes a **container** — a live, isolated process.

---

## Why "isolated"?

A container runs in its own bubble:
- Its own filesystem
- Its own Python version
- Its own installed packages

It does not touch your laptop's Python, your system packages, or any other container. This is why "it works on my machine" becomes "it works on every machine."

---

## The lifecycle

```
Dockerfile
    │
    │  docker build
    ▼
  Image  ──── stored locally or on Docker Hub
    │
    │  docker run
    ▼
Container  ──── your app is running
```

---

## See also

- [`DOCKERFILE_EXPLAINED.md`](DOCKERFILE_EXPLAINED.md) — the actual 5-line Dockerfile with line-by-line breakdown
