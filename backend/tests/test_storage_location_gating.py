"""Focused tests for the storage_location admin gating fix on PUT /api/config."""
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


@pytest.fixture(scope="module", autouse=True)
def restore_storage(admin_client):
    """Snapshot storage_location before, restore to original after the module."""
    original = admin_client.get(f"{BASE_URL}/api/config", timeout=30).json().get("storage_location") or "data"
    yield original
    r = admin_client.put(f"{BASE_URL}/api/config", json={"storage_location": original}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert admin_client.get(f"{BASE_URL}/api/config", timeout=30).json().get("storage_location") == original


# --- storage_location gating (the applied fix) ---
class TestStorageLocationGating:
    def test_nonadmin_storage_location_403(self, user_client, restore_storage):
        r = user_client.put(f"{BASE_URL}/api/config", json={"storage_location": "/tmp/evil"}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert "detail" in body and "dmin" in body["detail"], body
        # Verify nothing was written
        cfg = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert cfg.get("storage_location") != "/tmp/evil"
        assert cfg.get("storage_location") == restore_storage

    def test_admin_storage_location_200_and_persists(self, admin_client, restore_storage):
        r = admin_client.put(f"{BASE_URL}/api/config", json={"storage_location": "data"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        assert r.json().get("storage_location") == "data"
        g = admin_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert g.status_code == 200
        assert g.json().get("storage_location") == "data"

    def test_nonadmin_mixed_payload_rejected_atomically(self, user_client, restore_storage):
        """Allowed field + admin field in one payload => 403 and allowed field NOT applied."""
        before = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        prev_chairman = before.get("chairman_model")
        r = user_client.put(
            f"{BASE_URL}/api/config",
            json={"chairman_model": "openai/gpt-4o", "storage_location": "/tmp/evil2"},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"
        after = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        assert after.get("storage_location") == restore_storage
        assert after.get("chairman_model") == prev_chairman, "allowed field leaked through a rejected request"

    def test_anonymous_storage_location_rejected(self):
        r = requests.put(f"{BASE_URL}/api/config", json={"storage_location": "/tmp/anon"}, timeout=30)
        assert r.status_code in (401, 403), f"got {r.status_code}: {r.text[:200]}"


# --- non-admin allowed fields regression ---
class TestNonAdminAllowedFields:
    @pytest.mark.parametrize(
        "payload",
        [
            {"council_models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"]},
            {"chairman_model": "openai/gpt-4o-mini"},
            {"theme": "dark"},
        ],
    )
    def test_nonadmin_allowed(self, user_client, payload):
        r = user_client.put(f"{BASE_URL}/api/config", json=payload, timeout=60)
        assert r.status_code == 200, r.text[:400]
        g = user_client.get(f"{BASE_URL}/api/config", timeout=30).json()
        for k, v in payload.items():
            if isinstance(v, list):
                assert set(g.get(k) or []) == set(v)
            else:
                assert g.get(k) == v

    @pytest.mark.parametrize(
        "payload",
        [
            {"openrouter_api_key": "sk-or-v1-HACK"},
            {"lm_studio_urls": {"a": "http://x"}},
        ],
    )
    def test_nonadmin_forbidden(self, user_client, payload):
        r = user_client.put(f"{BASE_URL}/api/config", json=payload, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:300]}"

    def test_nonadmin_get_config_has_api_key(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/config", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("has_api_key") is True
        assert not str(data.get("openrouter_api_key") or "").startswith("sk-or")
