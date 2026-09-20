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
        # Ensure default consumption rate.
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 500.0}
        )
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["has_vision"] is False
        assert d["cost_type"] == "standard"
        # Cost is dynamic and composition-based; it must be a positive integer.
        assert isinstance(d["cost"], int) and d["cost"] > 0
        # The dynamic pricing block must be present with a coherent pipeline size.
        assert "pricing" in d
        n = len(d["council_models"])
        assert d["pricing"]["total_api_calls"] == (2 * n) + 2
        assert d["pricing"]["estimated_usd"] > 0

    def test_cost_tracks_admin_pricing(self, admin_session, user_a):
        # The admin knob is now credits_per_usd (consumption rate). Doubling it must
        # increase the credits charged for the same council composition.
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 500.0}
        )
        low = user_a.post(
            f"{BASE_URL}/api/cost/estimate", json={"include_documents": False}
        ).json()["cost"]

        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 1000.0}
        )
        high = user_a.post(
            f"{BASE_URL}/api/cost/estimate", json={"include_documents": False}
        ).json()["cost"]
        assert high > low
        # restore default
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 500.0}
        )

# ============================ v34 consistency: cost == sum(per_model_credits) ============================

class TestCostEqualsSumPerModel:
    def test_cost_equals_sum_of_per_model_credits_default(self, admin_session, user_a):
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 500.0}
        )
        r = user_a.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        pm = d["pricing"]["per_model_credits"]
        assert isinstance(pm, list) and len(pm) > 0
        # each entry has model + integer credits
        for entry in pm:
            assert "model" in entry and "credits" in entry
            assert isinstance(entry["credits"], int) and entry["credits"] >= 0
        total = sum(m["credits"] for m in pm)
        # v34 rule: top-level cost equals sum of per-model credits (floored by minimum)
        assert d["cost"] == total, f"cost={d['cost']} sum(per_model)={total}"

    def test_cost_equals_sum_under_multiple_rates(self, admin_session, user_a):
        for rate in (500.0, 1000.0, 250.0):
            admin_session.put(
                f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": rate}
            )
            d = user_a.post(
                f"{BASE_URL}/api/cost/estimate", json={"include_documents": False}
            ).json()
            total = sum(m["credits"] for m in d["pricing"]["per_model_credits"])
            assert d["cost"] == total, f"rate={rate} cost={d['cost']} sum={total}"
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/credits_per_usd", json={"value": 500.0}
        )

    def test_message_402_required_matches_estimate_cost(self, admin_session):
        # Zero-credit user should get 402, and detail.required must equal /api/cost/estimate cost
        # which itself must equal sum(per_model_credits).
        s = _login(f"TEST_broke_debit_{uuid.uuid4().hex[:8]}@example.com")
        est = s.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False}).json()
        assert est["balance"] == 0
        est_cost = est["cost"]
        sum_pm = sum(m["credits"] for m in est["pricing"]["per_model_credits"])
        assert est_cost == sum_pm

        # Create a conversation and send a message
        conv = s.post(f"{BASE_URL}/api/conversations", json={"title": "TEST_v34"})
        assert conv.status_code in (200, 201), conv.text
        cid = conv.json()["id"]
        r = s.post(
            f"{BASE_URL}/api/conversations/{cid}/message",
            json={"content": "hello"},
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
        detail = r.json().get("detail")
        # detail can be dict or string; handle both
        if isinstance(detail, dict):
            required = detail.get("required")
        else:
            required = None
        assert required == est_cost, f"required={required} estimate cost={est_cost}"



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
            json={"amount": 100000, "reason": "TEST cost estimate"},
        )
        r = s.post(f"{BASE_URL}/api/cost/estimate", json={"include_documents": False})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["balance"] >= 100000
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
