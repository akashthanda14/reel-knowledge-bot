"""
Smoke test for server.py — verifies all 6 MCP tools are registered and reachable.

Run this locally (outside Docker) to confirm the MCP server starts correctly:
    python test_server.py

What it checks:
  1. MCP server starts without errors
  2. All 6 expected tools are registered
  3. download_reel works on a real public URL (optional — comment out if offline)

It does NOT test Notion or Qdrant — those require live credentials and running containers.
"""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "download_reel",
    "transcribe_audio",
    "get_existing_topics",
    "save_to_notion",
    "embed_and_store",
    "get_similar_reels",
}


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 1. Verify all tools are registered ───────────────────────────
            tools = await session.list_tools()
            registered = {t.name for t in tools.tools}

            print("Registered tools:")
            for name in sorted(registered):
                status = "OK" if name in EXPECTED_TOOLS else "UNEXPECTED"
                print(f"  [{status}] {name}")

            missing = EXPECTED_TOOLS - registered
            if missing:
                print(f"\nMISSING tools: {missing}")
            else:
                print(f"\nAll {len(EXPECTED_TOOLS)} expected tools are registered.")

            # ── 2. Call download_reel with a short public video ───────────────
            # Comment this block out if you don't want a real network call.
            test_url = "https://www.youtube.com/shorts/MhIGCMiNDEY"
            print(f"\nCalling download_reel({test_url!r}) ...")
            result = await session.call_tool("download_reel", {"url": test_url})
            output = result.content[0].text
            print(f"Result: {output}")

            if output.startswith("Error"):
                print("download_reel FAILED — check yt-dlp and ffmpeg are installed.")
            else:
                print("download_reel OK — audio saved to", output)


if __name__ == "__main__":
    asyncio.run(main())
