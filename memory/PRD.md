# LLM Council — Heroku Deployment

## Goal
Make the LLM Council app (repo `africAIsoftmarketing/llm-council`) deployable on Heroku as a single web dyno: FastAPI serves the API + the pre-built React frontend.

## KEY FINDING (2026-06-30)
- The Emergent workspace `/app` IS the connected repo (full-featured version: documents, vision, LM Studio, advanced config, built-in Settings UI). "Save to Github" pushes `/app`.
- The earlier failed Heroku deploy used branch `master_herokuVersion` which had NO deploy files → `Procfile (none)` → H14 "No web processes". Only `heroku/python` buildpack ran (no root package.json), Python 3.10 (.python-version), uv sync.

## What was done on /app (Heroku-ready)
- Root files created: `Procfile` (`uvicorn backend.main:app --port $PORT`), `runtime.txt` (python-3.12.10), `.python-version` -> 3.12.10, `requirements.txt` (minimal), `app.json` (2 buildpacks), `package.json` (heroku-postbuild builds frontend), `.env.example`.
- `pyproject.toml` updated to the real minimal runtime deps and `uv.lock` regenerated (Heroku uses `uv sync --locked`). Deliberately EXCLUDES torch/easyocr/opencv/pandas (backend/requirements.txt bloat) to stay under Heroku's 500MB slug limit — code only imports fastapi/uvicorn/httpx/pydantic/dotenv/PyPDF2/docx/pptx/PIL/multipart.
- Backend already served static frontend (SPA catch-all after /api) and api.js already used relative URLs — no change needed there.
- Branding: title `LLM Council — AfricAIsoft`, footer `Powered by AfricAIsoft`, accent `#1a5276`.
- `.gitignore`: keeps `frontend/dist/`, `node_modules/` ignored; tracks `.env.example`.
- Cleaned up: removed irrelevant nested clone `/app/llm-council` and `/app/artifacts`.

## Validation (done locally)
- `uv lock` OK; frontend `npm run build` OK; `uvicorn backend.main:app --port $PORT` boots and serves `/` (AfricAIsoft title), `/api/health`, `/api/conversations`, `/assets/*` (all 200). Preview confirmed branding.
- LLM pipeline not run (no OpenRouter key) — app shows "Configuration Required"; key set in-app Settings or via OPENROUTER_API_KEY.
- NOTE: pre-existing bug (not deployment-related): GET /api/documents/supported-types returns 404 because `/api/documents/{doc_id}` route is declared before it.

## Deploy steps for the user
1. Click "Save to Github" (pushes /app to africAIsoftmarketing/llm-council). Note the target branch.
2. heroku buildpacks:clear; add `heroku/nodejs` (index 1) then `heroku/python` (index 2).
3. (optional) `heroku config:set OPENROUTER_API_KEY=...` (or configure in-app).
4. `git push heroku <branch>:main` ; `heroku open`.

## Backlog / next
- P1: pre-existing route-order bug for /api/documents/supported-types.
- P2 (DONE 2026-07-01): Postgres persistence — see below.

## 2026-07-01 — Heroku Postgres persistence (conversations)
`backend/storage.py` now auto-selects a backend: **PostgreSQL** when `DATABASE_URL` is set (Heroku Postgres add-on), else JSON files (local/ephemeral). Only the 5 primitives (create/get/save/list/delete_conversation) are backend-aware; table `conversations (id TEXT PK, data JSONB, created_at, updated_at)` is auto-created on first use (`_ensure_table`). Uses `psycopg2-binary` (added to pyproject + uv.lock), connection pool, `sslmode=require` (override via `DB_SSLMODE`). app.json adds `heroku-postgresql:essential-0`; README documents the addon command; .env.example documents DATABASE_URL/DB_SSLMODE.
Validated with a real local Postgres 15: create/get/save/list(newest-first)/delete + incremental assistant updates all persist; data survives a fresh process (restart-safe); JSON fallback still works with no DATABASE_URL.

## 2026-07-01 — App CONFIG persistence (fixes settings lost on restart)
The in-app config (OpenRouter API key, council models, chairman, LM Studio URLs, advanced config, throttle, etc.) was stored in `data/config.json` on the ephemeral disk → lost on every dyno restart. Fixed by making `config_manager.load_config`/`save_config` backend-aware: when `DATABASE_URL` is set, config is stored as a single JSONB row in an `app_config` table (reusing storage's PG pool); else file fallback. `get_api_key`/`get_council_models`/`apply_config_to_env` all read through `load_config`, so the key flows to OpenRouter after restart. Validated with local Postgres: API key + models survive a fresh process.

## 2026-07-01 — Fix: Stage 2/3 never ran (TypeError)
`council.stage2_collect_rankings` was missing the `advanced_config` parameter, yet its body referenced `advanced_config` (NameError) and callers passed it as a kwarg (TypeError). Stage 2 raised immediately → task set status=error → Stages 2 & 3 never executed (UI showed only Stage 1). Added `advanced_config: dict = None` to the signature. Validated: a full run now reaches status=complete with stage1/2/3 all populated.
`config_manager.add_custom_model` previously appended only to the in-memory `AVAILABLE_MODELS` (lost on restart). Now custom models are stored in config under `custom_models` (persisted via Postgres/file); `get_available_models` merges built-ins + persisted customs (deduped); `custom_models` added to `DEFAULT_CONFIG` and `update_config` allowed keys. Validated with local Postgres: custom model + its selection in `council_models` survive a fresh process; no duplicate on re-add.

## 2026-06-30 — Resume-on-refresh for in-progress council runs
Problem: refreshing mid-conversation lost all streaming progress (response only saved after Stage 3; client disconnect cancelled the run).
Fix:
- `backend/storage.py`: `add_running_assistant_message` + `update_last_assistant_message` (incremental per-stage persistence with a `status` field: running/complete/error).
- `backend/main.py`: in-memory run hub (`_run_hub`) with publish/subscribe + event replay; council now runs in a DETACHED `asyncio` task (`_run_council_task`) that survives client disconnect and persists each stage. POST `/message/stream` starts the task and streams; new GET `/conversations/{id}/stream` resumes (replays past events + live).
- `frontend/src/api.js`: `resumeStream()` (GET SSE reader).
- `frontend/src/App.jsx`: extracted `makeEventHandler(convId)` (conversation-guarded); `loadConversation` detects a `running` assistant, reconstructs loading flags from saved stages, and resumes the live stream; `complete` re-syncs persisted state.
Validated locally (dummy key): MAIN + RESUME streams both received replayed events; stage1 persisted incrementally; error path persisted+broadcast. Rebuilt & committed `frontend/dist`.

## 2026-07-01 — Switched resume/progress to POLLING (Heroku-robust)
SSE resume was unreliable on Heroku (router/proxy buffering delayed events; the run kept only stage1 visible after refresh). Replaced the client update mechanism with polling of the incrementally-persisted state:
- Backend: new `POST /api/conversations/{id}/run` starts the detached council task and returns `{status:"started"}` immediately (no streaming). SSE endpoints kept for compatibility + added `X-Accel-Buffering: no`.
- Frontend: `api.startRun()`; `App.jsx` polls `GET /api/conversations/{id}` every 2s (`startPolling`), rebuilding loading flags from saved stages and stopping when `status != running` (surfaces `error` via toast). `loadConversation` starts polling when a `running` assistant is detected → refresh-safe. Removed SSE `makeEventHandler`.
Validated: `/run` returns instantly; polling shows stage1 persisted + status transitions (complete/error). UI renders (title/footer intact).
