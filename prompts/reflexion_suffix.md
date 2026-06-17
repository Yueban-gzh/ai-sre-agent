## Reflexion Trigger

The previous remediation attempt did NOT pass verification.

<observation>
{observation}
</observation>

<reflection_instruction>
1. What specifically failed? (wrong loop bound? hotfix `- 1` instead of correct fix? wrong file?)
2. Re-read the source with `read_source` — do NOT trust the hotfix section alone.
3. Check RAG results for "Full Remediation Steps" vs "Quick Mitigation".
4. Propose a DIFFERENT patch than before, then call `run_tests` again.
</reflection_instruction>

Reflect inside `<reasoning>` tags first. Do NOT repeat the same search/replace snippet.
