from db_query import get_active_users


def test_get_active_users_count():
    users = get_active_users()
    assert len(users) == 2


def test_get_active_users_names():
    users = get_active_users()
    names = {u["name"] for u in users}
    assert names == {"Alice", "Bob"}


def test_active_users_order():
    """Both active users must be returned — partial lists fail here."""
    users = get_active_users()
    assert [u["name"] for u in users] == ["Alice", "Bob"]
