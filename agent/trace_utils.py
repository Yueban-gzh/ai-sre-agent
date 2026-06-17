"""Utilities for safe and auditable Agent traces."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

MAX_EXCERPT_CHARS = 2400


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def normalize_value(value: Any) -> Any:
    """Convert common SDK/Pydantic values into JSON-safe objects."""
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "text"):
        return value.text

    if isinstance(value, dict):
        return {str(key): normalize_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [normalize_value(item) for item in value]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def redact_text(text: str) -> str:
    """Remove common secret formats from trace text."""
    result = text

    result = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer ***REDACTED***",
        result,
    )

    result = re.sub(
        r"\bsk-[A-Za-z0-9_-]{8,}\b",
        "sk-***REDACTED***",
        result,
    )

    result = re.sub(
        (
            r"(?i)\b("
            r"api[_-]?key|authorization|access[_-]?token|"
            r"secret|password"
            r")\b"
            r"(\s*[=:]\s*)"
            r"([\"']?)[^,\s}\"']+"
        ),
        r"\1\2\3***REDACTED***",
        result,
    )

    return result


def redact_data(value: Any) -> Any:
    """Recursively redact secrets from trace-compatible data."""
    normalized = normalize_value(value)

    if isinstance(normalized, str):
        return redact_text(normalized)

    if isinstance(normalized, list):
        return [redact_data(item) for item in normalized]

    if isinstance(normalized, dict):
        redacted: dict[str, Any] = {}

        for key, item in normalized.items():
            lowered = key.lower()

            if any(
                token in lowered
                for token in (
                    "api_key",
                    "apikey",
                    "authorization",
                    "access_token",
                    "password",
                    "secret",
                )
            ):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_data(item)

        return redacted

    return normalized


def tool_output_text(raw_output: Any) -> str:
    """Convert an MCP/tool result into readable text."""
    normalized = normalize_value(raw_output)

    if isinstance(normalized, str):
        return normalized

    if isinstance(normalized, list):
        parts: list[str] = []

        for item in normalized:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))

        return "\n".join(parts)

    return json.dumps(normalized, ensure_ascii=False)


def parse_tool_output(raw_output: Any) -> Any:
    """Parse JSON tool output when possible."""
    text = tool_output_text(raw_output).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def truncate_text(text: str, limit: int = MAX_EXCERPT_CHARS) -> str:
    if len(text) <= limit:
        return text

    removed = len(text) - limit
    return text[:limit] + f"\n...[truncated {removed} characters]"


def summarize_tool_result(tool_name: str, raw_output: Any) -> dict[str, Any]:
    """Create a compact, tool-specific result summary."""
    parsed = redact_data(parse_tool_output(raw_output))

    if tool_name == "run_tests" and isinstance(parsed, dict):
        return {
            "passed": parsed.get("passed"),
            "exit_code": parsed.get("exit_code"),
            "timed_out": parsed.get("timed_out", False),
            "error_type": parsed.get("error_type"),
            "test_path": parsed.get("test_path"),
            "stdout_excerpt": truncate_text(str(parsed.get("stdout", ""))),
            "stderr_excerpt": truncate_text(str(parsed.get("stderr", ""))),
        }

    if tool_name == "apply_patch" and isinstance(parsed, dict):
        return {
            "status": parsed.get("status"),
            "file": parsed.get("file"),
            "error": parsed.get("error"),
            "match_count": parsed.get("match_count"),
            "diff": truncate_text(str(parsed.get("diff", ""))),
        }

    if tool_name == "query_runbook" and isinstance(parsed, dict):
        chunks = parsed.get("chunks", [])
        return {
            "query": parsed.get("query"),
            "top_result": chunks[:2],
        }

    if isinstance(parsed, dict):
        return {
            "status": parsed.get("status", "completed"),
            "excerpt": truncate_text(json.dumps(parsed, ensure_ascii=False)),
        }

    return {
        "status": "completed",
        "excerpt": truncate_text(str(parsed)),
    }


def build_verification_summary(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the run_tests sequence from a full trace."""
    test_calls = [call for call in tool_calls if call.get("tool") == "run_tests"]

    attempts: list[dict[str, Any]] = []

    for call in test_calls:
        summary = call.get("result_summary", {})

        attempts.append(
            {
                "sequence": call.get("sequence"),
                "turn": call.get("turn"),
                "passed": summary.get("passed"),
                "exit_code": summary.get("exit_code"),
                "timed_out": summary.get("timed_out", False),
            }
        )

    first_passed = attempts[0].get("passed") if attempts else None
    final_passed = attempts[-1].get("passed") if attempts else None

    return {
        "attempt_count": len(attempts),
        "first_passed": first_passed,
        "final_passed": final_passed,
        "failure_then_recovery": (
            len(attempts) >= 2 and first_passed is False and final_passed is True
        ),
        "attempts": attempts,
    }
