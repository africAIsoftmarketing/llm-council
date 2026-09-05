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

---
## Role-based Settings visibility fix — 2026
Corrected prior over-gating. Verified: testing_agent iter_21 (frontend 100%) + iter_22 (backend 23/23).
- backend/main.py PUT /api/config: now get_current_user (not admin-only). Non-admins may set
  council_models / chairman_model / theme (200); admin_only_fields = {openrouter_api_key,
  lm_studio_urls, advanced_config, storage_location} -> 403 for non-admin. Gate runs before
  update_config so rejected mixed payloads write nothing (atomic). GET /api/config -> all
  logged-in users, has_api_key true (non-admin inherits admin key, raw key never leaked).
- frontend/src/App.jsx: Settings view rendered for ALL users again (passes isAdmin), not
  admin-gated.
- frontend/src/components/Sidebar.jsx: nav-settings visible to everyone; nav-advanced (separate
  Advanced LLM config modal) stays admin-only.
- frontend/src/components/Settings.jsx: takes isAdmin prop. Tabs = [API Settings (admin only),
  Council Models, Chairman, Advanced]. Default tab = api (admin) / models (non-admin). API
  section renders only when activeTab==='api' && isAdmin. Storage Location section
  (data-testid='section-storage-location') wrapped in {isAdmin && ...}; Advanced tab keeps
  Theme + About for all (not empty). data-testid='tab-api' absent for non-admins.
Result: non-admin sees Council Models + Chairman + Advanced (no API tab, no Storage Location),
can select/save council & chairman; admin sees everything. No console errors / layout breaks.
Known non-blocking: dead 'advanced_config' gate entry (field not on model; harmless/future-proof);
Theme radio group styling is a pre-existing cosmetic nit (out of scope).

---
## Per-User Council Models — 2026-06 (branch target: master_herokuVersion_v23)
Verified: testing_agent iter_23 — backend 17/17 pytest (tests/test_user_council.py), frontend 100% (both roles). Extra curl-verified de-dup + catalogue validation guards.
Non-admin users now keep a PERSONAL council selection without touching the admin's GLOBAL default; unset users fall back to the global default.
- backend/council.py: _resolve_council_models(advanced_config) / _resolve_chairman_model(advanced_config) prefer per-user override keys (_user_council_models / _user_chairman_model) injected into advanced_config, else global get_council_models/get_chairman_model. Applied in stage1/stage2/stage3 + generate_conversation_title.
- backend/main.py: helpers _user_council_key(uid)='user_council:{uid}', _user_chairman_key(uid)='user_chairman:{uid}', _get_user_council(user), _inject_user_council(user, advanced). Endpoints GET/PUT/DELETE /api/config/council (all get_current_user). PUT validates: de-dup, >=2 models, all ids in catalogue, chairman in council. GET /api/config overlays personal council for NON-ADMIN only (admin always global). Both message endpoints call request.advanced = await _inject_user_council(user, request.advanced) before pipeline. PUT /api/config stays admin-only for sensitive fields.
- frontend/src/api.js: api.getUserCouncil(), api.updateUserCouncil(models, chairman), api.resetUserCouncil().
- frontend/src/components/Settings.jsx: loadConfiguration routes admin->getConfig / non-admin->getUserCouncil (+ isCustomCouncil state). handleSaveModels routes admin->updateConfig / non-admin->updateUserCouncil. handleResetCouncil (DELETE) shown only to non-admins with a custom council (btn-reset-council). Min raised to >=2 (Save disabled < 2). Catalogue-mutating controls (Add Custom Model, catalog-edit/delete-btn-*, council inline edit-model-btn-*) gated to isAdmin; remove-model-btn-* stays for all.
Storage: Postgres app_settings JSONB, per-user keys. Persistent across restarts.
Note: admin hitting PUT /api/config/council writes harmless unused per-user state (UI never does this).

---
## Progress Bar + OpenRouter Key Status & Cost Analytics — 2026-06 (branch target: master_herokuVersion_v23)
Verified: testing_agent iter_24 — backend 9/9 new (tests/test_openrouter_and_costs.py) + 17/17 regression, frontend 100%. No issues.
Feature 1 — per-stage council progress bar (frontend-only, driven by existing SSE):
- frontend/src/components/CouncilProgress.jsx + .css: 3-step stepper (Stage1 Individual / Stage2 Peer review / Stage3 Chairman). States pending/active/done/error; active = animated indeterminate sweep (keeps moving during SSE : keep-alive heartbeats); done=green; error=red; percent shown.
- frontend/src/App.jsx: councilProgress state; set on send + reset; SSE handler maps stageN_start->active, stageN_complete->done, complete->100%/done, error->first non-done step becomes error; hard catch (402/network)->null; reset on conversation select/create. Passed to ChatInterface.
- frontend/src/components/ChatInterface.jsx: renders <CouncilProgress> at top of messages-container (above answer area).
Feature 2 — admin OpenRouter key status + per-run cost (admin-only):
- backend/openrouter.py: query_model returns usage.cost + total_tokens (adds harmless usage:{include:true}; reads cost from body regardless).
- backend/council.py: stage1/2/3 results carry cost/tokens; generate_conversation_title(return_usage=True)->(title,cost,tokens,model); aggregate_run_cost(...) -> (breakdown{model:{cost,tokens}}, total_cost, total_tokens), missing cost treated as 0 (never crashes).
- backend/db.py: RunCost model (run_costs table, total_cost stored as Text for precision, breakdown JSONB) + record_run_cost(); init_db creates indexes ix_run_costs_created_at (DESC) + ix_run_costs_user_id.
- backend/main.py: _record_run_cost_safe() best-effort after BOTH message endpoints; both endpoints capture title usage; PUT /api/config calls admin.bust_key_status_cache() when openrouter_api_key changes.
- backend/admin.py: GET /api/admin/openrouter/key-status (Depends get_current_admin) calls GET https://openrouter.ai/api/v1/key with persisted key; returns usage/limit/limit_remaining/is_free_tier/usage_percent; {configured:false} no key, {configured:true,valid:false} on 401; cache _KEY_STATUS_CACHE keyed BY KEY VALUE, TTL 180s, refresh=true bypass; never leaks key. GET /api/admin/openrouter/cost-summary -> {total_cost,total_tokens,total_runs,last_run,per_model[]}.
- frontend/src/pages/Admin.jsx: new 'OpenRouter' tab (admin-tab-openrouter) — key cards, usage bar, app cost cards, per-model table, Refresh button. frontend/src/api.js: adminApi.openrouterKeyStatus(refresh) + openrouterCostSummary().
ENV NOTE: Postgres is volatile & NOT supervisor-managed. If backend 502/DB-refused: `pg_ctlcluster 15 main start` (or pg_ctl on /var/lib/postgresql/15/main), ensure db llm_council exists, `ALTER USER postgres WITH PASSWORD 'postgres'`, then restart backend.

---
## Rebrand → "AI Delphi Council" + Logos + Terms + How-it-works + Full EN/FR i18n — 2026-09 (branch target: master_herokuVersion_v25/v26)
Verified: testing_agent iter_25 — frontend 100% (all 10 checks). Login-page footer nit fixed after.
1) Rebrand (display-name only): index.html <title>/meta, header, sidebar, welcome, footer, login, terms, legal now show "AI Delphi Council". Code identifiers, TERMS_KEY ('llm_council_terms_accepted_v1'), support email (llmcouncilsupport@africaisoft.africa) unchanged. api.js:2 comment left (not user-facing).
2) Logos: frontend/src/assets/logo-product.jpg (header white chip, welcome, login, terms modal) + logo-africaisoft.jpg (footer "by AfricAIsoft" lockup, href '#'). alt text set; white rounded chips for dark surfaces.
3) Terms of Use: full professional EN+FR in i18n (terms.sections.* 11 sections + contact + dataProtection + legalNotice). Wired into TermsModal (consent gate) and /legal page.
4) How it works: frontend/src/components/HowItWorks.jsx (+ .css) 4 cards Input/Enrich/Process/Output, inline SVG icons (NO lucide-react — not installed here), on welcome empty-state, non-blocking.
5) i18n: react-i18next + i18next + i18next-browser-languagedetector. frontend/src/i18n/{index.js,en.json,fr.json}. BRAND const kept identical both langs. LanguageSwitcher.jsx (EN/FR) in header + login + terms + legal. Persist localStorage key 'app_lang', default browser lang, fallback en, live switch no reload. Imported in main.jsx. Wired t() across: AppHeader, AppFooter, Sidebar, ChatInterface, HowItWorks, CouncilProgress, DocumentPanel, Stage1/2/3, TermsModal, Legal, Login, Credits, Settings (full), Admin (tabs + OpenRouter tab). api.js adminApi unchanged.
NOTE: header nav label "Council" intentionally identical in both languages (brand). No backend changes this task.
ENV: Postgres volatile/not-supervised — restart via `pg_ctlcluster 15 main start` + ALTER USER postgres password 'postgres' + ensure db llm_council + restart backend if 502.

---
## FIX: Heroku servait un build figé périmé — 2026-09 (iter_26, frontend 100%)
Symptôme (déployé Heroku): "no localization, logo didn't change" — page /login montrait encore "LLM Council" + ancien logo balance, alors que l'aperçu Emergent (Vite dev) était correct.
Cause: le repo commite `frontend/dist` (cf .gitignore ligne 21 "frontend/dist is intentionally committed so Heroku serves the built SPA"). Le backend (backend/main.py get_frontend_path) sert frontend/dist. Après édition de frontend/src/*, le dist n'avait jamais été régénéré → Heroku servait l'ancien build (title "frontend", "LLM Council", pas d'i18n).
Correctif:
- Ajout de frontend/.env.production (REACT_APP_BACKEND_URL vide + VITE_BACKEND_URL vide) => build de prod en SAME-ORIGIN (API_BASE=''), comme l'ancien build qui encodait /api. (le .env dev garde l'URL d'aperçu, protégé, inchangé).
- Régénéré frontend/dist via `yarn build`. Nouveau dist: <title>AI Delphi Council</title>, logo-product bundlé, i18n FR/EN ("Bienvenue sur AI Delphi Council", "Comment ça marche"), lien www.africaisoft.africa, AUCUNE URL preview encodée.
Vérif: testing_agent iter_26 a servi le dist (serve -s) à l'URL d'aperçu => 100%, aucun "LLM Council", aucun ancien logo.
ACTION UTILISATEUR: "Save to Github" (pousse le nouveau dist + .env.production) puis REDÉPLOYER cette branche sur Heroku. À CHAQUE futur changement front, il FAUT régénérer frontend/dist avant de pousser (sinon Heroku reste figé).
