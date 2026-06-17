"""Tests for safe patching and structured test failures."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace

from agent.scenario import get_scenario
from mcp_server import sre_tools


def temporary_scenario(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    return replace(
        get_scenario("indexerror"),
        repo_dir=repo_dir,
    )


def test_apply_patch_returns_diff_and_writes_atomically(monkeypatch, tmp_path):
    scenario = temporary_scenario(tmp_path)
    source = scenario.repo_dir / "sample.py"
    source.write_text("def value():\n    return 1\n", encoding="utf-8")

    monkeypatch.setattr(sre_tools, "active_scenario", lambda: scenario)

    payload = json.loads(
        sre_tools.apply_patch(
            "sample.py",
            "return 1",
            "return 2",
        )
    )

    assert payload["status"] == "patched"
    assert "-    return 1" in payload["diff"]
    assert "+    return 2" in payload["diff"]
    assert source.read_text(encoding="utf-8") == "def value():\n    return 2\n"
    assert not (scenario.repo_dir / ".sample.py.tmp").exists()


def test_apply_patch_rejects_invalid_python_without_modifying_file(monkeypatch, tmp_path):
    scenario = temporary_scenario(tmp_path)
    source = scenario.repo_dir / "sample.py"
    original = "def value():\n    return 1\n"
    source.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sre_tools, "active_scenario", lambda: scenario)

    payload = json.loads(
        sre_tools.apply_patch(
            "sample.py",
            "return 1",
            "return (",
        )
    )

    assert payload["status"] == "rejected"
    assert payload["error"] == "Patch introduces invalid Python syntax"
    assert source.read_text(encoding="utf-8") == original


def test_apply_patch_rejects_ambiguous_search(monkeypatch, tmp_path):
    scenario = temporary_scenario(tmp_path)
    source = scenario.repo_dir / "sample.py"
    original = "value = 1\nvalue = 1\n"
    source.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sre_tools, "active_scenario", lambda: scenario)

    payload = json.loads(
        sre_tools.apply_patch(
            "sample.py",
            "value = 1",
            "value = 2",
        )
    )

    assert payload["status"] == "rejected"
    assert payload["match_count"] == 2
    assert source.read_text(encoding="utf-8") == original


def test_run_tests_timeout_is_structured(monkeypatch):
    scenario = get_scenario("indexerror")

    monkeypatch.setattr(sre_tools, "active_scenario", lambda: scenario)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=60,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(sre_tools.subprocess, "run", raise_timeout)

    payload = json.loads(sre_tools.run_tests(scenario.test_path))

    assert payload["passed"] is False
    assert payload["timed_out"] is True
    assert payload["error_type"] == "TimeoutExpired"
    assert payload["stdout"] == "partial stdout"
