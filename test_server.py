import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            print()

            # Call download_reel
            url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            print(f"Calling download_reel with URL: {url}")
            result = await session.call_tool("download_reel", {"url": url})
            print(f"Result: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
