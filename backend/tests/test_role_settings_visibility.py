"""Role-based settings access tests: PUT /api/config field gating + GET has_api_key."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

ADMIN_EMAIL = "somecedric@gmail.com"
USER_EMAIL = "bob@example.com"


def _session(email, name):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email, "name": name}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"dev-login failed for {email}: {r.status_code} {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def admin_client():
    return _session(ADMIN_EMAIL, "Admin QA")


@pytest.fixture(scope="module")
def user_client():
    return _session(USER_EMAIL, "Bob QA")


class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


class TestRoles:
    def test_admin_role(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["role"] == "admin"

    def test_user_role(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["role"] == "user"


class TestConfigGating:
    def test_admin_can_save_api_key(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/config", json={"openrouter_api_key": "sk-or-v1-TESTKEY0000000000000000"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        g = admin_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert g.status_code == 200
        assert g.json().get("has_api_key") is True

    def test_nonadmin_get_config_inherits_key(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("has_api_key") is True
        assert "openrouter_api_key" not in data or not data.get("openrouter_api_key", "").startswith("sk-or")

    def test_nonadmin_api_key_forbidden(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"openrouter_api_key": "sk-or-hack"}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"

    def test_nonadmin_advanced_config_ignored(self, user_client):
        """advanced_config is not a ConfigUpdateRequest field -> silently ignored (200, no change)."""
        r = user_client.put(f"{BASE_URL}/api/config", json={"advanced_config": {"mode": "HACKED"}}, timeout=30)
        assert r.status_code in (200, 403), r.text[:300]
        if r.status_code == 200:
            assert r.json().get("advanced_config", {}).get("mode") != "HACKED"

    def test_nonadmin_lm_studio_urls_forbidden(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"lm_studio_urls": {"a": "http://x"}}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"

    def test_nonadmin_storage_location_gating(self, user_client):
        """Storage Location is hidden from non-admins in the UI; API should also reject it."""
        r = user_client.put(f"{BASE_URL}/api/config", json={"storage_location": "/tmp/TEST_nonadmin_storage"}, timeout=30)
        assert r.status_code == 403, f"storage_location not admin-gated: got {r.status_code}: {r.text[:200]}"

    def test_nonadmin_can_save_council_models(self, user_client):
        cur = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        original = cur.get("council_models") or []
        models = ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"]
        r = user_client.put(f"{BASE_URL}/api/config", json={"council_models": models}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        g = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert set(g.get("council_models") or []) == set(models)
        if original:
            user_client.put(f"{BASE_URL}/api/config", json={"council_models": original}, timeout=60)

    def test_nonadmin_can_save_chairman(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"chairman_model": "openai/gpt-4o-mini"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        g = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert g.get("chairman_model") == "openai/gpt-4o-mini"

    def test_nonadmin_can_save_theme(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"theme": "dark"}, timeout=60)
        assert r.status_code == 200, r.text[:400]

    def test_anonymous_config_put_rejected(self):
        r = requests.put(f"{BASE_URL}/api/config", json={"theme": "dark"}, timeout=30)
        assert r.status_code in (401, 403), f"got {r.status_code}"
