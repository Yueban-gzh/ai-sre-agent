"""Print a concise, screenshot-friendly Agent trace summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--path",
        type=Path,
        help="Specific trace JSON path",
    )
    parser.add_argument(
        "--scenario",
        default="indexerror",
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "reflexion_demo"],
        default="reflexion_demo",
    )

    return parser.parse_args()


def find_latest_trace(scenario: str, mode: str) -> Path:
    if mode == "reflexion_demo":
        pattern = f"trace_{scenario}_reflexion_demo_*.json"
    else:
        pattern = f"trace_{scenario}_*.json"

    candidates = sorted(
        RUNS_DIR.glob(pattern),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise FileNotFoundError(f"No trace found for pattern: {pattern}")

    return candidates[0]


def outcome_for_call(call: dict[str, Any]) -> str:
    tool = call.get("tool", "unknown")
    summary = call.get("result_summary", {})

    if tool == "run_tests":
        passed = summary.get("passed")
        exit_code = summary.get("exit_code")

        if passed is True:
            return f"PASS (exit={exit_code})"
        if summary.get("timed_out"):
            return "TIMEOUT"
        return f"FAIL (exit={exit_code})"

    if tool == "apply_patch":
        return (
            f"{str(summary.get('status')).upper()} "
            f"{summary.get('file', '')}"
        ).strip()

    return str(
        summary.get("status", call.get("status", "completed"))
    ).upper()


def main() -> None:
    args = parse_args()

    trace_path = (
        args.path if args.path else find_latest_trace(args.scenario, args.mode)
    )

    data = json.loads(trace_path.read_text(encoding="utf-8"))

    print("=" * 78)
    print("AI SRE AGENT - AUDIT TRACE SUMMARY")
    print("=" * 78)
    print(f"Trace:       {trace_path.name}")
    print(f"Scenario:    {data.get('scenario')}")
    print(f"Run mode:    {data.get('run_mode')}")
    print(f"Model:       {data.get('model')}")
    print(f"Turns:       {data.get('turns')}")
    print(f"Reflexion:   {data.get('reflexion_rounds')} round(s)")
    print(f"Tool calls:  {data.get('tool_call_count')}")
    print()

    print("SEQ | TURN | PHASE        | TOOL                 | RESULT")
    print("-" * 78)

    for call in data.get("tool_calls", []):
        print(
            f"{call.get('sequence', 0):>3} | "
            f"{call.get('turn', 0):>4} | "
            f"{str(call.get('phase', 'UNKNOWN')):<12} | "
            f"{str(call.get('tool', 'unknown')):<20} | "
            f"{outcome_for_call(call)}"
        )

    verification = data.get("verification", {})

    print()
    print("VERIFICATION")
    print("-" * 78)
    print(f"Attempts:              {verification.get('attempt_count')}")
    print(f"First attempt passed:  {verification.get('first_passed')}")
    print(f"Final attempt passed:  {verification.get('final_passed')}")
    print(f"Failure then recovery: {verification.get('failure_then_recovery')}")

    patch_calls = [
        call for call in data.get("tool_calls", []) if call.get("tool") == "apply_patch"
    ]

    for index, call in enumerate(patch_calls, start=1):
        diff = call.get("result_summary", {}).get("diff", "")

        if diff:
            print()
            print(f"PATCH DIFF #{index}")
            print("-" * 78)
            print(diff)

    print()
    print("=" * 78)
    print(
        "AUDIT RESULT: "
        + (
            "RECOVERY VERIFIED"
            if verification.get("failure_then_recovery")
            else "RECOVERY NOT VERIFIED"
        )
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
