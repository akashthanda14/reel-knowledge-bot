# Architecture & Flow Diagrams — Reel Knowledge Agent

This file contains ready-to-teach diagrams using Mermaid.

---

## 1) High-level architecture

```mermaid
flowchart LR
    U[User on Telegram] --> B[bot.py\nTelegram Interface]
    B --> A[agent.py\nOrchestrator]
    A <--> M[MCP stdio session]
    M <--> S[server.py\nTool Server]
    S --> Y[yt-dlp + ffmpeg\nAudio extraction]
    S --> W[Whisper local\nTranscription]
    S --> O[OpenAI Audio API\nFallback transcription]
    A --> C[OpenAI Chat Model\nReasoning + Tool Calls]
    S --> N[Notion API\nDatabase Storage]
```

---

## 2) End-to-end sequence (single reel)

```mermaid
sequenceDiagram
    participant User
    participant Telegram as bot.py
    participant Agent as agent.py
    participant Model as OpenAI Chat
    participant MCP as MCP Session
    participant Server as server.py
    participant Notion as Notion API

    User->>Telegram: Send reel URL
    Telegram->>Agent: process_url(url)
    Agent->>MCP: start stdio server + initialize
    Agent->>MCP: list_tools()

    Agent->>Model: messages + tool schemas
    Model-->>Agent: call download_reel(url)
    Agent->>MCP: call_tool(download_reel)
    MCP->>Server: download_reel(url)
    Server-->>Agent: /tmp/reels/audio.mp3

    Agent->>Model: tool result
    Model-->>Agent: call transcribe_audio(path)
    Agent->>MCP: call_tool(transcribe_audio)
    MCP->>Server: transcribe_audio(path)
    alt local whisper works
        Server-->>Agent: transcript
    else local whisper fails
        Server->>Server: OpenAI transcription fallback
        Server-->>Agent: transcript
    end

    Agent->>Model: tool result
    Model-->>Agent: call get_existing_topics()
    Agent->>MCP: call_tool(get_existing_topics)
    MCP->>Server: get_existing_topics()
    Server->>Notion: query database
    Notion-->>Server: existing pages/topics
    Server-->>Agent: formatted topics

    Agent->>Model: transcript + topics
    Model-->>Agent: call save_to_notion(topic, subtopic, content)
    Agent->>MCP: call_tool(save_to_notion)
    MCP->>Server: save_to_notion(...)
    Server->>Notion: create page
    Notion-->>Server: page url
    Server-->>Agent: Saved to Notion: <url>

    Agent->>Model: save result
    Model-->>Agent: final summary
    Agent-->>Telegram: final text
    Telegram-->>User: reply
```

---

## 3) Agentic loop state flow

```mermaid
flowchart TD
    S0[Start process_url] --> S1[Build system + user messages]
    S1 --> S2[Call OpenAI chat completion]
    S2 --> Q{tool_calls present?}
    Q -- Yes --> T1[Execute each tool via MCP]
    T1 --> T2[Append tool outputs to messages]
    T2 --> S2
    Q -- No --> G{save_to_notion attempted?}
    G -- No --> R1[Inject reminder message\n"must call save_to_notion"]
    R1 --> S2
    G -- Yes --> G2{last save result starts with Error?}
    G2 -- Yes --> E[Return explicit Notion failure]
    G2 -- No --> F[Return final assistant summary]
```

---

## 4) Tool layer architecture

```mermaid
flowchart TB
    subgraph MCP_Server[server.py - FastMCP]
        D[download_reel(url)]
        T[transcribe_audio(file_path)]
        G[get_existing_topics()]
        V[save_to_notion(topic, subtopic, content)]
    end

    D --> D1[yt-dlp subprocess]
    D1 --> D2[/tmp/reels/audio.mp3]

    T --> T1[Whisper base local]
    T --> T2[OpenAI transcription fallback]
    T --> T3[cleanup temp file]

    G --> NQ[POST /databases/{id}/query]
    V --> NP[POST /pages]
```

---

## 5) Failure-handling flow

```mermaid
flowchart TD
    A[Incoming URL] --> B[download_reel]
    B -->|error| E1[Return error to agent]
    B -->|ok| C[transcribe_audio]
    C -->|local whisper ok| D[transcript ready]
    C -->|local whisper fail| C2[try OpenAI fallback]
    C2 -->|ok| D
    C2 -->|fail| E2[Return combined transcription error]
    D --> F[get_existing_topics]
    F -->|error| E3[Return Notion read error]
    F -->|ok| G[save_to_notion]
    G -->|error| E4[Agent returns explicit save failure]
    G -->|ok| H[Final success response]
```

---

## 6) One-line architecture summary

Telegram UI triggers an OpenAI-driven agent loop that calls MCP tools for media download/transcription/classification context and persists structured knowledge to Notion.
