- Tasks are GitHub issues, one at a time
- The MVP plan is the product source of truth; read the relevant acceptance criteria before starting and before closing an issue
- `_docs/tasks.md` mirrors the GitHub issue backlog; keep both aligned when task scope changes
- Project code, UI text, and project documentation are written in English
- Commit regularly

Roles

- PM - grooms a task before anyone implements it, follows `_docs/team/pm.md`
- UX Specialist - reviews the groomed task and defines the intended user experience before implementation, follows `_docs/team/ux-specialist.md`
- Engineer - implements one groomed task, follows `_docs/team/software-engineer.md`
- QA - checks the result against the acceptance criteria, follows `_docs/team/qa-engineer.md`

Orchestrator

The main session is the orchestrator. It launches the PM, UX Specialist,
engineer and QA as subagents. It does not groom, design, implement or test itself.

Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. UX Specialist reviews the groomed task and defines the intended user experience when relevant
4. Engineer implements it
5. QA verifies it
6. On FAIL, back to step 4 with the QA comment as input
7. On PASS, close the issue
8. Repeat until the backlog is empty

Rules

- Do not skip step 2
- Do not skip step 3 for tasks with user-facing impact
- For tasks with no UX impact, the UX Specialist may return `No UX impact`
- The UX Specialist does not change product scope or acceptance criteria; ambiguities that affect product behavior go back to the PM
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator closes the issue only after QA outputs PASS
- Closing means closing the remote GitHub issue, not only finishing the code. After QA returns PASS, run `gh issue close <number> --comment "QA: PASS ..."`.
- Immediately verify the remote state with `gh issue view <number> --json state`; the issue is not complete until the result is `CLOSED`.
- Before declaring the backlog empty, run `gh issue list --state open` and confirm that it returns no MVP issues.