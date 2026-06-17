"""Tests for trace redaction and verification summaries."""

from agent.trace_utils import (
    build_verification_summary,
    redact_data,
    redact_text,
    summarize_tool_result,
)


def test_redact_text_removes_api_key():
    original = (
        "OPENAI_API_KEY=sk-example-secret-value "
        "Authorization: Bearer abc.def.ghi"
    )

    redacted = redact_text(original)

    assert "example-secret-value" not in redacted
    assert "abc.def.ghi" not in redacted
    assert "REDACTED" in redacted


def test_redact_data_handles_nested_secrets():
    value = {
        "config": {
            "api_key": "private-value",
            "model": "example-model",
        }
    }

    redacted = redact_data(value)

    assert redacted["config"]["api_key"] == "***REDACTED***"
    assert redacted["config"]["model"] == "example-model"


def test_summarize_run_tests_result():
    summary = summarize_tool_result(
        "run_tests",
        (
            '{"passed": false, "exit_code": 1, '
            '"timed_out": false, '
            '"test_path": "tests/test_example.py", '
            '"stdout": "1 failed", "stderr": ""}'
        ),
    )

    assert summary["passed"] is False
    assert summary["exit_code"] == 1
    assert summary["stdout_excerpt"] == "1 failed"


def test_verification_summary_detects_recovery():
    calls = [
        {
            "sequence": 1,
            "turn": 2,
            "tool": "run_tests",
            "result_summary": {
                "passed": False,
                "exit_code": 1,
            },
        },
        {
            "sequence": 3,
            "turn": 4,
            "tool": "run_tests",
            "result_summary": {
                "passed": True,
                "exit_code": 0,
            },
        },
    ]

    summary = build_verification_summary(calls)

    assert summary["attempt_count"] == 2
    assert summary["first_passed"] is False
    assert summary["final_passed"] is True
    assert summary["failure_then_recovery"] is True
