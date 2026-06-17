"""Agent orchestration loop: MCP tool use + CoT + Reflexion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.llm_client import LLMClient
from agent.mcp_client import MCPClient
from agent.scenario import Scenario, get_scenario

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"

MAX_TURNS = 20
MAX_REFLEXION_ROUNDS = 3

TOOL_PHASES: dict[str, str] = {
    "read_logs": "ASSESS",
    "git_recent_changes": "ASSESS",
    "query_runbook": "INVESTIGATE",
    "read_source": "INVESTIGATE",
    "apply_patch": "REMEDIATE",
    "run_tests": "VERIFY",
}


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def compact_tool_result(tool_name: str, result: str, max_chars: int = 4000) -> str:
    """Summarize long tool output to reduce context rot (course: compaction)."""
    if len(result) <= max_chars:
        return result
    return result[:max_chars] + f"\n... [truncated, {len(result) - max_chars} chars omitted]"


def parse_tool_result(result: str) -> dict[str, Any]:
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"raw": result}


class IncidentOrchestrator:
    def __init__(self, mcp: MCPClient, llm: LLMClient, scenario: Scenario | None = None) -> None:
        self.mcp = mcp
        self.llm = llm
        self.scenario = scenario or get_scenario()
        self.messages: list[dict[str, Any]] = []
        self.reflexion_count = 0
        self.tool_call_log: list[dict[str, Any]] = []
        self.phases_seen: list[str] = []

    def _build_initial_messages(self, user_alert: str) -> None:
        system_prompt = load_prompt("system_prompt.md")
        scenario_ctx = (
            f"\n\n## Active Scenario\n"
            f"- name: `{self.scenario.name}`\n"
            f"- description: {self.scenario.description}\n"
            f"- primary source: `{self.scenario.primary_source}`\n"
            f"- default log: `{self.scenario.default_log}`\n"
            f"- test path: `{self.scenario.test_path}`\n"
        )
        self.messages = [
            {"role": "system", "content": system_prompt + scenario_ctx},
            {"role": "user", "content": user_alert},
        ]

    async def _execute_tool_calls(
        self, tool_calls: list[dict[str, Any]], assistant_content: str | None = None
    ) -> list[dict[str, Any]]:
        """Execute tool calls via MCP and return OpenAI-style tool messages."""
        tool_messages: list[dict[str, Any]] = []

        assistant_tool_calls = []
        for call in tool_calls:
            assistant_tool_calls.append(
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    },
                }
            )

        self.messages.append(
            {
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": assistant_tool_calls,
            }
        )

        pending_reflexion: dict[str, Any] | None = None

        for call in tool_calls:
            name = call["name"]
            args = call["arguments"]
            phase = TOOL_PHASES.get(name, "UNKNOWN")
            if phase not in self.phases_seen:
                self.phases_seen.append(phase)
            print(f"\n[PHASE:{phase}] [TOOL] {name}({json.dumps(args, ensure_ascii=False)})")

            result = await self.mcp.call_tool(name, args)
            compacted = compact_tool_result(name, result)
            print(f"[RESULT] {compacted[:500]}{'...' if len(compacted) > 500 else ''}")

            parsed_for_log = parse_tool_result(result) if name == "run_tests" else None
            self.tool_call_log.append(
                {
                    "tool": name,
                    "arguments": args,
                    "result_preview": compacted[:300],
                    "passed": parsed_for_log.get("passed") if parsed_for_log else None,
                }
            )

            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": compacted,
                }
            )

            if name == "run_tests":
                parsed = parse_tool_result(result)
                if not parsed.get("passed", False):
                    pending_reflexion = parsed

        self.messages.extend(tool_messages)

        if pending_reflexion is not None:
            await self._trigger_reflexion(pending_reflexion)

        return tool_messages

    async def _trigger_reflexion(self, test_result: dict[str, Any]) -> None:
        if self.reflexion_count >= MAX_REFLEXION_ROUNDS:
            return

        self.reflexion_count += 1
        suffix_template = load_prompt("reflexion_suffix.md")
        observation = json.dumps(test_result, ensure_ascii=False, indent=2)
        reflexion_prompt = suffix_template.format(observation=observation)

        print(f"\n[REFLEXION] Round {self.reflexion_count} — tests failed, reflecting...")
        self.messages.append({"role": "user", "content": reflexion_prompt})

    async def run(self, user_alert: str) -> dict[str, Any]:
        self._build_initial_messages(user_alert)
        tools = self.mcp.tools
        final_content = ""

        for turn in range(1, MAX_TURNS + 1):
            print(f"\n{'=' * 60}\n[TURN {turn}] Calling LLM...\n{'=' * 60}")

            response = self.llm.chat(self.messages, tools=tools)

            if response.get("content"):
                print(f"\n[ASSISTANT]\n{response['content']}")

            if response["tool_calls"]:
                await self._execute_tool_calls(
                    response["tool_calls"], assistant_content=response.get("content")
                )
                if self._incident_resolved():
                    print("\n[DONE] Tests passed — generating incident report...")
                    self.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Tests have passed. Produce the final incident report now "
                                "(root cause, evidence, fix applied, verification)."
                            ),
                        }
                    )
                continue

            if response.get("content"):
                final_content = response["content"]
                self.messages.append({"role": "assistant", "content": final_content})

                if self._incident_resolved():
                    print("\n[DONE] Incident resolved — tests passed.")
                    break

                if turn < MAX_TURNS:
                    self.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Continue the incident response. "
                                "If you have not yet verified the fix, call run_tests. "
                                "If tests pass, produce the final incident report."
                            ),
                        }
                    )
                    continue
                break

        return {
            "final_report": final_content,
            "turns": turn,
            "reflexion_rounds": self.reflexion_count,
            "tool_calls": self.tool_call_log,
            "messages_count": len(self.messages),
            "phases": self.phases_seen,
        }

    def _incident_resolved(self) -> bool:
        for entry in reversed(self.tool_call_log):
            if entry["tool"] == "run_tests":
                if entry.get("passed") is not None:
                    return entry["passed"]
                parsed = parse_tool_result(entry.get("result_preview", "{}"))
                return parsed.get("passed", False)
        return False
