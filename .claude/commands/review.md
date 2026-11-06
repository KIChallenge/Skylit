---
description: Review a diff, branch or PR for bugs, secrets and rule violations
---

Review this change: $ARGUMENTS

If no target is given, review the uncommitted diff (`git diff HEAD`).

Report findings ordered by severity. For each: file and line, the problem, a concrete fix.
Check in this order:
1. Leaked secrets, personal data or real health data.
2. Bugs that break the demo flow.
3. Violations of AGENTS.md (files outside the task, missing README run steps, missing decision log entry).
4. Missing error handling or timeouts at external calls (LLM APIs, file IO).
5. UI: colours, sizes or components outside `docs/DESIGN.md`, missing loading, empty or error states, wrong-language or placeholder text.
Skip style nitpicks. If the change is fine, say so in one line.
