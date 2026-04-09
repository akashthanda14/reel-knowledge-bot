"""
MCP client + OpenAI agentic loop.
Given a reel URL, runs the full pipeline:
  download → transcribe → extract concepts → save to Notion
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

load_dotenv()

# OpenAI client used for reasoning + tool orchestration.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are a knowledge extraction agent.
Given a reel URL you must:
1. Call download_reel to download the audio.
2. Call transcribe_audio with the returned file path.
3. Call get_existing_topics to see what topics already exist in Notion.
4. Analyse the transcript: extract 3–7 key concepts, determine the best topic and subtopic
   (reuse an existing topic/subtopic when it fits, otherwise create a new one).
5. Call save_to_notion with topic, subtopic, and a clean structured summary of the key concepts.
6. Reply with a short confirmation: topic, subtopic, and bullet-point key concepts.

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
    """Connect to the MCP server and run the full pipeline for a reel URL."""
    # This launches the local MCP tool server over stdio.
    # The server process is started on demand (not a permanently running API service).
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
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
            # Guardrails so the model cannot finish without attempting persistence.
            saved_to_notion = False
            last_save_result = ""

            # Agentic loop
            while True:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )

                msg = response.choices[0].message
                messages.append(msg)

                # No more tool calls — we have the final answer
                if not msg.tool_calls:
                    # Force at least one save attempt before allowing completion.
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

                    # Return a clear status if the save step itself failed.
                    if last_save_result.startswith("Error"):
                        return f"Processing completed, but Notion save failed: {last_save_result}"

                    return msg.content

                # Execute each tool call via MCP
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    print(f"[agent] calling {name}({args})")
                    result = await session.call_tool(name, args)
                    output = result.content[0].text

                    if name == "save_to_notion":
                        saved_to_notion = True
                        last_save_result = output

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": output,
                        }
                    )


async def main():
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else input("Reel URL: ").strip()
    print(f"\nProcessing: {url}\n")
    result = await process_url(url)
    print("\n--- Result ---")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
