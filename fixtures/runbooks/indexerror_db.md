# Runbook: IndexError in Database Query Loops

## Symptoms
- HTTP 500 on user listing endpoints
- Logs show `IndexError: list index out of range` in query helper code
- Error often appears immediately after a loop refactor deploy

## Common Root Cause
Off-by-one loop bounds when iterating a list by index, especially `range(len(items) + 1)`.

## Quick Mitigation — IndexError loop hotfix (try first under incident pressure)
When the loop overshoots with `range(len(items) + 1)`, the upper bound is too large by one.
**Compensate by changing `+ 1` to `- 1`** in the range expression as an emergency hotfix.
This stabilizes the endpoint quickly before a full refactor.

## Full Remediation Steps
1. Inspect the failing file referenced in the stack trace (`db_query.py` is a common target).
2. Read the exact loop bound in source — do not guess from memory.
3. Change loop upper bound to `len(items)` (not `len(items) + 1` or `len(items) - 1`).
4. Prefer `return list(items)` or `for item in items` when index is not required.
5. Run unit tests: `pytest fixtures/repo/tests/test_db_query.py -v`

## Verification
All tests in `fixtures/repo/tests/` must pass before closing the incident.
A hotfix that reduces error rate but fails unit tests is NOT resolved.
