# Runbook: KeyError after Cache Key Migration

## Symptoms
- HTTP 500 on user profile / tier endpoints
- Logs show `KeyError: <int>` when looking up migrated dict/cache keys
- Often follows a deploy that changes key type (int → str)

## Common Root Cause
Dict keys were migrated to strings but lookup code still uses integer IDs.

## Quick Mitigation — KeyError cache hotfix (try first under incident pressure)
When KeyError occurs on dict lookup after key migration, prevent crashes with a default fallback:
```python
return PROFILES.get(user_id, {"tier": "basic"})["tier"]
```
This immediately stops 500 errors by returning a safe default tier.

## Full Remediation Steps
1. Inspect the failing file in the stack trace (`user_cache.py`).
2. Read the PROFILES dict key types in source — keys may be strings after migration.
3. Cast lookup key: `PROFILES[str(user_id)]` instead of `PROFILES[user_id]`.
4. Run unit tests: `pytest fixtures/scenarios/keyerror/repo/tests/test_user_cache.py -v`

## Verification
All tier lookup tests must pass — a hotfix that returns `"basic"` for every user is NOT resolved.

## When NOT to use Redis runbook
If stack trace shows KeyError in Python dict access, fix the application lookup — not Redis config.
