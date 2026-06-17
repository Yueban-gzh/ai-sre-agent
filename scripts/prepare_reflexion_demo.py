"""Prepare a controlled failed-hotfix state for Reflexion evaluation."""

from __future__ import annotations

from pathlib import Path

from agent.scenario import Scenario, get_scenario


def prepare_failed_hotfix(
    scenario: Scenario | str = "indexerror",
) -> Path:
    """
    Simulate a previously applied but semantically incorrect emergency hotfix.

    Initial bug:
        range(len(users) + 1)

    Failed emergency hotfix:
        range(len(users) - 1)

    The second version no longer raises IndexError, but silently drops
    the final active user, so the scenario tests must fail.
    """
    sc = scenario if isinstance(scenario, Scenario) else get_scenario(scenario)

    if sc.name != "indexerror":
        raise ValueError(
            "The controlled Reflexion demo currently supports "
            "only the indexerror scenario."
        )

    target = sc.repo_dir / sc.primary_source

    if not target.exists():
        raise FileNotFoundError(f"Scenario source does not exist: {target}")

    original = target.read_text(encoding="utf-8")

    search = "range(len(users) + 1)"
    replacement = "range(len(users) - 1)"
    match_count = original.count(search)

    if match_count != 1:
        raise RuntimeError(
            "Expected exactly one initial off-by-one expression "
            f"but found {match_count}. Run reset_scenario first."
        )

    updated = original.replace(search, replacement, 1)
    target.write_text(updated, encoding="utf-8")

    print(
        "[FAULT-INJECTION] Applied known-bad emergency hotfix: "
        "range(len(users) + 1) -> range(len(users) - 1)"
    )
    print(
        "[FAULT-INJECTION] Expected result: endpoint no longer "
        "raises IndexError, but tests fail because one user is omitted."
    )

    return target


if __name__ == "__main__":
    prepare_failed_hotfix("indexerror")
