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
- P2: ephemeral storage on Heroku (conversations/documents lost on restart) -> Postgres/S3.
