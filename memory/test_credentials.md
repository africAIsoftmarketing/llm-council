# Test Credentials — LLM Council v9 (Monetization)

## Auth (Google SSO + preview dev-login)
Google OAuth is the production login. GOOGLE_CLIENT_ID/SECRET are NOT yet provided,
so for preview/testing a **dev-login** endpoint is enabled (gated by `DEV_AUTH=1` in
`backend/.env`; set to `0` in production).

- Dev login endpoint: `POST /api/auth/dev-login` with JSON `{"email": "...", "name": "..."}`
  - Sets an httpOnly session cookie (JWT). Use a cookie jar.
- Frontend dev login: `/login` → "Accès développeur (aperçu)" → enter email → "Entrer".

### Accounts
- **Admin**: `somecedric@gmail.com` (in ADMIN_EMAILS → auto role=admin on login)
- **Normal user**: any other email, e.g. `bob@example.com` (role=user)

## Database
- PostgreSQL (local, supervisor-managed): `postgresql://postgres:postgres@localhost:5432/llm_council`
- Tables: users, credit_transactions, app_settings, conversations

## PayPal (sandbox)
- Configured in backend/.env (PAYPAL_CLIENT_ID/SECRET/WEBHOOK_ID, PAYPAL_MODE=sandbox)
- Order creation + capture verified server-side. Smart Buttons render in a real browser
  (blocked in the headless automation environment only).

## OpenRouter
- No OPENROUTER_API_KEY provided → the actual 3-stage council pipeline cannot execute.
  Sending a message debits credits, the pipeline fails, and credits are auto-refunded.

## Default pricing (editable in Admin → Tarification)
- Packs: Découverte 5 CAD/50, Standard 15 CAD/200, Pro 40 CAD/650
- Cost: standard 10 credits, vision 15 credits
