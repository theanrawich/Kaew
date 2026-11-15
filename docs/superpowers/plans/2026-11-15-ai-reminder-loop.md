# AI reminder loop implementation plan

Goal: implement the user's M4 specification on the existing feature/ai-reminder-loop branch.
Architecture: refactor hydration_ai and advice_log; use stdlib Groq/OpenRouter adapters, bounded JSON decisions, and the existing reminders/notification jobs. Decisions run on admin requests, new drink events, and after repeating reminders fire. Commit the fire before inference; guard against overwriting a reminder changed during inference. Preserve pending one-shot voice reminders on automatic triggers. Never authorize actuation.

The detailed user request is the binding specification. Execution is inline as requested, without restarting or switching branches.

- [x] Add failing contract/provider tests and integration assertions (scheduling, history, migration, auth, one-shot preservation, no immediate jobs).
- [x] Implement provider selection, validation/fallback, schema v8 and Postgres 002, atomic logging/scheduling, triggers and latest decision API.
- [x] Add compact dashboard display and update environment/operator/M4 documentation.
- [x] Run both required suites, inspect diff and secrets without exposing values, commit locally, and write the external report including exact SQL.

Review focus: no network inside writer transactions; stale inference cannot replace a newer manual reminder; duplicate/fault events do not infer; fallback schedules; one-shot delivery stays one-shot. All tests use explicit injected providers or no provider, never environment credentials.

Verification: JS 25 passed; Python 76 run, 71 passed and 5 optional local Postgres tests skipped. Dashboard inline JavaScript syntax passed. Independent review found overdue one-shot loss and a Postgres writer-lock gap; both were fixed. Overdue regression failed before the fix and passed afterward. Added optional Postgres shared-lock coverage; it remains skipped without a local test database. One Groq smoke: HTTP 200, JSON parsed, openai/gpt-oss-20b. User-directed finish: commit locally, keep this branch/workspace, no push/PR/deploy.
