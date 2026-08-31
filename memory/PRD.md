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

## Bugfix (2026-07-26): Heroku 500 on POST /api/conversations
- Cause: psycopg2 (storage.py, settings_store.py) defaulted DB_SSLMODE to "disable".
  Heroku Postgres requires SSL -> "no pg_hba.conf entry ... no encryption" FATAL.
  db.py (asyncpg) worked because asyncpg negotiates SSL automatically.
- Fix: default DB_SSLMODE changed "disable" -> "require" in storage.py & settings_store.py.
  Local backend/.env keeps DB_SSLMODE=disable explicitly (local PG has no SSL).
- Action for prod: redeploy, OR immediate `heroku config:set DB_SSLMODE=require`.
- Note: local Postgres (postgres user + /var/lib/postgresql) was missing in this fork;
  reinstalled postgresql-15, recreated role postgres/postgres and db llm_council.

## Bugfix (2026-07-27): Heroku 500 - column "user_id" does not exist
- SSL fix worked; next error: conversations table on Heroku predates the user_id column.
  CREATE TABLE IF NOT EXISTS never alters an existing table.
- Fix: storage._ensure_table() now runs idempotent ALTER TABLE ADD COLUMN IF NOT EXISTS
  for user_id, created_at, updated_at. Runs lazily on first psycopg2 pool init.
- Validated locally by dropping user_id (simulating old schema) -> restart -> create conv 200.
- Action: user must redeploy to Heroku for this code to run.

---
## SSE Streaming Fix (Heroku) — 2026
Problem: On Heroku the 3-stage SSE pipeline hung on Stage 1 (backend generated
responses, frontend spinner never resolved).

Root causes:
1. Fragile frontend SSE parsing in api.js sendMessageStream (chunk.split('\n'),
   no buffer) — Heroku splits large stage1_complete across TCP chunks, truncated
   data: lines failed JSON.parse (silently) and events were lost.
2. SSE buffering by Heroku router/uvicorn; no early flush/heartbeat.

Fixes:
- frontend/src/api.js: buffered SSE parser (decode {stream:true}, split on \n\n,
  keep partial remainder, ignore ':' comments, never parse partial lines).
- backend/main.py send_message_stream: headers Cache-Control no-cache,no-transform +
  Connection keep-alive + X-Accel-Buffering:no; immediate ': ping'; 10s heartbeat
  during Stage 1 via run_with_heartbeat. SSE event format & credit logic unchanged.
- Rebuilt frontend/dist.

Verification: raw curl (ping first, correct framing) + node fragmentation test pass.
Full 3-stage happy path not run live (no OpenRouter key in preview).

---
## SSE Heartbeat Extended to Stages 2 & 3 — 2026
Residual bug: same infinite-spinner symptom reappeared on Stage 2/3 (stage2_start
and stage3_start shown, but stage2_complete/stage3_complete never received). Cause:
run_with_heartbeat was only applied to Stage 1; Stages 2/3 were plain awaits →
no bytes sent during their long OpenRouter calls → Heroku 30s/55s cutoff.
Fix (backend/main.py event_generator): wrapped stage2_collect_rankings and
stage3_synthesize_final in the existing run_with_heartbeat, extracting result via
("__result__", value) marker. Stage 2 result is a tuple (stage2_results,
label_to_model) — unpacked after extraction (marker tuple != business tuple).
SSE format, credit logic, headers, 10s interval unchanged. Frontend unchanged.
Verified: async heartbeat test (tuple+object results) PASS.

---
## Stage 3 Report Actions (export/copy) — 2026
Additive frontend fix (regression restore). frontend/src/components/Stage3.jsx now
shows an action bar (only when finalResponse exists) with 3 buttons:
- Copier: navigator.clipboard.writeText(finalResponse.response) + textarea/execCommand
  fallback for non-secure contexts; shows "Copié ✓" for 2s.
- Exporter .txt: Blob text/plain;charset=utf-8 → <a download> → revokeObjectURL.
  Filename council-report-<timestamp>.txt.
- Exporter .pdf: jsPDF (unit pt, a4) + splitTextToSize + manual pagination loop
  (handles long reports, no truncation). Filename council-report-<timestamp>.pdf.
Errors (clipboard denied / PDF fail) show an inline .report-action-error line for 3s
(Stage3 receives no showToast prop, so feedback is self-contained).
Deps: jspdf added to package.json (pulls html2canvas/dompurify as optional; bundles OK).
Styles added to Stage3.css (.final-response-header, .report-actions, .report-action-btn,
.report-action-error). Backend/SSE/pipeline untouched. Frontend rebuilt → frontend/dist.
NOTE: live Stage-3 render requires a completed council run (OpenRouter key), not
available in preview; verified via successful Vite build + bundle contains the labels.

---
## Stage 3 Enriched Report + Export Quality — 2026
Frontend-only, additive. Backend/SSE/credits untouched.
PART A (render + exports):
- ReactMarkdown now uses remark-gfm (tables, etc.). LaTeX artifacts normalized to
  Unicode ($\checkmark$→✓, $\rightarrow$→→, $\approx$→≈, $\times$→×, $\leq$→≤ …) and
  $...$ delimiters stripped; decorative ═══/***/=== runs → real <hr>.
- On-screen hierarchy improved in Stage3.css: styled section headings, dark monospace
  code blocks (<pre><code>), GFM tables, blockquotes.
- PDF export rewritten to WYSIWYG: html2canvas captures an offscreen fully-expanded
  report surface (browser fonts render all Unicode → no more %P%P/!' corruption),
  paginated across A4 pages. txt/copy use markdownToPlain() (strips md, keeps Unicode).
PART B (all council members in final report):
- Stage3.jsx now accepts stage1Responses, aggregateRankings, labelToModel props
  (propagated from ChatInterface.jsx). Renders: Chairman synthesis (always visible) +
  collapsible "Membres du council" accordion (per-model markdown, collapsed by default,
  first member open) + collapsible "Classement agrégé" table (#, modèle, score moyen,
  votes). Missing stage1/aggregate handled gracefully (sections hidden).
- Copy/.txt/.pdf all include the full enriched content (Chairman + members + ranking).
Deps added: html2canvas, remark-gfm (jspdf already present). Vite build OK.
Verified visually via temp preview route (removed after): markdown clean, Unicode
correct, members accordion expands & renders, code/table styled. frontend/dist rebuilt.

---
## 5 Improvements: math render, key persistence, settings gating, T&C, legal — 2026
Verified: testing_agent iteration_20 — 14/14 backend pytest + 4 Playwright UI flows, 100%, no defects.
1. Math/Markdown: new shared src/components/MarkdownView.jsx (react-markdown + remark-gfm +
   remark-math + rehype-katex + katex css); preprocessMath converts \[..\]→$$, \(..\)→$,
   decorative rules→<hr>. Stage1/2/3 now use MarkdownView (KaTeX renders \boxed{}, etc.).
2. API key persistence + admin-only settings: config_manager.get_api_key() reads Postgres
   app_settings('openrouter_api_key') first (survives Heroku restart) then config.json/env.
   PUT /api/config, POST /api/config/advanced, GET /api/config/advanced, POST /api/config/
   validate-key => admin only (get_current_admin, 403 for non-admin). GET /api/config =>
   any logged-in user, overlays council/chairman + has_api_key + masked key from DB. Frontend:
   App.isAdmin gates Settings view + Advanced panel; Sidebar hides nav-settings/nav-advanced
   for non-admins. Non-admins inherit admin key (has_api_key=true).
3. Council selection persistence: GET /api/config overlays council_models/chairman_model from
   app_settings (persist across restart); App caches to localStorage 'llm_council_last_selection'
   and restores on load.
4. Terms & Conditions modal (English): src/components/TermsModal.jsx(+css). Shows on first
   launch (localStorage 'llm_council_terms_accepted_v1' absent), accept btn disabled until
   checkbox ticked, blocks app, remembered after accept (no reappear on reload).
5. Contact/legal: src/components/AppFooter.jsx(+css) in app shell (email
   llmcouncilsupport@africaisoft.africa + /legal + privacy links); src/pages/Legal.jsx(+css)
   at route /legal (Legal notice + Privacy + Terms + Contact). main.jsx registers /legal.
Deps added: katex, remark-math, rehype-katex (+ earlier jspdf, html2canvas, remark-gfm).
NOTE: Feature 1 runtime math render not exercised (needs OpenRouter key); static-verified.
Preview only: Postgres is NOT supervisor-managed — bootstrap it before backend on pod restart.
