"""
MCP client + OpenAI agentic loop + Redis worker.

Architecture:
  Redis queue (jobs:pending) → worker() → process_url() → Redis result (result:{job_id})

process_url() is unchanged — it still runs the full MCP pipeline:
  download → transcribe → extract concepts → save to Notion

The worker loop wraps it: pop a job from Redis, run the pipeline, push the result back.
"""

import asyncio
import json
import os

import redis.asyncio as aioredis
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

load_dotenv()

# OpenAI client used for reasoning + tool orchestration.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

# Redis connection string. "redis" resolves to the Redis container hostname
# inside Docker Compose's internal network.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# The list key agent.py reads from. Must match the key bot.py writes to.
JOB_QUEUE = "jobs:pending"

# How long (seconds) to keep a result key in Redis before auto-deleting it.
# Prevents orphaned keys from accumulating if the bot crashes before reading.
RESULT_TTL = 600

SYSTEM_PROMPT = """You are a knowledge extraction agent.
Given a reel URL you must follow these steps in order:
1. Call download_reel to download the audio.
2. Call transcribe_audio with the returned file path.
3. Call get_existing_topics to see what topics already exist in Notion.
4. Analyse the transcript: extract 3-7 key concepts, determine the best topic and subtopic
   (reuse an existing topic/subtopic when it fits, otherwise create a new one).
5. Call save_to_notion with topic, subtopic, and a clean structured summary of the key concepts.
6. Call embed_and_store with:
   - text: the full transcript
   - topic: same topic you used in save_to_notion
   - subtopic: same subtopic
   - source_url: the original reel URL the user sent
   - summary: the same bullet-point summary you saved to Notion
   This stores the knowledge in the vector search database for future retrieval.
7. Reply with a short confirmation: topic, subtopic, and bullet-point key concepts.

Format the content you pass to save_to_notion as plain text bullet points."""


def _mcp_tools_to_openai(tools) -> list[dict]:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
        )
    return openai_tools


async def process_url(url: str) -> str:
    """Connect to the MCP server and run the full pipeline for a reel URL.
    This function is unchanged from the single-container version.
    It is called by the worker loop below."""
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = (await session.list_tools()).tools
            openai_tools = _mcp_tools_to_openai(mcp_tools)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Process this reel: {url}"},
            ]
            saved_to_notion = False
            embedded_in_qdrant = False
            last_save_result = ""

            while True:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )

                msg = response.choices[0].message
                messages.append(msg)

                if not msg.tool_calls:
                    # Hard-enforce save_to_notion — no final answer without it.
                    if not saved_to_notion:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "You must call save_to_notion before your final response. "
                                    "Call save_to_notion now with the best topic, subtopic, and "
                                    "plain-text bullet summary, then confirm to the user."
                                ),
                            }
                        )
                        continue

                    # Soft-enforce embed_and_store — nudge once, don't block on failure.
                    if not embedded_in_qdrant:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "You still need to call embed_and_store to save this reel "
                                    "to the vector search database. Call it now with the full "
                                    "transcript, topic, subtopic, source_url, and summary."
                                ),
                            }
                        )
                        continue

                    if last_save_result.startswith("Error"):
                        return f"Processing completed, but Notion save failed: {last_save_result}"

                    return msg.content

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    print(f"[agent] calling {name}({args})")
                    result = await session.call_tool(name, args)
                    output = result.content[0].text

                    if name == "save_to_notion":
                        saved_to_notion = True
                        last_save_result = output

                    if name == "embed_and_store":
                        embedded_in_qdrant = True

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": output,
                        }
                    )


async def worker() -> None:
    """Redis worker loop.

    Connects to Redis, then blocks waiting for jobs on JOB_QUEUE.
    For each job it calls process_url() and pushes the result back to Redis
    so bot.py can read it and reply to the Telegram user.

    This loop runs forever — Docker Compose restarts it if it crashes.
    """
    # Create one Redis connection for the lifetime of the worker process.
    r = aioredis.from_url(REDIS_URL)
    print(f"[worker] Connected to Redis at {REDIS_URL}")
    print(f"[worker] Listening for jobs on '{JOB_QUEUE}' ...")

    try:
        while True:
            # BLPOP blocks until a value appears at JOB_QUEUE (or forever if
            # timeout=0). It returns a (key, value) tuple when a job arrives.
            # This is efficient — the worker sleeps at the OS level instead of
            # polling, so it uses near-zero CPU while idle.
            raw = await r.blpop(JOB_QUEUE, timeout=0)

            # Decode the JSON payload that bot.py pushed.
            job = json.loads(raw[1])
            url = job["url"]
            job_id = job["job_id"]

            print(f"[worker] job={job_id[:8]}... url={url}")

            # Run the full pipeline and catch any exception so a bad URL
            # or transient API failure doesn't crash the worker — it just
            # sends an error message back to the user.
            try:
                text = await process_url(url)
                payload = json.dumps({"text": text})
            except Exception as e:
                payload = json.dumps({"text": f"Processing failed: {e}"})

            # Push the result to a per-job key. bot.py is blocking on this key.
            # RPUSH + EXPIRE are two separate commands, not atomic, but that's
            # fine here — the worst case is a result key that never expires,
            # which won't cause correctness issues.
            result_key = f"result:{job_id}"
            await r.rpush(result_key, payload)

            # Set a TTL so the key is automatically deleted if the bot never
            # reads it (e.g., bot crashed between pushing the job and reading
            # the result). Without this, orphaned keys accumulate forever.
            await r.expire(result_key, RESULT_TTL)

            print(f"[worker] job={job_id[:8]}... done")

    finally:
        # Runs on KeyboardInterrupt or unhandled exception — close cleanly.
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(worker())
