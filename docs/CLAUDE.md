# Reel Knowledge Agent

## What this does
Telegram bot that receives Instagram/YouTube reel links,
downloads audio, transcribes it using Whisper,
Claude extracts key concepts and topic,
saves structured notes to Notion automatically.

## Stack
- Python 3.10+
- mcp (Anthropic MCP SDK)
- yt-dlp (download reels)
- openai-whisper (transcribe audio locally)
- Notion API (save notes)
- Telegram Bot API (receive links)

## Files
- server.py — MCP server with all tools
- agent.py — MCP client + agentic loop
- bot.py — Telegram bot
- topic-map.md — topic classification rules

## Tools in server.py
- download_reel(url) — downloads audio using yt-dlp
- transcribe_audio(file_path) — transcribes using Whisper
- get_existing_topics() — reads Notion structure
- save_to_notion(topic, subtopic, content) — saves notes

## Rules
- Never hardcode tokens — always from .env
- download_reel saves audio to /tmp/reels/
- transcribe_audio always deletes audio file after transcription

---

## New Architecture (v2)

This project now combines three AI patterns:
- MCP: Tools for downloading, transcribing, saving to Notion
- RAG: Qdrant vector database for semantic search across saved reels
- LangGraph: Orchestrates the full pipeline as a graph with nodes

## Two Flows

1. INGEST: reel link → download → transcribe → extract → save Notion + Qdrant
2. RETRIEVAL: question → embed → search Qdrant → answer from saved reels

## New Files
- graph/state.py — shared state between LangGraph nodes
- graph/nodes.py — each processing step as a function
- graph/router.py — decides ingest vs retrieval
- qdrant_helper.py — Qdrant connection and search helpers

## New Tools in server.py
- embed_and_store(text, metadata) — embeds text and saves to Qdrant
- get_similar_reels(query, limit) — semantic search across saved reels