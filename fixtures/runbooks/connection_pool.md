# Runbook: Database Connection Pool Exhaustion

## Symptoms
- HTTP 500 on database-backed endpoints
- Elevated error rate after deploy
- Logs may show timeout or connection warnings

## Common Root Cause
Connection pool saturation under load — unrelated to Python list indexing.

## Remediation Steps
1. Check connection pool metrics (active / idle / waiting).
2. Increase pool size or reduce query timeout in service config.
3. Restart connection pool sidecar if configured.
4. Roll back deploy if pool settings changed in last release.

## When NOT to use this runbook
If the stack trace shows `IndexError: list index out of range` in application code,
this is an **application logic bug**, not a connection pool issue. Use the IndexError runbook instead.
