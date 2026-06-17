"""Simulated user profile cache with intentional key-type mismatch bug."""

PROFILES = {
    "1": {"name": "Alice", "tier": "pro"},
    "2": {"name": "Bob", "tier": "basic"},
}


def get_user_tier(user_id: int) -> str:
    # BUG: keys migrated to str but lookup still uses int
    return PROFILES[str(user_id)]["tier"]
