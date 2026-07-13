# SecToolkit Agent Instructions

All AI agents working in this repository should first read:

```text
.ai/skills/sec-toolkit/SKILL.md
```

That file is the tool-agnostic project skill derived from the old Cursor `.mdc` rules. Prefer it over Cursor-specific files when instructions conflict.

Key reminders:

- Production deployment uses Docker Compose, not `./start.sh dev`.
- Runtime data lives under `data/` locally and `/app/data` inside Docker.
- File-based Quick PoC files live under `data/poc-files/` and are served as `/p/<name>`.
- Frontend Nginx must proxy `/p/` to the backend. If `/p/test` returns the React homepage, check the Nginx `location /p/` rule before debugging backend code.
