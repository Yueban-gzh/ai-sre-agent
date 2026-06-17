## Controlled Reflexion Evaluation Context

This is a controlled fault-injection evaluation of the Reflexion loop.

A previous on-call responder has already applied the runbook's emergency
"Quick Mitigation". The patch may have removed the visible IndexError
without preserving the endpoint's required business behavior.

Mandatory execution order:

1. Gather the relevant logs, source, runbook evidence, and test constraints.
2. Before calling `apply_patch`, call `run_tests` to verify the currently
   installed emergency hotfix.
3. Do not modify source code before this first verification.
4. When verification fails, inspect the exact failed assertions.
5. Use the injected Reflexion observation to explain why the previous
   mitigation was incomplete.
6. Re-read the current source and compare "Quick Mitigation" against
   "Full Remediation Steps".
7. Apply a different, evidence-based patch.
8. Run the same tests again.
9. Produce the incident report only after the tests pass.

The final report must explicitly distinguish:

- original defect;
- previously applied emergency hotfix;
- failed verification evidence;
- final remediation;
- successful regression-test evidence.
