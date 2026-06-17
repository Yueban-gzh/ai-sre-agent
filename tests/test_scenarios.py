"""Tests for multi-scenario configuration."""

from dataclasses import replace

from agent.scenario import SCENARIOS, get_scenario
from scripts.reset_demo import reset_scenario


def test_both_scenarios_registered():
    assert "indexerror" in SCENARIOS
    assert "keyerror" in SCENARIOS


def test_indexerror_paths():
    sc = get_scenario("indexerror")
    assert sc.primary_source == "db_query.py"
    assert sc.test_path.endswith("test_db_query.py")


def test_keyerror_paths():
    sc = get_scenario("keyerror")
    assert sc.primary_source == "user_cache.py"
    assert sc.test_path.endswith("test_user_cache.py")


def test_reset_indexerror_writes_buggy_code(tmp_path):
    sc = replace(
        get_scenario("indexerror"),
        repo_dir=tmp_path / "indexerror_repo",
    )

    reset_scenario(sc)

    content = (sc.repo_dir / "db_query.py").read_text(encoding="utf-8")
    assert "range(len(users) + 1)" in content


def test_reset_keyerror_writes_buggy_code(tmp_path):
    sc = replace(
        get_scenario("keyerror"),
        repo_dir=tmp_path / "keyerror_repo",
    )

    reset_scenario(sc)

    content = (sc.repo_dir / "user_cache.py").read_text(encoding="utf-8")
    assert "PROFILES[user_id]" in content
