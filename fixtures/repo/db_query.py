"""Simulated database query module with an intentional off-by-one bug."""

USERS = [
    {"id": 1, "name": "Alice", "active": True},
    {"id": 2, "name": "Bob", "active": True},
    {"id": 3, "name": "Carol", "active": False},
]


def get_active_users():
    users = [u for u in USERS if u["active"]]
    # BUG: off-by-one — introduced in recent refactor
    return [users[i] for i in range(len(users) + 1)]
