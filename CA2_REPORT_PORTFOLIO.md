# CA2 Report + Portfolio
## AI Knowledge Engine (Reel Knowledge Agent)

---

## 1) Student Information
- **Student Name:** [Your Name]
- **Roll Number:** [Your Roll No]
- **Program / Semester:** [Program, Sem]
- **Course / Subject:** [Course Name]
- **Faculty Name:** [Faculty Name]
- **Submission Date:** 15 April 2026

---

## 2) Abstract
This project implements an AI-powered knowledge pipeline that converts unstructured reel/video content into structured, searchable knowledge. A user sends an Instagram or YouTube reel link to a Telegram bot. The system downloads the audio, transcribes it using Whisper (with OpenAI fallback), extracts key learning points, classifies the content into topic/subtopic, stores structured notes in Notion, and saves semantic embeddings in Qdrant for retrieval. 

The architecture uses Docker Compose with four services (`bot`, `agent`, `redis`, `qdrant`) to separate messaging, processing, queueing, and vector storage. Redis decouples the Telegram interface from slow AI processing, improving reliability and responsiveness. The project demonstrates practical skills in AI orchestration, tool calling, queue-driven system design, RAG implementation, and production-style local deployment. The result is a “second brain” workflow: users can capture knowledge from short-form content and retrieve it later by meaning, not just keywords.

---

## 3) Problem Statement
Educational insights from reels/short videos are usually lost due to fast scrolling and lack of structured capture. Manual note-taking is inconsistent and non-scalable.

### Objective
Build a local, modular AI system that:
1. Accepts reel/video links from users.
2. Converts audio/video into text.
3. Extracts structured concepts (topic, subtopic, summary).
4. Saves knowledge to Notion.
5. Enables semantic retrieval through vector search (RAG).

---

## 4) Scope
### In Scope
- Telegram-based input.
- Reel audio download using `yt-dlp`.
- Transcription using local Whisper + OpenAI fallback.
- AI reasoning loop with tool calling.
- Structured storage in Notion.
- Embedding and semantic search in Qdrant.
- Dockerized multi-container deployment.

### Out of Scope (Current Version)
- Web dashboard/UI.
- Multi-user authentication.
- Analytics panel.
- Cloud deployment autoscaling.

---

## 5) System Architecture
### High-Level Flow
User → Telegram Bot → Redis Queue → Agent Worker → MCP Tools → Notion + Qdrant → Response to User

### Components
1. **`bot.py`**: Telegram interface; validates links, pushes jobs, waits for results.
2. **`agent.py`**: Worker loop; pops jobs and runs AI tool-orchestration pipeline.
3. **`server.py`**: MCP tool server exposing download/transcribe/save/embed/search functions.
4. **Redis**: Job queue (`jobs:pending`) and result synchronization (`result:{job_id}`).
5. **Qdrant**: Vector database for semantic retrieval.
6. **Notion**: Structured long-term knowledge store.

### Deployment Model
- Docker Compose, 4 containers:
  - `redis`
  - `qdrant`
  - `bot`
  - `agent`

---

## 6) Technology Stack and Justification
| Layer | Technology | Why Used |
|---|---|---|
| Messaging Interface | python-telegram-bot | Easy Telegram integration |
| Queue | Redis | Fast, simple FIFO queue with blocking pop |
| AI Agent | OpenAI GPT-4o | Reliable tool-calling + reasoning |
| Tool Protocol | MCP (FastMCP) | Clean separation between agent and tools |
| Transcription | openai-whisper + OpenAI API fallback | Offline-first + robust fallback |
| Video/Audio ingestion | yt-dlp + ffmpeg | Standard for reel/short extraction |
| Vector DB | Qdrant | Efficient similarity search for RAG |
| Structured Storage | Notion API | Human-readable knowledge base |
| Containerization | Docker Compose | Reproducible local environment |

---

## 7) Functional Modules
### 7.1 Input Handling
- User sends URL to Telegram bot.
- URL is wrapped in JSON job payload and pushed to Redis list.

### 7.2 Agentic Processing
- Worker consumes queued job.
- AI loop decides tool calls in sequence.
- Pipeline enforces `save_to_notion` before final completion and nudges `embed_and_store` for vector memory.

### 7.3 MCP Tool Layer
Implemented tools:
1. `download_reel(url)`
2. `transcribe_audio(file_path)`
3. `get_existing_topics()`
4. `save_to_notion(topic, subtopic, content)`
5. `embed_and_store(text, topic, subtopic, source_url, summary)`
6. `get_similar_reels(query, limit=5)`

### 7.4 RAG Retrieval
- At ingest: transcript → embedding → Qdrant point with metadata.
- At query: user query → embedding → nearest vectors → grounded response context.

---

## 8) Data Flow (Detailed)
1. Telegram receives reel URL.
2. `bot.py` pushes `{job_id, url}` to `jobs:pending`.
3. `agent.py` performs `BLPOP` and receives job.
4. Agent starts MCP and calls:
   - download
   - transcription
   - topic checking
   - Notion save
   - Qdrant embedding storage
5. Agent pushes result to `result:{job_id}`.
6. `bot.py` reads result and replies to Telegram user.
7. Result key expires (TTL) to avoid stale data accumulation.

---

## 9) Testing and Results
### Test Cases
| TC ID | Input | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| TC-01 | Valid YouTube Shorts URL | Audio download + transcript + Notion entry + summary reply | Working as expected | Pass |
| TC-02 | Valid Instagram reel URL | End-to-end ingestion pipeline completes | Working as expected | Pass |
| TC-03 | Invalid/unsupported URL | User gets failure-safe error message | Error handled without crash | Pass |
| TC-04 | Notion API unavailable | Pipeline reports save error gracefully | Error surfaced, worker remains alive | Pass |
| TC-05 | Semantic search query | Relevant reels returned with scores | Similar items retrieved from Qdrant | Pass |

### Observed Outcome
- Queue-based architecture kept bot responsive even during long transcription.
- RAG retrieval improved reuse of previously captured knowledge.
- Containerized setup ensured reproducibility across systems.

---

## 10) Challenges and Solutions
### Challenge 1: Slow AI tasks blocking bot responsiveness
**Solution:** Introduced Redis queue with separate `bot` and `agent` services.

### Challenge 2: Transcription reliability
**Solution:** Implemented fallback from local Whisper to OpenAI transcription API.

### Challenge 3: Consistent topic organization
**Solution:** Added retrieval of existing Notion topics before creating new entries.

### Challenge 4: Retrieval quality
**Solution:** Stored embeddings with metadata in Qdrant and used similarity search.

---

## 11) Non-Functional Evaluation
| Parameter | Target | Outcome |
|---|---|---|
| Reliability | Worker should not crash on single bad URL | Achieved via try/except and queue isolation |
| Maintainability | Modular tools and services | Achieved through MCP + separate files |
| Portability | Run on any machine with Docker | Achieved with Compose setup |
| Usability | Simple Telegram UX | Achieved (single-link input workflow) |
| Scalability (basic) | Add more workers if required | Possible by scaling `agent` service |

---

## 12) Learning Outcomes
This project helped me build practical skills in:
- AI tool-calling workflows and prompt-driven orchestration.
- Queue-based asynchronous architecture.
- RAG fundamentals (embedding, indexing, retrieval).
- API integrations (Telegram, Notion, OpenAI).
- Production-style local deployment with Docker Compose.

---

## 13) Conclusion
The project successfully demonstrates an end-to-end AI knowledge engine that transforms unstructured reel content into structured and retrievable knowledge. It solves a real learning-retention problem and reflects industry-relevant engineering practices: modularity, asynchronous processing, retrieval augmentation, and reproducible deployment.

This implementation is a strong foundation for future upgrades such as web dashboard, user auth, feedback-driven ranking, and analytics.

---

## 14) Future Enhancements
1. Multi-user profiles with auth and per-user knowledge spaces.
2. Web dashboard for browsing notes and retrieval history.
3. Citation-style answer generation with source timestamps.
4. Automated duplicate detection and clustering.
5. Confidence scoring and evaluation benchmark for retrieval quality.

---

## 15) Portfolio Evidence (High-Weight Section)
### A) GitHub Repository Checklist
- [ ] Clean README with architecture and setup.
- [ ] Environment setup via `.env.example`.
- [ ] Screenshots of Telegram flow + Notion page + Qdrant search output.
- [ ] At least 10 meaningful commits showing progress.
- [ ] Proper project tags/topics and license.

### B) LinkedIn Checklist
- [ ] One project post (problem → approach → architecture → impact).
- [ ] Add repo in “Featured” section.
- [ ] Mention tools/skills used (Python, Docker, Redis, RAG, Notion API).
- [ ] Add short demo video link.

### C) Add these links before final submission
- **GitHub Repository:** [Paste URL]
- **LinkedIn Post:** [Paste URL]
- **Demo Video:** [Paste URL]

---

## 16) References
1. OpenAI API documentation.
2. Whisper transcription documentation.
3. Qdrant vector database documentation.
4. Redis command documentation (`RPUSH`, `BLPOP`, `EXPIRE`).
5. Notion API documentation.
6. Docker and Docker Compose documentation.

---

## 17) Appendix: Project Evidence from Codebase
- Core workflow: [agent.py](agent.py)
- Telegram interface: [bot.py](bot.py)
- MCP tools + Notion/Qdrant integration: [server.py](server.py)
- Vector helper: [qdrant_helper.py](qdrant_helper.py)
- Container orchestration: [docker-compose.yml](docker-compose.yml)
- Setup and usage: [README.md](README.md)
- Architecture notes: [docs/ARCHITECTURE_DIAGRAMS.md](docs/ARCHITECTURE_DIAGRAMS.md)

---

### Declaration
I confirm that this report is based on my implemented project work and that all external APIs/tools used are appropriately acknowledged.

**Signature:** ____________________

