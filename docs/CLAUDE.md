# Reel Knowledge Agent

## What this does
Telegram bot that receives Instagram/YouTube reel links,
downloads audio, transcribes it using Whisper,
uses GPT-4o to extract key concepts and assign a topic,
saves structured notes to Notion, and embeds transcripts
into Qdrant for semantic search (RAG).

## Stack
- Python 3.11
- Docker Compose (4 containers: redis, qdrant, bot, agent)
- mcp (Anthropic MCP SDK)
- yt-dlp (download reels)
- openai-whisper (transcribe audio locally)
- OpenAI GPT-4o (reasoning + tool calling)
- OpenAI text-embedding-3-small (embeddings for RAG)
- Notion API (save notes)
- Telegram Bot API (receive links)
- Redis (job queue between bot and agent)
- Qdrant (vector store for semantic search)

## Files
- server.py — MCP server with all tools
- agent.py — Redis worker + OpenAI agentic loop
- bot.py — Telegram bot, pushes jobs to Redis
- qdrant_helper.py — Qdrant client, embed_text, store_reel, search_reels
- setup_notion.py — one-time Notion schema setup
- docker-compose.yml — 4-container runtime
- docs/topic-map.md — topic classification rules

## Tools in server.py
- download_reel(url) — downloads audio using yt-dlp to /tmp/reels/
- transcribe_audio(file_path) — transcribes using local Whisper (OpenAI API fallback)
- get_existing_topics() — reads Notion structure to reuse existing topics
- save_to_notion(topic, subtopic, content) — saves structured notes
- embed_and_store(text, metadata) — embeds transcript and stores in Qdrant
- get_similar_reels(query, limit) — semantic search across saved reels

## Two Flows
1. INGEST: reel link → download → transcribe → extract → save Notion + embed Qdrant
2. RETRIEVAL: question → get_similar_reels → LLM answers from context

## Rules
- Never hardcode tokens — always from .env
- download_reel saves audio to /tmp/reels/
- transcribe_audio always deletes audio file after transcription
- topic-map.md lives in docs/ — reference as docs/topic-map.md
