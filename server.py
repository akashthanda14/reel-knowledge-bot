import os
import subprocess

import requests
import whisper
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

from qdrant_helper import search_reels, store_reel

load_dotenv()

# FastMCP exposes regular Python functions as tools callable by the agent.
mcp = FastMCP("reel-knowledge")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


@mcp.tool()
def download_reel(url: str) -> str:
    """Download audio from an Instagram or YouTube reel URL.
    Returns the file path on success or an error message on failure."""
    # Fixed output path keeps the pipeline simple (download -> transcribe).
    output_path = "/tmp/reels/audio.mp3"
    os.makedirs("/tmp/reels", exist_ok=True)

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--output", output_path,
                "--no-playlist",
                "--force-overwrites",
                url,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return f"Error downloading audio: {result.stderr.strip()}"
        return output_path
    except FileNotFoundError:
        return "Error: yt-dlp is not installed or not found in PATH"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio file using Whisper. Deletes the file after transcription.
    Returns the transcript text or an error message."""
    if not os.path.exists(file_path):
        return f"Error: file not found at {file_path}"

    try:
        # Primary path: local Whisper model.
        model = whisper.load_model("base")
        result = model.transcribe(file_path)
        transcript = result["text"].strip()
        return transcript
    except Exception as e:
        local_error = str(e)

        # Fallback path: OpenAI transcription (useful for SSL/cert/model-download issues).
        if OPENAI_API_KEY:
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                with open(file_path, "rb") as audio_file:
                    resp = client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe",
                        file=audio_file,
                    )
                text = (getattr(resp, "text", "") or "").strip()
                if text:
                    return text
                return "Error transcribing audio: OpenAI transcription returned empty text"
            except Exception as fallback_error:
                return (
                    "Error transcribing audio: "
                    f"local Whisper failed ({local_error}); "
                    f"OpenAI fallback failed ({fallback_error})"
                )

        return f"Error transcribing audio: {local_error}"
    finally:
        # Always remove temporary audio to keep /tmp clean.
        if os.path.exists(file_path):
            os.remove(file_path)


@mcp.tool()
def get_existing_topics() -> str:
    """Retrieve existing topics and subtopics from the Notion database.
    Returns a JSON-formatted string of topic/subtopic pairs."""
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return "Error: NOTION_TOKEN or NOTION_DATABASE_ID not set in .env"

    try:
        url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
        response = requests.post(url, headers=NOTION_HEADERS, json={})
        response.raise_for_status()

        # Read existing pages to help topic/subtopic reuse.
        pages = response.json().get("results", [])
        topics = []
        for page in pages:
            props = page.get("properties", {})
            topic = _extract_text(props.get("Topic"))
            subtopic = _extract_text(props.get("Subtopic"))
            if topic:
                topics.append({"topic": topic, "subtopic": subtopic})

        if not topics:
            return "No existing topics found."

        lines = [f"- {t['topic']} / {t['subtopic']}" for t in topics]
        return "Existing topics:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error fetching topics from Notion: {e}"


@mcp.tool()
def save_to_notion(topic: str, subtopic: str, content: str) -> str:
    """Save structured notes to Notion under the given topic and subtopic.
    Returns a success message with the page URL or an error message."""
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return "Error: NOTION_TOKEN or NOTION_DATABASE_ID not set in .env"

    try:
        # Maps directly to the Notion database schema: Name (title), Topic, Subtopic.
        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": f"{topic} — {subtopic}"}}]
                },
                "Topic": {
                    "rich_text": [{"text": {"content": topic}}]
                },
                "Subtopic": {
                    "rich_text": [{"text": {"content": subtopic}}]
                },
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ],
        }

        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=NOTION_HEADERS,
            json=payload,
        )
        response.raise_for_status()
        page_url = response.json().get("url", "")
        return f"Saved to Notion: {page_url}"
    except Exception as e:
        return f"Error saving to Notion: {e}"


def _extract_text(prop: dict) -> str:
    """Helper to pull plain text out of a Notion property."""
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "title":
        items = prop.get("title", [])
    elif prop_type == "rich_text":
        items = prop.get("rich_text", [])
    else:
        return ""
    return "".join(item.get("plain_text", "") for item in items)


# ── RAG tools ─────────────────────────────────────────────────────────────────
# The two tools below implement the RAG (Retrieval-Augmented Generation) pattern.
#
# RAG = storing knowledge as vectors so the agent can retrieve relevant
# context before generating an answer, rather than relying on model memory alone.
#
# embed_and_store → the "Augmented" write side: save new knowledge into the vector DB.
# get_similar_reels → the "Retrieval" read side: fetch relevant knowledge at query time.


# RAG pattern — memory write
# Every time a reel is ingested, this tool creates a vector embedding of the
# transcript and stores it in Qdrant alongside the metadata. This is the moment
# RAG memory is created: the transcript moves from ephemeral text into a
# persistent, searchable vector index that the agent can query later.
@mcp.tool()
def embed_and_store(
    text: str,
    topic: str,
    subtopic: str,
    source_url: str,
    summary: str,
) -> str:
    """Embed a reel transcript and store it in the Qdrant vector database.

    Converts the transcript text into a 1536-dimension vector using
    OpenAI text-embedding-3-small, then saves the vector and metadata
    as a searchable point in the 'reels' Qdrant collection.

    Args:
        text:       Full transcript text to embed.
        topic:      Top-level topic (e.g. "Technology").
        subtopic:   Specific subtopic (e.g. "AI & Machine Learning").
        source_url: Original reel URL — stored for attribution.
        summary:    Bullet-point summary that was saved to Notion.

    Returns:
        "Stored successfully with id: {uuid}" on success, or an error string.
    """
    # This is where RAG memory is created.
    try:
        metadata = {
            "topic": topic,
            "subtopic": subtopic,
            "source_url": source_url,
            "summary": summary,
        }
        # store_reel embeds text, builds a PointStruct, and upserts into Qdrant.
        # It returns the UUID assigned to this point in the collection.
        point_id = store_reel(text, metadata)
        return f"Stored successfully with id: {point_id}"
    except Exception as e:
        return f"Error storing in Qdrant: {e}"


# RAG pattern — memory retrieval
# When the user asks a question, this tool converts the question into a vector
# and searches Qdrant for the most similar transcript vectors. The results give
# the agent factual context from previously saved reels before it generates
# an answer — this is the core RAG retrieval step.
@mcp.tool()
def get_similar_reels(query: str, limit: int = 5) -> str:
    """Search the Qdrant vector database for reels semantically similar to a query.

    Embeds the query string using the same model used at ingest time
    (text-embedding-3-small), then returns the closest matching reel
    transcripts ranked by cosine similarity score.

    Args:
        query: A natural-language question or topic, e.g.
               "What did I learn about sleep and recovery?"
        limit: Maximum number of results to return. Default 5.

    Returns:
        A formatted string listing each result with its score, summary,
        and topic — ready for the agent to read and use as context.
        Returns an error string if the search fails.
    """
    # This is where RAG retrieval happens.
    try:
        results = search_reels(query, limit)

        if not results:
            return "No similar reels found."

        # Format each result as a readable line for the agent.
        # The agent reads this text and uses it as grounding context
        # before generating its answer to the user.
        lines = []
        for i, reel in enumerate(results, start=1):
            score = round(reel["score"], 2)
            summary = reel["summary"] or reel["text"][:120]
            topic = reel["topic"]
            subtopic = reel["subtopic"]
            source = reel["source_url"]
            lines.append(
                f"Reel {i} (score: {score}): {summary} | "
                f"Topic: {topic} / {subtopic} | Source: {source}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching Qdrant: {e}"


if __name__ == "__main__":
    mcp.run()
