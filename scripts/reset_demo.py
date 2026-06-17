"""Reset scenario fixtures to initial buggy state."""

from __future__ import annotations

from agent.scenario import PROJECT_ROOT, Scenario, get_scenario

BUGGY_SOURCES: dict[str, dict[str, str]] = {
    "indexerror": {
        "db_query.py": '''"""Simulated database query module with an intentional off-by-one bug."""

USERS = [
    {"id": 1, "name": "Alice", "active": True},
    {"id": 2, "name": "Bob", "active": True},
    {"id": 3, "name": "Carol", "active": False},
]


def get_active_users():
    users = [u for u in USERS if u["active"]]
    # BUG: off-by-one — introduced in recent refactor
    return [users[i] for i in range(len(users) + 1)]
''',
    },
    "keyerror": {
        "user_cache.py": '''"""Simulated user profile cache with intentional key-type mismatch bug."""

PROFILES = {
    "1": {"name": "Alice", "tier": "pro"},
    "2": {"name": "Bob", "tier": "basic"},
}


def get_user_tier(user_id: int) -> str:
    # BUG: keys migrated to str but lookup still uses int
    return PROFILES[user_id]["tier"]
''',
    },
}


def reset_scenario(scenario: Scenario | str | None = None) -> Scenario:
    sc = get_scenario(scenario if isinstance(scenario, str) else None)
    sources = BUGGY_SOURCES[sc.name]

    for rel_path, content in sources.items():
        target = sc.repo_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(PROJECT_ROOT)
        print(f"[RESET] [{sc.name}] Restored: {rel}")

    return sc


def reset_demo(scenario: str | None = None) -> None:
    reset_scenario(scenario)


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else None
    reset_scenario(name)
