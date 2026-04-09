import os
import subprocess

import requests
import whisper
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

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


if __name__ == "__main__":
    mcp.run()
