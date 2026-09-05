"""Backend tests for OpenRouter key-status + cost-summary admin endpoints,
cache invalidation on key change, and graceful cost aggregation on pipeline failure."""
import os
import json
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


def _session(email, name="QA"):
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
    email = f"TEST_or_{uuid.uuid4().hex[:8]}@example.com"
    return _session(email, "Regular QA")


@pytest.fixture(scope="module")
def key_baseline(admin_client):
    """Snapshot admin's current openrouter_api_key so we can restore after."""
    r = admin_client.get(f"{BASE_URL}/api/admin/settings", timeout=30)
    if r.status_code != 200:
        pytest.skip("admin settings not reachable")
    return r.json().get("openrouter_api_key") or ""


# ============ Auth gating ============
class TestAdminGating:
    def test_key_status_forbidden_for_nonadmin(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:300]}"

    def test_cost_summary_forbidden_for_nonadmin(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/admin/openrouter/cost-summary", timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:300]}"

    def test_key_status_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30)
        assert r.status_code in (401, 403)

    def test_cost_summary_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/openrouter/cost-summary", timeout=30)
        assert r.status_code in (401, 403)


# ============ key-status shape + cache ============
class TestKeyStatusAndCache:
    def _set_key(self, admin_client, key):
        return admin_client.put(f"{BASE_URL}/api/config", json={"openrouter_api_key": key}, timeout=30)

    def test_status_shape_never_leaks_key(self, admin_client, key_baseline):
        # Set a known dummy invalid key
        dummy = f"sk-or-v1-TESTinvalid-{uuid.uuid4().hex[:12]}"
        try:
            assert self._set_key(admin_client, dummy).status_code == 200
            r = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30)
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            # Never leak the key value
            body_text = json.dumps(data)
            assert dummy not in body_text
            assert "openrouter_api_key" not in body_text
            assert data.get("configured") is True
            # Invalid key -> valid=False and error string
            assert data.get("valid") is False
            assert "error" in data
        finally:
            self._set_key(admin_client, key_baseline)

    def test_cache_hit_within_ttl_and_refresh_bypass(self, admin_client, key_baseline):
        dummy = f"sk-or-v1-TESTcache-{uuid.uuid4().hex[:12]}"
        try:
            assert self._set_key(admin_client, dummy).status_code == 200
            # First call primes the cache (cached:false right after key change / miss)
            r1 = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30).json()
            assert r1.get("configured") is True
            assert r1.get("cached") in (False, None)
            # Second call within TTL -> cached:true
            r2 = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30).json()
            assert r2.get("cached") is True, f"expected cached hit, got {r2}"
            # refresh=true bypasses cache
            r3 = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status?refresh=true", timeout=30).json()
            # cached must be false (or absent), and body still consistent
            assert r3.get("cached") in (False, None)
            assert r3.get("configured") is True
        finally:
            self._set_key(admin_client, key_baseline)

    def test_cache_invalidation_on_key_change(self, admin_client, key_baseline):
        """Saving a new key in Settings must bust the cache — next call is not
        served from the previous key's cached entry."""
        k1 = f"sk-or-v1-TESTk1-{uuid.uuid4().hex[:12]}"
        k2 = f"sk-or-v1-TESTk2-{uuid.uuid4().hex[:12]}"
        try:
            assert self._set_key(admin_client, k1).status_code == 200
            r1a = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30).json()
            r1b = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30).json()
            assert r1b.get("cached") is True, r1b
            # Change key -> next call must be a miss
            assert self._set_key(admin_client, k2).status_code == 200
            r2 = admin_client.get(f"{BASE_URL}/api/admin/openrouter/key-status", timeout=30).json()
            assert r2.get("cached") in (False, None), f"cache not invalidated: {r2}"
            assert r2.get("configured") is True
        finally:
            self._set_key(admin_client, key_baseline)


# ============ cost-summary ============
class TestCostSummaryShape:
    def test_shape_and_types(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/openrouter/cost-summary", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("total_cost", "total_tokens", "total_runs", "last_run", "per_model"):
            assert k in d, f"missing key {k} in {d}"
        assert isinstance(d["total_cost"], (int, float))
        assert isinstance(d["total_tokens"], int)
        assert isinstance(d["total_runs"], int)
        assert isinstance(d["per_model"], list)
        # last_run either null or a dict with total_cost etc.
        if d["last_run"] is not None:
            assert isinstance(d["last_run"], dict)


# ============ Graceful cost aggregation on pipeline failure ============
class TestPipelineFailureIsGraceful:
    """Since no valid OPENROUTER_API_KEY is configured, sending a message
    should fail cleanly, refund credits, and NOT crash cost aggregation."""

    def test_stream_error_and_refund_no_traceback(self, admin_client):
        # Admin has admin role — grant self credits via admin API
        me = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=30).json()
        user_id = me["id"]
        # Grant credits
        admin_client.post(f"{BASE_URL}/api/admin/users/{user_id}/credits",
                          json={"amount": 50, "reason": "TEST_pipeline"}, timeout=30)

        # Create conversation
        c = admin_client.post(f"{BASE_URL}/api/conversations", json={}, timeout=30)
        assert c.status_code == 200, c.text[:300]
        conv_id = c.json()["id"]

        # Get cost-summary before
        before = admin_client.get(f"{BASE_URL}/api/admin/openrouter/cost-summary", timeout=30).json()
        runs_before = before["total_runs"]

        # Fire the stream — expect it to end with an 'error' SSE event, refunded:true
        with admin_client.post(
            f"{BASE_URL}/api/conversations/{conv_id}/message/stream",
            json={"content": "TEST_pipeline hello?"},
            stream=True, timeout=180,
        ) as resp:
            # 200 OK is fine because SSE opens successfully; failure is reported inline.
            assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
            saw_error = False
            error_payload = None
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if raw.startswith(":"):  # keep-alive
                    continue
                if raw.startswith("data: "):
                    try:
                        payload = json.loads(raw[6:])
                    except Exception:
                        continue
                    if payload.get("type") == "error":
                        saw_error = True
                        error_payload = payload
                        break
            assert saw_error, "expected an 'error' SSE event because no real OpenRouter key is set"
            assert error_payload.get("refunded") is True, error_payload
            # message must be a string, not a raw traceback dump
            msg = error_payload.get("message", "")
            assert isinstance(msg, str) and msg
            assert "Traceback" not in msg

        # cost-summary must remain queryable (aggregation didn't crash) and total_runs unchanged
        after = admin_client.get(f"{BASE_URL}/api/admin/openrouter/cost-summary", timeout=30).json()
        assert isinstance(after["total_cost"], (int, float))
        assert after["total_runs"] == runs_before, (
            "run_costs should not gain a row when pipeline failed before assistant message"
        )

        # cleanup
        admin_client.delete(f"{BASE_URL}/api/conversations/{conv_id}", timeout=30)
