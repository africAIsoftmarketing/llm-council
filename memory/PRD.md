# LLM Council — Heroku Deployment (branch `heroku-deploy`)

## Problem statement
Transform the LLM Council project (fork of karpathy/llm-council, repo `africAIsoftmarketing/llm-council`) into a Heroku-deployable single-dyno web app on a new branch `heroku-deploy` (branched from `master`). `master` stays untouched.

## Architecture (target)
Monolithic single-dyno: FastAPI serves the `/api/*` backend AND the pre-built React frontend (`frontend/dist/`) via `StaticFiles` + SPA catch-all. Two Heroku buildpacks: `heroku/nodejs` (builds frontend via root `package.json` `heroku-postbuild`) then `heroku/python`.

## What's been implemented (2026-06-30)
- Root files: `Procfile`, `runtime.txt` (python-3.12.10), `requirements.txt`, `app.json` (buildpacks+env+formation), `package.json` (delegates build to frontend), `.env.example`.
- `backend/main.py`: reads `$PORT`; dynamic CORS (localhost + `$HEROKU_APP_NAME` + `$CUSTOM_DOMAIN`); static serving + SPA catch-all declared AFTER all `/api` routes (route order is critical); old `GET /` health moved to `GET /api/health`.
- `backend/config.py`: `COUNCIL_MODELS` (comma-separated) and `CHAIRMAN_MODEL` env-configurable with defaults; `DATA_DIR` env-configurable.
- `backend/storage.py`: ephemeral-filesystem note + `# TODO: Migrate to Heroku Postgres`.
- `frontend/src/api.js`: relative API base in prod, `localhost:8001` in dev, `VITE_API_URL` override.
- `frontend/vite.config.js`: `/api` dev proxy + build outDir `dist`.
- Branding: title `LLM Council — AfricAIsoft`, footer `Powered by AfricAIsoft`, accent `#1a5276`.
- README Heroku section + CLAUDE.md branch notes. `.gitignore` keeps `frontend/dist/` ignored.

## Validation (done)
- `npm run build` -> `frontend/dist/index.html` OK
- `pip install -r requirements.txt` OK
- `PORT=... python -m backend.main`: `/` -> index.html, `/api/health` & `/api/conversations` -> JSON, POST create works, SPA fallback works, unknown `/api/*` -> 404 OK
- Visual preview verified: UI loads, title + footer + accent correct, conversation list loads via relative `/api` OK
- LLM deliberation pipeline (Stage 1->2->3) NOT triggered — requires real OpenRouter key, user tests post-deploy (their choice).

## Notes / Next actions
- Code lives in nested repo `/app/llm-council` on branch `heroku-deploy`, committed locally. Needs `git push` to GitHub.
- Storage is ephemeral on Heroku (MVP). P1: migrate to Heroku Postgres.
