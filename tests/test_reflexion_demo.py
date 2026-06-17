"""Tests for the controlled Reflexion evaluation setup."""

from dataclasses import replace

import pytest

from agent.scenario import get_scenario
from scripts.prepare_reflexion_demo import prepare_failed_hotfix


def test_prepare_failed_hotfix_replaces_initial_bug(tmp_path):
    scenario = replace(
        get_scenario("indexerror"),
        repo_dir=tmp_path,
    )

    source = tmp_path / "db_query.py"
    source.write_text(
        """
def get_active_users():
    users = ["Alice", "Bob"]
    return [
        users[i]
        for i in range(len(users) + 1)
    ]
""".lstrip(),
        encoding="utf-8",
    )

    result_path = prepare_failed_hotfix(scenario)
    content = result_path.read_text(encoding="utf-8")

    assert "range(len(users) - 1)" in content
    assert "range(len(users) + 1)" not in content


def test_prepare_failed_hotfix_requires_initial_state(tmp_path):
    scenario = replace(
        get_scenario("indexerror"),
        repo_dir=tmp_path,
    )

    source = tmp_path / "db_query.py"
    source.write_text(
        """
def get_active_users():
    users = ["Alice", "Bob"]
    return [
        users[i]
        for i in range(len(users))
    ]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Expected exactly one"):
        prepare_failed_hotfix(scenario)


def test_reflexion_demo_rejects_other_scenario(tmp_path):
    scenario = replace(
        get_scenario("keyerror"),
        repo_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="only the indexerror scenario"):
        prepare_failed_hotfix(scenario)
