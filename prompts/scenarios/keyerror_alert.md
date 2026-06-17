[PagerDuty ALERT — SEV2]

Service: user-profile-api
Time: 2026-06-18 14:30 CST
Symptom: HTTP 500 errors on GET /api/users/{id}/tier
Error rate: 28 req/min (baseline 1 req/min)
Recent deploy: yes — cache key migration deployed 3 hours ago

Note: Redis cache hit rate dropped but primary errors show KeyError in application code.

Please diagnose the root cause, apply a fix, verify with tests, and produce an incident report.
