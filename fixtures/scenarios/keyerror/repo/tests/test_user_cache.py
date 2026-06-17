from user_cache import get_user_tier


def test_alice_tier_is_pro():
    assert get_user_tier(1) == "pro"


def test_bob_tier_is_basic():
    assert get_user_tier(2) == "basic"


def test_no_keyerror_on_valid_users():
    """Hotfix returning default for all users must not mask wrong tiers."""
    assert get_user_tier(1) != get_user_tier(2)
