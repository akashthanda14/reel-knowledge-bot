"""
Qdrant helper — vector storage and semantic search for reel transcripts.

Qdrant itself runs as a Docker container (see docker-compose.yml).
This file is the Python interface to it: embed text with OpenAI,
store vectors in Qdrant, search for similar reels by query.

Usage:
    from qdrant_helper import store_reel, search_reels
"""

import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

# OpenAI API key — used for text-embedding-3-small.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Qdrant server URL.
# Inside Docker Compose: QDRANT_URL=http://qdrant:6333 (set in docker-compose.yml).
# Running locally against the Docker-exposed port: defaults to http://localhost:6333.
# The Qdrant server itself is never installed locally — it always runs in Docker.
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# Name of the Qdrant collection that stores reel embeddings.
# A collection in Qdrant is like a table in a relational database —
# one collection, one vector size, one distance metric.
COLLECTION_NAME = "reels"

# Dimension of the OpenAI text-embedding-3-small output vector.
# Every vector stored in the collection must have exactly this many dimensions.
# text-embedding-3-small → 1536 floats per embedding.
VECTOR_SIZE = 1536

# ── Clients ───────────────────────────────────────────────────────────────────

# Shared OpenAI client — used only for embeddings in this file.
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# QdrantClient connects to the Qdrant server over HTTP.
# url= accepts the full base URL; qdrant-client handles /collections,
# /points, etc. routing internally.
qdrant = QdrantClient(url=QDRANT_URL)

# ── Collection bootstrap ──────────────────────────────────────────────────────

# Create the "reels" collection the first time this module is imported,
# but only if it doesn't already exist — so re-importing never wipes data.
#
# VectorParams tells Qdrant the shape of every vector it will store:
#   size=VECTOR_SIZE  → each vector has 1536 dimensions
#   distance=COSINE   → similarity is measured by cosine similarity
#                        (angle between vectors, ignores magnitude).
#                        Best choice for text embeddings from OpenAI.
if not qdrant.collection_exists(COLLECTION_NAME):
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


# ── Functions ─────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Convert a string into a 1536-dimension embedding vector using OpenAI.

    The embedding captures the *meaning* of the text as a point in
    high-dimensional space. Texts with similar meaning land close together,
    which is what makes semantic search possible.

    Model: text-embedding-3-small
      - 1536 dimensions
      - Fast and cheap vs text-embedding-3-large
      - Strong enough for topic-level similarity across reel transcripts

    Args:
        text: Any string — a transcript, a question, a summary.

    Returns:
        A list of 1536 floats representing the text's position in
        embedding space.
    """
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    # response.data is a list; [0] is the first (and only) embedding result.
    # .embedding is the list of floats.
    return response.data[0].embedding


def store_reel(text: str, metadata: dict) -> str:
    """Embed a reel transcript and store it in Qdrant with metadata.

    Each reel becomes one "point" in the Qdrant collection:
      - vector: the embedding of the transcript text
      - payload: structured metadata stored alongside the vector

    The payload is returned in search results, so callers get back
    the original text and metadata without needing a separate database.

    Args:
        text: The full transcript or summary text to embed and store.
        metadata: A dict with at least these keys:
                    topic      — e.g. "Technology"
                    subtopic   — e.g. "AI & Machine Learning"
                    source_url — the original reel URL
                    summary    — bullet-point summary saved to Notion

    Returns:
        The point ID (UUID string) assigned to this entry in Qdrant.
        Save this if you need to update or delete the point later.
    """
    # Generate a random UUID for this point.
    # Qdrant accepts UUID strings as point IDs (alongside plain integers).
    # UUIDs are collision-resistant across concurrent ingestion jobs.
    point_id = str(uuid.uuid4())

    # Embed the transcript text into a 1536-dim vector.
    vector = embed_text(text)

    # Build the payload — everything stored alongside the vector.
    # Include text itself so search results are self-contained
    # (no separate lookup needed to get the transcript back).
    payload = {
        "text": text,
        "topic": metadata.get("topic", ""),
        "subtopic": metadata.get("subtopic", ""),
        "source_url": metadata.get("source_url", ""),
        "summary": metadata.get("summary", ""),
    }

    # upsert = insert or update.
    # If a point with this ID already exists it gets overwritten,
    # otherwise it is inserted. Safe to call multiple times.
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        ],
    )

    return point_id


def search_reels(query: str, limit: int = 5) -> list[dict]:
    """Find reels semantically similar to a query string.

    Embeds the query, then asks Qdrant to return the `limit` closest
    vectors by cosine similarity. "Closest" means most similar in meaning,
    not exact keyword match — so "machine learning trends" finds reels
    about "AI developments" even if the words don't overlap.

    Args:
        query: A natural-language question or topic, e.g.
               "What did I learn about sleep and recovery?"
        limit: Maximum number of results to return. Default 5.

    Returns:
        A list of dicts, each containing:
            text       — the original transcript/summary text
            topic      — topic assigned during ingest
            subtopic   — subtopic assigned during ingest
            source_url — the original reel URL
            summary    — bullet-point summary
            score      — cosine similarity score (0–1, higher = more similar)
    """
    # Embed the query using the same model used at ingest time.
    # Mismatched models produce incompatible vector spaces and garbage results.
    query_vector = embed_text(query)

    # query_points searches the collection and returns the `limit` nearest
    # neighbours to query_vector, sorted by descending similarity score.
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    )

    # Flatten each ScoredPoint into a plain dict for easy consumption
    # by the caller (agent.py, LangGraph nodes, etc.).
    hits = []
    for point in results.points:
        payload = point.payload or {}
        hits.append(
            {
                "text": payload.get("text", ""),
                "topic": payload.get("topic", ""),
                "subtopic": payload.get("subtopic", ""),
                "source_url": payload.get("source_url", ""),
                "summary": payload.get("summary", ""),
                "score": point.score,
            }
        )

    return hits
