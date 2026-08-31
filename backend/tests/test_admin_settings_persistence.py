"""Tests for admin-only settings, API key persistence and council selection persistence.

Covers review items:
- feature 2: admin-only PUT /api/config, /api/config/validate-key, /api/config/advanced
- feature 2: OpenRouter key persisted server-side (app_settings) + inherited by non-admins
- feature 3: council_models / chairman_model persisted in app_settings
"""

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
TEST_KEY = "sk-or-v1-TESTKEY0123456789abcdef0123456789abcdef0123456789abcdef01"


def _login(email, name):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email, "name": name}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"dev-login failed for {email}: {r.status_code} {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def admin_client():
    return _login(ADMIN_EMAIL, "TEST_Admin")


@pytest.fixture(scope="module")
def user_client():
    return _login(USER_EMAIL, "TEST_Bob")


# ===== health =====
class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ===== auth / roles =====
class TestRoles:
    def test_admin_role(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        data = r.json()
        user = data.get("user", data)
        assert user["email"] == ADMIN_EMAIL
        assert user["role"] == "admin"

    def test_user_role(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        user = r.json().get("user", r.json())
        assert user["email"] == USER_EMAIL
        assert user["role"] != "admin"

    def test_config_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/config", timeout=30)
        assert r.status_code in (401, 403)


# ===== admin-only enforcement =====
class TestAdminOnlyEnforcement:
    def test_put_config_non_admin_403(self, user_client):
        r = user_client.put(f"{BASE_URL}/api/config", json={"chairman_model": "openai/gpt-4o"}, timeout=30)
        assert r.status_code == 403, r.text[:300]

    def test_advanced_config_non_admin_403(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/config/advanced", json={"mode": "simple"}, timeout=30)
        assert r.status_code == 403, r.text[:300]

    def test_validate_key_non_admin_403(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/config/validate-key", json={"api_key": TEST_KEY}, timeout=60)
        assert r.status_code == 403, r.text[:300]

    def test_advanced_config_admin_200(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/config/advanced", json={"mode": "simple"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("mode") == "simple"

    def test_validate_key_admin_reachable(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/config/validate-key", json={"api_key": TEST_KEY}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        # invalid key -> valid False
        assert r.json().get("valid") is False


# ===== API key persistence =====
class TestApiKeyPersistence:
    def test_admin_saves_key_and_get_config_masks_it(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/config", json={"openrouter_api_key": TEST_KEY}, timeout=30)
        assert r.status_code == 200, r.text[:300]

        g = admin_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert g.status_code == 200
        cfg = g.json()
        assert cfg["has_api_key"] is True
        masked = cfg.get("openrouter_api_key_masked")
        assert masked and masked.startswith(TEST_KEY[:8]) and masked.endswith(TEST_KEY[-4:])
        assert TEST_KEY not in str(cfg.get("openrouter_api_key", ""))

    def test_non_admin_inherits_key(self, user_client):
        g = user_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert g.status_code == 200
        cfg = g.json()
        assert cfg["has_api_key"] is True
        assert cfg.get("openrouter_api_key_masked")

    def test_key_stored_in_app_settings(self):
        import subprocess
        out = subprocess.run(
            ["su", "postgres", "-c",
             "psql -p 5432 -d llm_council -tAc \"SELECT key FROM app_settings WHERE key='openrouter_api_key';\""],
            capture_output=True, text=True,
        )
        assert "openrouter_api_key" in out.stdout, f"not persisted: {out.stdout} {out.stderr}"

    def test_key_survives_backend_restart(self, admin_client):
        import subprocess, time
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, text=True)
        for _ in range(20):
            time.sleep(2)
            try:
                if requests.get(f"{BASE_URL}/api/health", timeout=10).status_code == 200:
                    break
            except Exception:
                pass
        g = admin_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert g.status_code == 200
        assert g.json()["has_api_key"] is True


# ===== council selection persistence =====
class TestCouncilSelectionPersistence:
    def test_save_and_read_council_selection(self, admin_client):
        models = [m["id"] for m in admin_client.get(f"{BASE_URL}/api/models/available", timeout=30).json()["models"]]
        assert len(models) >= 3
        original = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        orig_council = original["council_models"]
        orig_chairman = original["chairman_model"]

        new_council = models[:3]
        new_chairman = models[1]
        try:
            r = admin_client.put(
                f"{BASE_URL}/api/config",
                json={"council_models": new_council, "chairman_model": new_chairman},
                timeout=30,
            )
            assert r.status_code == 200, r.text[:300]

            g = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json()
            assert g["council_models"] == new_council
            assert g["chairman_model"] == new_chairman

            # non-admin sees the same persisted selection
            u = _login(USER_EMAIL, "TEST_Bob").get(f"{BASE_URL}/api/config", timeout=30).json()
            assert u["council_models"] == new_council
            assert u["chairman_model"] == new_chairman
        finally:
            admin_client.put(
                f"{BASE_URL}/api/config",
                json={"council_models": orig_council, "chairman_model": orig_chairman},
                timeout=30,
            )
