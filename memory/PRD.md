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

## Next action items / backlog
- P0: Provide GOOGLE_CLIENT_ID/SECRET; add redirect URI `https://<host>/api/auth/callback`
  in Google Console; then set DEV_AUTH=0 in prod.
- P0: Provide OPENROUTER_API_KEY so the council actually runs.
- P1: Complete a full PayPal sandbox purchase in a real browser (capture + credit).
- P2: i18n EN toggle; per-user document scoping (documents currently global).
