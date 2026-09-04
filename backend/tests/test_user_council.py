"""Per-user council selection tests: GET/PUT/DELETE /api/config/council + /api/config overlay & isolation."""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

ADMIN_EMAIL = "somecedric@gmail.com"

GLOBAL_MODELS = ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"]
GLOBAL_CHAIRMAN = "openai/gpt-4o-mini"


def _session(email, name="QA User"):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email, "name": name}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"dev-login failed for {email}: {r.status_code} {r.text[:300]}")
    return s


def _fresh_user_client():
    email = f"TEST_council_{uuid.uuid4().hex[:8]}@example.com"
    return _session(email, "Fresh QA"), email


@pytest.fixture(scope="module")
def admin_client():
    return _session(ADMIN_EMAIL, "Admin QA")


@pytest.fixture(scope="module", autouse=True)
def global_council(admin_client):
    """Ensure a known GLOBAL council as admin; restore afterwards."""
    before = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
    r = admin_client.put(f"{BASE_URL}/api/config", json={
        "council_models": GLOBAL_MODELS, "chairman_model": GLOBAL_CHAIRMAN}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    yield {"council_models": GLOBAL_MODELS, "chairman_model": GLOBAL_CHAIRMAN}
    admin_client.put(f"{BASE_URL}/api/config", json={
        "council_models": before.get("council_models") or GLOBAL_MODELS,
        "chairman_model": before.get("chairman_model") or GLOBAL_CHAIRMAN}, timeout=60)


@pytest.fixture
def user_client():
    """Fresh non-admin per test; resets its council at teardown."""
    client, email = _fresh_user_client()
    yield client
    client.delete(f"{BASE_URL}/api/config/council", timeout=30)


# --- Health ---
class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# --- GET /api/config/council ---
class TestGetUserCouncil:
    def test_fresh_nonadmin_gets_global_default(self, user_client, global_council):
        r = user_client.get(f"{BASE_URL}/api/config/council", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("council_models", "chairman_model", "is_custom",
                  "default_council_models", "default_chairman_model"):
            assert k in d, f"missing key {k} in {d}"
        assert d["is_custom"] is False
        assert d["council_models"] == global_council["council_models"]
        assert d["chairman_model"] == global_council["chairman_model"]
        assert d["default_council_models"] == global_council["council_models"]
        assert d["default_chairman_model"] == global_council["chairman_model"]

    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/config/council", timeout=30)
        assert r.status_code in (401, 403), r.status_code


# --- PUT /api/config/council validation ---
class TestPutValidation:
    def test_rejects_fewer_than_two_models(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config/council", json={
            "council_models": ["openai/gpt-4o-mini"], "chairman_model": "openai/gpt-4o-mini"}, timeout=30)
        assert r.status_code == 400, r.text[:300]
        assert "2" in str(r.json().get("detail", ""))
        # no side effect
        g = user_client.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["is_custom"] is False

    def test_rejects_empty_models(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config/council", json={"council_models": []}, timeout=30)
        assert r.status_code == 400, r.text[:300]

    def test_rejects_chairman_not_in_council(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config/council", json={
            "council_models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
            "chairman_model": "google/gemini-2.0-flash-001"}, timeout=30)
        assert r.status_code == 400, r.text[:300]
        assert "chairman" in str(r.json().get("detail", "")).lower()
        g = user_client.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["is_custom"] is False

    def test_missing_chairman_defaults_to_first(self, user_client):
        models = ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"]
        r = user_client.put(f"{BASE_URL}/api/config/council", json={"council_models": models}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["chairman_model"] == models[0]
        g = user_client.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["chairman_model"] == models[0]
        assert g["is_custom"] is True


# --- PUT persistence + overlay ---
class TestPersistenceAndOverlay:
    def test_save_persists_and_overlays_config(self, user_client, global_council):
        models = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"]
        chairman = "meta-llama/llama-3.3-70b-instruct"
        r = user_client.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models, "chairman_model": chairman}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["council_models"] == models
        assert body["chairman_model"] == chairman
        assert body["is_custom"] is True

        g = user_client.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["council_models"] == models
        assert g["chairman_model"] == chairman
        assert g["is_custom"] is True
        # defaults still point at the global council
        assert g["default_council_models"] == global_council["council_models"]
        assert g["default_chairman_model"] == global_council["chairman_model"]

        # /api/config overlay for non-admin
        cfg = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg["council_models"] == models
        assert cfg["chairman_model"] == chairman

    def test_persists_across_new_session(self, global_council):
        email = f"TEST_council_{uuid.uuid4().hex[:8]}@example.com"
        c1 = _session(email, "Persist QA")
        models = ["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"]
        assert c1.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models, "chairman_model": models[1]}, timeout=30).status_code == 200
        c2 = _session(email, "Persist QA")  # new cookie/session, same user
        g = c2.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["council_models"] == models
        assert g["chairman_model"] == models[1]
        assert g["is_custom"] is True
        c2.delete(f"{BASE_URL}/api/config/council", timeout=30)


# --- DELETE reset ---
class TestReset:
    def test_delete_resets_to_global(self, user_client, global_council):
        models = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"]
        assert user_client.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models, "chairman_model": models[0]}, timeout=30).status_code == 200
        d = user_client.delete(f"{BASE_URL}/api/config/council", timeout=30)
        assert d.status_code == 200, d.text[:300]
        body = d.json()
        assert body["is_custom"] is False
        assert body["council_models"] == global_council["council_models"]
        assert body["chairman_model"] == global_council["chairman_model"]

        g = user_client.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["is_custom"] is False
        assert g["council_models"] == global_council["council_models"]

        cfg = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg["council_models"] == global_council["council_models"]
        assert cfg["chairman_model"] == global_council["chairman_model"]

    def test_delete_idempotent_on_fresh_user(self, user_client):
        d = user_client.delete(f"{BASE_URL}/api/config/council", timeout=30)
        assert d.status_code == 200, d.text[:300]
        assert d.json()["is_custom"] is False


# --- Isolation ---
class TestIsolation:
    def test_two_nonadmins_independent(self, global_council):
        a, _ = _fresh_user_client()
        b, _ = _fresh_user_client()
        models_a = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"]
        assert a.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models_a, "chairman_model": models_a[0]}, timeout=30).status_code == 200
        gb = b.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert gb["is_custom"] is False
        assert gb["council_models"] == global_council["council_models"]

        models_b = ["openai/gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct"]
        assert b.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models_b, "chairman_model": models_b[1]}, timeout=30).status_code == 200
        ga = a.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert ga["council_models"] == models_a
        assert ga["chairman_model"] == models_a[0]
        a.delete(f"{BASE_URL}/api/config/council", timeout=30)
        b.delete(f"{BASE_URL}/api/config/council", timeout=30)

    def test_admin_config_unaffected_by_user_council(self, admin_client, global_council):
        u, _ = _fresh_user_client()
        models = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"]
        assert u.put(f"{BASE_URL}/api/config/council", json={
            "council_models": models, "chairman_model": models[0]}, timeout=30).status_code == 200
        time.sleep(0.3)
        cfg = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg["council_models"] == global_council["council_models"]
        assert cfg["chairman_model"] == global_council["chairman_model"]
        u.delete(f"{BASE_URL}/api/config/council", timeout=30)

    def test_global_default_unchanged_in_settings(self, admin_client, global_council):
        """A user's PUT /api/config/council must not touch the global council_models."""
        u, _ = _fresh_user_client()
        u.put(f"{BASE_URL}/api/config/council", json={
            "council_models": ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"],
            "chairman_model": "google/gemini-2.0-flash-001"}, timeout=30)
        g = u.get(f"{BASE_URL}/api/config/council", timeout=30).json()
        assert g["default_council_models"] == global_council["council_models"]
        cfg = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg["council_models"] == global_council["council_models"]
        u.delete(f"{BASE_URL}/api/config/council", timeout=30)


# --- Admin-only gating still intact on PUT /api/config ---
class TestAdminGating:
    def test_nonadmin_api_key_forbidden(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={
            "openrouter_api_key": "sk-or-v1-SHOULDNOTAPPLY0000000"}, timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:300]}"

    def test_nonadmin_lm_studio_urls_forbidden(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"lm_studio_urls": {"model_1": "http://x:1234"}}, timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:300]}"

    def test_admin_global_put_still_works(self, admin_client, global_council):
        r = admin_client.put(f"{BASE_URL}/api/config", json={
            "council_models": global_council["council_models"],
            "chairman_model": global_council["chairman_model"]}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        cfg = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg["council_models"] == global_council["council_models"]
