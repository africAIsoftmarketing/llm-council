# LLM Council — v9 Monetization PRD

## Original problem statement
Transform LLM Council (3-stage OpenRouter deliberation app) into a monetized SaaS:
Google SSO auth, prepaid credit system via PayPal (pay-per-request), and a full admin
panel. Stack imposed: PostgreSQL + SQLAlchemy 2.x async + Alembic, authlib Google OAuth,
PayPal Checkout (Orders v2), React + Vite + react-router. French-first UI.

## User choices (2026-06)
- DB: strict PostgreSQL/SQLAlchemy/Alembic (a local Postgres runs in the preview container).
- Auth: their own Google OAuth 2.0 (authlib). GOOGLE_CLIENT_ID/SECRET **not yet provided**.
- PayPal: sandbox creds provided (client id/secret/webhook id).
- OpenRouter: no key provided (council pipeline cannot actually run -> auto-refund on failure).
- Admin email: somecedric@gmail.com.

## Architecture
- Backend FastAPI (`backend/main.py`; `server:app` on :8001).
  - `db.py` — async SQLAlchemy models: users, credit_transactions, app_settings; atomic
    `debit_user`/`credit_user`; partial unique index on `paypal_order_id` (idempotency).
  - `auth.py` — Google OAuth (authlib) + JWT httpOnly cookie (`council_session`, 7d,
    Secure, SameSite=Lax) + `get_current_user`/`get_current_admin`. `dev-login` gated by
    `DEV_AUTH=1` for preview testing (disable in prod).
  - `payments.py` — PayPal Orders v2 (create/capture) + webhook w/ signature verification.
  - `admin.py` — /api/admin/* (admin-only): models (OpenRouter-validated), users, settings, stats.
  - `settings_store.py` — app_settings w/ 60s cache + defaults seed; config_manager reads
    council_models/chairman from here (runtime-editable). council.py untouched.
  - `storage.py` — conversations in Postgres, scoped by user_id.
- Frontend React+Vite: react-router pages `/login`, `/` (council), `/credits`, `/admin`;
  AuthContext + RequireAuth (adminOnly). Header shows live credit balance + buy button.
  402 -> "Crédits insuffisants" modal -> CTA `/credits`.
- Alembic migration `0001_initial`; Procfile `release: alembic upgrade head`.

## Implemented & verified (2026-06)
- Dev-login, JWT cookie, /me, RBAC (403 non-admin) — verified.
- Atomic debit; 402 {error,required,balance} — verified.
- Auto-refund on pipeline failure (both /message -> 502 and /message/stream -> SSE error) — verified.
- Admin models/users/pricing/stats — verified. PayPal order creation (real sandbox id) — verified.
- Conversations persist per-user in Postgres. 22/22 pytest pass.

## Deployment fixes (post-launch)
- 2026-06 Heroku `alembic: not found`: added all runtime deps to root pyproject.toml + uv.lock.
- 2026-06 Heroku "no paywall gate": frontend/dist was gitignored -> Heroku served a stale/dev
  build. Fix: committed a fresh auth-gated `frontend/dist` (un-ignored), hardened
  `get_frontend_path()` to only serve a real build (index.html + assets/, never the Vite dev
  entry), added root `package.json` (heroku-postbuild) + `app.json` (heroku/nodejs then
  heroku/python). Verified 100% (anon -> /login on / /credits /admin; 22/22 backend tests).
  NOTE: for an existing Heroku app, set buildpack order: `heroku buildpacks:clear` then add
  heroku/nodejs then heroku/python. Committed dist also works with Python-only buildpack.

- 2026-06 Heroku `uv.lock needs to be updated (--locked)`: the committed uv.lock kept
  drifting from pyproject.toml. Final fix = switch Heroku Python build from uv to **pip**:
  deleted `uv.lock`, added root `requirements.txt` with all runtime deps. heroku/python
  selects pip when no uv.lock/poetry.lock and a requirements.txt exists. Verified: pip
  resolves clean, alembic release migrates a fresh DB, 22/22 tests. IMPORTANT: uv.lock must
  stay deleted in the GitHub repo, else the buildpack reverts to `uv sync --locked`.

## Next action items / backlog
- 2026-06 Feature: Council Models UI (Settings) — per-model ✎ edit (change OpenRouter id
  inline) + 🗑 delete buttons; Save Council now mirrors council_models & chairman_model into
  app_settings (PUT /api/config -> settings_store) so edits hit the live pipeline. Verified 28/28.
- P0: Provide GOOGLE_CLIENT_ID/SECRET; add redirect URI `https://<host>/api/auth/callback`
  in Google Console; then set DEV_AUTH=0 in prod.
- P0: Provide OPENROUTER_API_KEY so the council actually runs.
- P1: Complete a full PayPal sandbox purchase in a real browser (capture + credit).
- P2: i18n EN toggle; per-user document scoping (documents currently global).
