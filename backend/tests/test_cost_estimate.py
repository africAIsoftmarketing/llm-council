"""Backend tests for the pre-flight cost estimate endpoint (POST /api/cost/estimate).

Verifies the endpoint returns the correct fields, prices correctly, reflects the
real balance, computes can_afford, returns the user's council selection, debits
NOTHING, and requires authentication.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://cost-preview-flow.preview.emergentagent.com"
).rstrip("/")

ADMIN_EMAIL = "somecedric@gmail.com"


def _new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(email: str) -> requests.Session:
    s = _new_session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email}, timeout=30)
    assert r.status_code == 200, f"dev-login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL)


@pytest.fixture(scope="module")
def user_a():
    return _login(f"TEST_cost_est_{uuid.uuid4().hex[:8]}@example.com")


# ============================ Shape / basics ============================

class TestCostEstimateShape:
    def test_returns_200_with_all_fields(self, user_a):
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in [
            "cost", "balance", "balance_after", "can_afford",
            "council_models", "chairman_model", "has_vision", "cost_type",
        ]:
            assert k in d, f"missing field: {k}"
        assert isinstance(d["council_models"], list)
        assert isinstance(d["cost"], int)
        assert isinstance(d["balance"], int)
        assert isinstance(d["can_afford"], bool)

    def test_default_include_documents_true(self, user_a):
        # Empty body -> include_documents defaults to True and still succeeds.
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={})
        assert r.status_code == 200, r.text

    def test_requires_authentication(self):
        r = requests.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 401


# ============================ Pricing ============================

class TestCostEstimatePricing:
    def test_standard_cost_no_vision(self, admin_session, user_a):
        # Ensure default pricing.
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/request_cost",
            json={"value": {"standard": 10, "vision": 15}},
        )
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["has_vision"] is False
        assert d["cost_type"] == "standard"
        assert d["cost"] == 10

    def test_cost_tracks_admin_pricing(self, admin_session, user_a):
        # Change the standard price and confirm the estimate reflects it.
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/request_cost",
            json={"value": {"standard": 7, "vision": 15}},
        )
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        assert r.json()["cost"] == 7
        # restore default
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/request_cost",
            json={"value": {"standard": 10, "vision": 15}},
        )


# ============================ Balance / can_afford ============================

class TestCostEstimateBalance:
    def test_balance_matches_profile_and_no_debit(self, user_a):
        before = user_a.get(f"{BASE_URL}/api/auth/me").json()["credits"]
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["balance"] == before
        assert d["balance_after"] == before - d["cost"]
        # The endpoint must NOT debit anything.
        after = user_a.get(f"{BASE_URL}/api/auth/me").json()["credits"]
        assert after == before, f"balance changed by estimate: {before} -> {after}"

    def test_cannot_afford_when_zero_credits(self):
        s = _login(f"TEST_broke_{uuid.uuid4().hex[:8]}@example.com")
        r = s.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["balance"] == 0
        assert d["can_afford"] is False
        assert d["balance_after"] == -d["cost"]

    def test_can_afford_when_funded(self, admin_session):
        s = _login(f"TEST_rich_{uuid.uuid4().hex[:8]}@example.com")
        uid = s.get(f"{BASE_URL}/api/auth/me").json()["id"]
        admin_session.post(
            f"{BASE_URL}/api/admin/users/{uid}/credits",
            json={"amount": 100, "reason": "TEST cost estimate"},
        )
        r = s.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["balance"] >= 100
        assert d["can_afford"] is True


# ============================ Council reflection ============================

class TestCostEstimateCouncil:
    def test_council_matches_config(self, user_a):
        cfg = user_a.get(f"{BASE_URL}/api/config/council").json()
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["council_models"] == cfg["council_models"]
        assert d["chairman_model"] == cfg["chairman_model"]

    def test_council_reflects_personal_selection(self, user_a):
        # Save a personal council and confirm the estimate returns it.
        available = user_a.get(f"{BASE_URL}/api/config/council").json()["council_models"]
        if len(available) < 2:
            pytest.skip("not enough models to test personal selection")
        chosen = available[:2]
        r = user_a.put(
            f"{BASE_URL}/api/config/council",
            json={"council_models": chosen, "chairman_model": chosen[0]},
        )
        assert r.status_code == 200, r.text
        try:
            r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["council_models"] == chosen
            assert d["chairman_model"] == chosen[0]
        finally:
            user_a.delete(f"{BASE_URL}/api/config/council")
