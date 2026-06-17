"""
AI SRE Incident Diagnosis Agent — Experiment 2 (BYOA)

Entry point: connects MCP tools to LLM orchestration loop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agent.llm_client import LLMClient  # noqa: E402
from agent.mcp_client import connect_mcp  # noqa: E402
from agent.orchestrator import IncidentOrchestrator  # noqa: E402
from agent.scenario import SCENARIOS, get_scenario  # noqa: E402
from agent.trace_utils import (  # noqa: E402
    build_verification_summary,
    redact_data,
    utc_now_iso,
)
from scripts.prepare_reflexion_demo import prepare_failed_hotfix  # noqa: E402
from scripts.reset_demo import reset_scenario  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI SRE Incident Diagnosis Agent")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default=os.environ.get("SRE_SCENARIO", "indexerror"),
        help="Incident scenario to run (default: indexerror)",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit",
    )
    parser.add_argument(
        "--reflexion-demo",
        action="store_true",
        help=(
            "Run a controlled failed-hotfix scenario to demonstrate "
            "test failure, Reflexion, revised remediation, and recovery"
        ),
    )
    return parser.parse_args()


def export_trace(
    result: dict,
    llm_model: str,
    scenario_name: str,
    run_mode: str = "standard",
) -> Path:
    runs_dir = PROJECT_ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_label = (
        f"{scenario_name}_reflexion_demo"
        if run_mode == "reflexion_demo"
        else scenario_name
    )
    trace_path = runs_dir / f"trace_{trace_label}_{timestamp}.json"

    verification = build_verification_summary(result["tool_calls"])

    payload = {
        "trace_version": 2,
        "created_at": utc_now_iso(),
        "timestamp": timestamp,
        "scenario": scenario_name,
        "run_mode": run_mode,
        "model": llm_model,
        "success": verification["final_passed"] is True,
        "turns": result["turns"],
        "reflexion_rounds": result["reflexion_rounds"],
        "tool_call_count": len(result["tool_calls"]),
        "tool_calls": redact_data(result["tool_calls"]),
        "tools_used": sorted({call["tool"] for call in result["tool_calls"]}),
        "phases": result.get("phases", []),
        "verification": verification,
        "final_report_preview": redact_data(
            (result.get("final_report") or "")[:1200]
        ),
    }
    trace_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return trace_path


async def run_agent(
    scenario_name: str,
    reflexion_demo: bool = False,
) -> None:
    os.environ["SRE_SCENARIO"] = scenario_name
    scenario = reset_scenario(scenario_name)

    user_alert = scenario.alert_file.read_text(encoding="utf-8")

    if reflexion_demo:
        if scenario_name != "indexerror":
            raise ValueError(
                "--reflexion-demo currently supports only --scenario indexerror"
            )

        prepare_failed_hotfix(scenario)

        demo_prompt_path = (
            PROJECT_ROOT / "prompts" / "scenarios" / "indexerror_reflexion_demo.md"
        )
        demo_context = demo_prompt_path.read_text(encoding="utf-8")
        user_alert = f"{user_alert}\n\n{demo_context}"

    print("=" * 60)
    print("AI SRE Incident Diagnosis Agent")
    print(f"Scenario: {scenario.display_name} ({scenario.name})")
    print(
        "Mode: "
        + ("CONTROLLED REFLEXION EVALUATION" if reflexion_demo else "STANDARD")
    )
    print("=" * 60)
    print("\n[INCIDENT ALERT]")
    print(user_alert)

    llm = LLMClient()

    async with connect_mcp(scenario_name) as mcp:
        tools = [t["function"]["name"] for t in mcp.tools]
        print(f"\n[MCP] Connected. Tools: {tools}")

        orchestrator = IncidentOrchestrator(mcp, llm, scenario=scenario)
        result = await orchestrator.run(user_alert)

        run_mode = "reflexion_demo" if reflexion_demo else "standard"

        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(
            json.dumps(
                {
                    "scenario": scenario_name,
                    "run_mode": run_mode,
                    "turns": result["turns"],
                    "reflexion_rounds": result["reflexion_rounds"],
                    "tool_call_count": len(result["tool_calls"]),
                    "tools_used": list({c["tool"] for c in result["tool_calls"]}),
                    "phases": result.get("phases", []),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        if result["final_report"]:
            print("\n[FINAL INCIDENT REPORT]")
            print(result["final_report"])

        trace_path = export_trace(
            result,
            llm.model,
            scenario_name,
            run_mode=run_mode,
        )
        print(f"\n[TRACE] Saved: {trace_path}")


async def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()

    if args.list_scenarios:
        for name, sc in SCENARIOS.items():
            print(f"  {name:12} — {sc.display_name}")
            print(f"               {sc.description}")
        return

    if args.reflexion_demo and args.scenario != "indexerror":
        raise SystemExit(
            "--reflexion-demo currently supports only --scenario indexerror"
        )

    await run_agent(
        args.scenario,
        reflexion_demo=args.reflexion_demo,
    )


if __name__ == "__main__":
    asyncio.run(main())
