"""MCP client wrapper: connects to the SRE tools MCP server via stdio."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "sre_tools.py"


def mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    """Convert MCP tool schema to OpenAI function calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


class MCPClient:
    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self._tools: list[dict[str, Any]] = []

    async def initialize(self) -> list[dict[str, Any]]:
        await self.session.initialize()
        response = await self.session.list_tools()
        self._tools = [mcp_tool_to_openai(t) for t in response.tools]
        return self._tools

    @property
    def tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self.session.call_tool(name, arguments)
        parts: list[str] = []
        for block in result.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts) if parts else json.dumps({"result": "ok"})


@asynccontextmanager
async def connect_mcp(scenario: str = "indexerror") -> AsyncIterator[MCPClient]:
    import os

    env = {**os.environ, "SRE_SCENARIO": scenario}
    server_params = StdioServerParameters(
        command="python",
        args=[str(MCP_SERVER_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            client = MCPClient(session)
            await client.initialize()
            yield client
