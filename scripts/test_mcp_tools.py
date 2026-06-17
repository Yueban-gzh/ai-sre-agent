"""Offline test: verify MCP tools for a given scenario."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.mcp_client import connect_mcp  # noqa: E402
from agent.scenario import get_scenario  # noqa: E402
from scripts.reset_demo import reset_scenario  # noqa: E402


async def main() -> None:
    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "indexerror"
    os.environ["SRE_SCENARIO"] = scenario_name
    sc = reset_scenario(scenario_name)

    async with connect_mcp(scenario_name) as mcp:
        print(f"Scenario: {sc.name}")
        print("Tools:", [t["function"]["name"] for t in mcp.tools])

        info = await mcp.call_tool("list_scenario_info", {})
        print("\n[list_scenario_info]", info[:200])

        logs = await mcp.call_tool(
            "read_logs", {"file_name": sc.default_log, "filter_keyword": "ERROR"}
        )
        print("\n[read_logs]", logs[:180])

        runbook = await mcp.call_tool("query_runbook", {"keyword": sc.name, "top_k": 2})
        print("\n[query_runbook]", runbook[:200])

        tests_before = await mcp.call_tool("run_tests", {"test_path": sc.test_path})
        print("\n[run_tests BEFORE]", json.loads(tests_before)["passed"])

    print("\n[OK] MCP tools working for scenario:", scenario_name)


if __name__ == "__main__":
    asyncio.run(main())
