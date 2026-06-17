"""Incident scenario registry — supports multiple demo incidents."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Scenario:
    name: str
    display_name: str
    alert_file: Path
    logs_dir: Path
    default_log: str
    git_fixture: Path
    repo_dir: Path
    test_path: str
    primary_source: str
    description: str

    @property
    def allowed_test_paths(self) -> set[str]:
        tests_dir = self.repo_dir / "tests"
        return {self.test_path, str(tests_dir.relative_to(PROJECT_ROOT)).replace("\\", "/")}


SCENARIOS: dict[str, Scenario] = {
    "indexerror": Scenario(
        name="indexerror",
        display_name="IndexError — off-by-one loop",
        alert_file=PROJECT_ROOT / "prompts" / "scenarios" / "indexerror_alert.md",
        logs_dir=PROJECT_ROOT / "fixtures" / "logs",
        default_log="app_error.log",
        git_fixture=PROJECT_ROOT / "fixtures" / "git" / "recent_changes.json",
        repo_dir=PROJECT_ROOT / "fixtures" / "repo",
        test_path="fixtures/repo/tests/test_db_query.py",
        primary_source="db_query.py",
        description="HTTP 500 after loop refactor — IndexError in db_query.py",
    ),
    "keyerror": Scenario(
        name="keyerror",
        display_name="KeyError — dict key type mismatch",
        alert_file=PROJECT_ROOT / "prompts" / "scenarios" / "keyerror_alert.md",
        logs_dir=PROJECT_ROOT / "fixtures" / "scenarios" / "keyerror" / "logs",
        default_log="cache_error.log",
        git_fixture=PROJECT_ROOT / "fixtures" / "scenarios" / "keyerror" / "git" / "recent_changes.json",
        repo_dir=PROJECT_ROOT / "fixtures" / "scenarios" / "keyerror" / "repo",
        test_path="fixtures/scenarios/keyerror/repo/tests/test_user_cache.py",
        primary_source="user_cache.py",
        description="HTTP 500 on profile tier lookup — KeyError after key migration",
    ),
}

RUNBOOKS_DIR = PROJECT_ROOT / "fixtures" / "runbooks"


def get_scenario(name: str | None = None) -> Scenario:
    key = (name or os.environ.get("SRE_SCENARIO", "indexerror")).lower().strip()
    if key not in SCENARIOS:
        available = ", ".join(SCENARIOS)
        raise ValueError(f"Unknown scenario '{key}'. Available: {available}")
    return SCENARIOS[key]


def list_scenario_names() -> list[str]:
    return list(SCENARIOS.keys())
