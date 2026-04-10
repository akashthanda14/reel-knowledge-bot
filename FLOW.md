# Reel Knowledge Agent — System Flow

## Current Status
- [x] MCP Server with download_reel, transcribe_audio, save_to_notion
- [ ] Qdrant RAG integration
- [ ] LangGraph orchestration
- [ ] Router node (ingest vs retrieval)
- [ ] Full end-to-end test

## Architecture

```
INGEST FLOW
──────────────────────────────────────────────
Telegram (reel link)
    ↓
LangGraph Router → detects URL → ingest pipeline
    ↓
Node 1: download_reel (MCP tool)
    ↓
Node 2: transcribe_audio (MCP tool)
    ↓
Node 3: extract_knowledge (Claude)
    → topic, subtopic, key concepts, summary
    ↓
Node 4: store (parallel)
    ├── save_to_notion (MCP tool)
    └── embed_and_store (MCP tool → Qdrant)
    ↓
Node 5: reply to user

RETRIEVAL FLOW
──────────────────────────────────────────────
Telegram (question)
    ↓
LangGraph Router → detects question → retrieval pipeline
    ↓
Node 1: embed question
    ↓
Node 2: get_similar_reels (MCP tool → Qdrant search)
    ↓
Node 3: Claude reads results → generates answer
    ↓
Node 4: reply with answer + sources
```

## MCP Tools
| Tool | Input | Output | Status |
|------|-------|--------|--------|
| download_reel | url | file_path | ✅ done |
| transcribe_audio | file_path | text | ✅ done |
| save_to_notion | topic, subtopic, content | success/fail | ✅ done |
| embed_and_store | text, metadata | vector_id | 🔄 building |
| get_similar_reels | query, limit | list of reels | 🔄 building |

## LangGraph Nodes
| Node | Job | Status |
|------|-----|--------|
| router | decides ingest vs retrieval | 🔄 building |
| download_node | calls download_reel tool | 🔄 building |
| transcribe_node | calls transcribe_audio tool | 🔄 building |
| extract_node | Claude extracts knowledge | 🔄 building |
| store_node | saves to Notion + Qdrant | 🔄 building |
| retrieve_node | searches Qdrant | 🔄 building |
| answer_node | Claude answers from context | 🔄 building |
| reply_node | sends Telegram message | 🔄 building |
