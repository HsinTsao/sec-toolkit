---
name: sec-toolkit
description: Repository-specific workflow for SecToolkit. Use when working in this repo on FastAPI backend code, React/TypeScript frontend code, SQLite data and migrations, Docker deployment scripts, Nginx proxy routing, Quick PoC/file-based PoC behavior, callback/OOB features, or LLM Agent tools.
---

# SecToolkit Skill

Use this skill to work on the SecToolkit repository without relying on Cursor-specific `.mdc` rules. Treat the repository as the source of truth and prefer the current code over stale documentation.

## Architecture

- Backend: FastAPI, async SQLAlchemy, aiosqlite, SQLite.
- Frontend: React 18, TypeScript, TailwindCSS, Zustand.
- API clients: handwritten Axios wrapper in `frontend/src/lib/api.ts`; generated API files under `frontend/src/api/generated/`.
- Deployment: Docker Compose with `backend` and `frontend` services; the frontend container runs Nginx.
- Runtime data: `data/` locally and `/app/data` inside the backend container.
- Production database: `data/toolkit.db`, mounted into Docker as `/app/data/toolkit.db`.

Important paths:

- Backend app: `backend/app/`
- API routers: `backend/app/api/v1/`
- SQLAlchemy models: `backend/app/models/`
- Pydantic schemas: `backend/app/schemas/`
- Tool logic modules: `backend/app/modules/`
- LLM Agent tools: `backend/app/agent/tools/`
- Frontend tool pages: `frontend/src/features/tools/`
- Frontend routes: `frontend/src/App.tsx`
- Sidebar navigation: `frontend/src/components/layout/Sidebar.tsx`
- Frontend Nginx config: `frontend/nginx.conf`
- SSL Nginx configs: `frontend/nginx-ssl.conf`, `deploy/nginx-ssl.conf`
- Deploy scripts: `deploy/`

## Backend Rules

- Use async DB access with `AsyncSession`; do not introduce sync SQLAlchemy sessions.
- Add API routes under `backend/app/api/v1/` and include routers through `backend/app/api/__init__.py` when creating a new route file.
- Keep complex business logic in `services/` or `modules/`; route handlers should primarily validate, call services, and return HTTP responses.
- Use `HTTPException` for standard API errors.
- Use UUID strings for primary keys and export new models from `backend/app/models/__init__.py`.
- Run `backend/scripts/migrate_db.py` for table creation or additive migrations. `Base.metadata.create_all` does not alter existing tables.

## Frontend Rules

- Put feature pages in `frontend/src/features/`.
- Put shared UI in `frontend/src/components/`.
- Use Tailwind theme classes such as `bg-theme-card`, `text-theme-text`, and `border-theme-border`.
- Use `cn()` from `frontend/src/lib/utils.ts` for conditional classes.
- Use `lucide-react` for icons.
- When backend API schemas change, regenerate generated clients with `npm run generate-api` from `frontend/` if generated client usage is affected.

## Adding A User-Facing Tool

Use this flow for ordinary tools:

1. Add pure backend logic under `backend/app/modules/<tool>/`.
2. Add or update an API endpoint under `backend/app/api/v1/`.
3. Regenerate API clients if needed.
4. Add a frontend page under `frontend/src/features/tools/`.
5. Add the route in `frontend/src/App.tsx`.
6. Add sidebar navigation in `frontend/src/components/layout/Sidebar.tsx`.
7. Build or test the affected frontend/backend surface.

## Adding An LLM Agent Tool

Use this flow for tools callable from AI Chat:

1. Put reusable logic in `backend/app/modules/` when the tool has non-trivial behavior.
2. Add a tool wrapper under `backend/app/agent/tools/`.
3. Register it through `register_builtin_tools()` in `backend/app/agent/tools/__init__.py`.
4. Use clear `ToolParameter` descriptions because Intent LLM routing depends on those descriptions.
5. If routing priority matters, inspect `backend/app/agent/intent.py`.
6. Restart the backend before testing natural-language triggering.

## Quick PoC

Quick PoC has two sources:

- Code-based PoCs under `backend/app/poc/handlers/`, registered through `@poc`.
- File-based PoCs under `data/poc-files/` locally and `/app/data/poc-files/` in Docker.

File-based examples:

- `data/poc-files/test.html` -> `/p/test`
- `data/poc-files/payload.js` -> `/p/payload`
- `data/poc-files/kit/index.html` -> `/p/kit`
- `data/poc-files/kit/evil.js` -> `/p/kit/evil.js`

Rules:

- Do not hard-code source-tree paths for runtime PoC files. In Docker the backend app runs from `/app/app`, while runtime data is mounted at `/app/data`.
- Respect `APP_DATA_DIR` and `APP_POC_FILE_DIR` when present.
- Quick PoC list data comes from `/api/poc/list`.
- Public PoC responses are served by backend routes `/p/{name}` and `/p/{name}/{path:path}` in `backend/app/main.py`.

Known failure mode:

- If `/p/test` or `/p/<name>` returns the React homepage, Nginx is handling it as SPA fallback instead of proxying it to the backend.
- Fix by adding `location /p/ { proxy_pass http://backend:8000/p/; ... }` to every active frontend Nginx config, including `frontend/nginx.conf`, `frontend/nginx-ssl.conf`, and `deploy/nginx-ssl.conf` when applicable.
- Keep `/p/` alongside `/api/` and `/c/` proxy locations, before the final `location / { try_files ... /index.html; }`.

## Deployment

Production should use Docker deployment, not `./start.sh dev`.

Daily deploy flow:

```bash
cd /code/sec-toolkit
git pull origin main
./deploy/preflight.sh
./deploy/deploy.sh
```

For low-risk deployments when a fresh backup already exists:

```bash
./deploy/deploy.sh --skip-backup
```

Disk-sensitive settings for small servers:

```bash
APP_BACKUP_KEEP_COUNT=1
APP_MIN_FREE_SPACE_MB=2048
DEPLOY_PRUNE_BUILD_CACHE=false
DEPLOY_PRUNE_DANGLING_IMAGES=true
```

For China-hosted servers, configure mirrors in `.env`:

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
```

Tradeoff:

- Keeping Docker build cache makes deploys faster.
- Running `docker builder prune -af` frees space but makes the next build slow because `pip install`, `npm ci`, and browser dependency layers may be rebuilt.

## Database And Data Safety

- Do not delete `data/toolkit.db`, `data/toolkit.db-wal`, `data/toolkit.db-shm`, `data/uploads/`, `data/poc-files/`, or `.env`.
- `data/` is runtime data; most of it is intentionally ignored by Git.
- `data/poc-files/**` is allowed in Git for reusable PoC examples.
- Backup snapshots live in `backups/snapshot-*`; keep retention low on small disks.

## Local Development

Use `start.sh` for non-Docker local development:

```bash
./start.sh dev
./start.sh stop
./start.sh status
./start.sh logs
```

Ports:

- Frontend: `http://localhost:80` or Vite dev port depending on mode.
- Backend: `http://localhost:8000`.
- API docs: `http://localhost:8000/api/docs`.

## Validation Checklist

Choose checks based on the change:

- Backend syntax: `python3 -m compileall backend/app`
- Deploy script syntax: `bash -n deploy/*.sh`
- Frontend build: `cd frontend && npm run build`
- Compose config on a Docker-capable server: `docker compose -f docker-compose.yml config`
- Quick PoC API: `curl -s http://127.0.0.1:8000/api/poc/list`
- Public PoC route through frontend Nginx: `curl -i http://127.0.0.1/p/test`
