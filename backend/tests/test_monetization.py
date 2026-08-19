"""Comprehensive backend tests for LLM Council v9 monetization layer.

Covers: dev-login auth, credits gate/402, admin grants, conversation ownership,
RBAC, admin models validation, admin pricing settings, PayPal order creation,
admin stats, and refund on pipeline failure.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://streaming-parser-fix.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "somecedric@gmail.com"
USER_EMAIL_A = f"TEST_alice_{uuid.uuid4().hex[:8]}@example.com"
USER_EMAIL_B = f"TEST_bob_{uuid.uuid4().hex[:8]}@example.com"


def _new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(email: str) -> requests.Session:
    s = _new_session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email}, timeout=30)
    assert r.status_code == 200, f"dev-login failed for {email}: {r.status_code} {r.text}"
    assert "council_session" in s.cookies.get_dict(), "session cookie missing"
    return s


# ============================ Fixtures ============================

@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL)


@pytest.fixture(scope="module")
def user_a():
    return _login(USER_EMAIL_A)


@pytest.fixture(scope="module")
def user_b():
    return _login(USER_EMAIL_B)


# ============================ Auth ============================

class TestAuth:
    def test_dev_login_creates_user_zero_credits(self):
        email = f"TEST_fresh_{uuid.uuid4().hex[:8]}@example.com"
        s = _new_session()
        r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email})
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == email.lower()
        assert data["role"] == "user"
        assert data["credits"] == 0
        assert "id" in data

    def test_admin_email_becomes_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"

    def test_me_without_cookie_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401

    def test_me_with_cookie_returns_profile(self, user_a):
        r = user_a.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == USER_EMAIL_A.lower()


# ============================ Credits gate / 402 ============================

class TestCreditsGate:
    def test_zero_credits_returns_402(self, user_a):
        # create conversation
        r = user_a.post(f"{BASE_URL}/api/conversations", json={})
        assert r.status_code == 200, r.text
        conv_id = r.json()["id"]

        r = user_a.post(
            f"{BASE_URL}/api/conversations/{conv_id}/message",
            json={"content": "hello", "include_documents": False},
        )
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", {})
        assert detail.get("error") == "insufficient_credits"
        assert detail.get("required") == 10
        assert detail.get("balance") == 0


# ============================ Admin grant + Stats ============================

class TestAdminGrant:
    def test_admin_grants_credits_and_persist(self, admin_session, user_a):
        # get user_a id
        r = user_a.get(f"{BASE_URL}/api/auth/me")
        uid = r.json()["id"]

        r = admin_session.post(
            f"{BASE_URL}/api/admin/users/{uid}/credits",
            json={"amount": 100, "reason": "TEST grant"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["credits"] >= 100

        r = user_a.get(f"{BASE_URL}/api/auth/me")
        assert r.json()["credits"] >= 100


# ============================ RBAC ============================

class TestRBAC:
    def test_non_admin_forbidden_on_admin_users(self, user_b):
        r = user_b.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 403

    def test_admin_can_list_users(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/users")
        assert r.status_code == 200
        assert "users" in r.json()


# ============================ Conversation ownership ============================

class TestOwnership:
    def test_user_cannot_access_others_conversation(self, user_a, user_b):
        r = user_a.post(f"{BASE_URL}/api/conversations", json={})
        assert r.status_code == 200
        conv_id = r.json()["id"]

        r = user_b.get(f"{BASE_URL}/api/conversations/{conv_id}")
        assert r.status_code == 404

    def test_list_only_shows_own_conversations(self, user_a, user_b):
        # user_a creates
        r = user_a.post(f"{BASE_URL}/api/conversations", json={})
        cid_a = r.json()["id"]
        # user_b list should not include cid_a
        r = user_b.get(f"{BASE_URL}/api/conversations")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert cid_a not in ids


# ============================ Admin models ============================

class TestAdminModels:
    def test_get_models(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/models")
        assert r.status_code == 200
        d = r.json()
        assert "council_models" in d and "chairman_model" in d
        assert isinstance(d["council_models"], list)

    def test_add_invalid_model_rejected(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/models",
            json={"model_id": "foo/does-not-exist-xyz"},
        )
        assert r.status_code == 400, r.text

    def test_delete_below_minimum_rejected(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/models")
        models = r.json()["council_models"]
        if len(models) <= 2:
            # already at minimum -> delete any should return 400
            m = models[0]
            r = admin_session.delete(f"{BASE_URL}/api/admin/models/{m}")
            assert r.status_code == 400
        else:
            # delete extras until 2 remain, then attempt to go below
            while len(models) > 2:
                m = models[-1]
                r = admin_session.delete(f"{BASE_URL}/api/admin/models/{m}")
                assert r.status_code == 200
                models = r.json()["council_models"]
            r = admin_session.delete(f"{BASE_URL}/api/admin/models/{models[0]}")
            assert r.status_code == 400

    def test_set_chairman(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/models")
        models = r.json()["council_models"]
        assert len(models) >= 2
        target = models[0]
        r = admin_session.put(
            f"{BASE_URL}/api/admin/chairman", json={"model_id": target}
        )
        assert r.status_code == 200
        assert r.json()["chairman_model"] == target


# ============================ Admin pricing ============================

class TestAdminPricing:
    def test_update_credit_packs_persists(self, admin_session, user_a):
        new_packs = [
            {"id": "decouverte", "name": "Découverte", "price_cad": 5, "credits": 50},
            {"id": "standard", "name": "Standard", "price_cad": 15, "credits": 200},
            {"id": "pro", "name": "Pro", "price_cad": 40, "credits": 650},
        ]
        r = admin_session.put(
            f"{BASE_URL}/api/admin/settings/credit_packs",
            json={"value": new_packs},
        )
        assert r.status_code == 200

        r = user_a.get(f"{BASE_URL}/api/payments/packs")
        assert r.status_code == 200
        packs = r.json()["packs"]
        assert any(p["id"] == "pro" and p["credits"] == 650 for p in packs)

    def test_update_request_cost_changes_402_required(self, admin_session):
        # set an unusual cost
        r = admin_session.put(
            f"{BASE_URL}/api/admin/settings/request_cost",
            json={"value": {"standard": 7, "vision": 15}},
        )
        assert r.status_code == 200

        # new user (0 credits), try message
        fresh_email = f"TEST_cost_{uuid.uuid4().hex[:8]}@example.com"
        s = _login(fresh_email)
        r = s.post(f"{BASE_URL}/api/conversations", json={})
        cid = r.json()["id"]

        # wait for cache TTL to be safe? settings cache is 60s. set_setting invalidates cache immediately.
        time.sleep(1)
        r = s.post(
            f"{BASE_URL}/api/conversations/{cid}/message",
            json={"content": "hi", "include_documents": False},
        )
        assert r.status_code == 402
        assert r.json()["detail"]["required"] == 7

        # restore default
        admin_session.put(
            f"{BASE_URL}/api/admin/settings/request_cost",
            json={"value": {"standard": 10, "vision": 15}},
        )


# ============================ Payments ============================

class TestPayments:
    def test_config(self):
        r = requests.get(f"{BASE_URL}/api/payments/config")
        assert r.status_code == 200
        d = r.json()
        assert d["currency"] == "CAD"
        assert d["mode"] in ("sandbox", "live")
        assert d["client_id"]

    def test_create_order(self, user_a):
        r = user_a.post(
            f"{BASE_URL}/api/payments/orders",
            json={"pack_id": "decouverte"},
        )
        assert r.status_code == 200, r.text
        assert "order_id" in r.json()
        assert len(r.json()["order_id"]) > 5

    def test_create_order_invalid_pack(self, user_a):
        r = user_a.post(
            f"{BASE_URL}/api/payments/orders",
            json={"pack_id": "nonexistent"},
        )
        assert r.status_code == 404


# ============================ Admin stats ============================

class TestAdminStats:
    def test_stats_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200
        d = r.json()
        for k in [
            "total_revenue_cad", "credits_purchased", "credits_consumed",
            "active_users", "requests_7d", "requests_30d", "recent_transactions",
        ]:
            assert k in d, f"missing key: {k}"
        assert isinstance(d["recent_transactions"], list)


# ============================ Refund on pipeline failure ============================

class TestRefund:
    def test_refund_on_pipeline_failure(self, admin_session, user_a):
        # get current balance
        me = user_a.get(f"{BASE_URL}/api/auth/me").json()
        uid = me["id"]
        # ensure enough credits (grant if needed)
        if me["credits"] < 20:
            admin_session.post(
                f"{BASE_URL}/api/admin/users/{uid}/credits",
                json={"amount": 100, "reason": "TEST refund setup"},
            )
            me = user_a.get(f"{BASE_URL}/api/auth/me").json()
        pre_balance = me["credits"]

        r = user_a.post(f"{BASE_URL}/api/conversations", json={})
        cid = r.json()["id"]

        # non-stream: pipeline will fail (no OPENROUTER_API_KEY) -> 502 + refund
        r = user_a.post(
            f"{BASE_URL}/api/conversations/{cid}/message",
            json={"content": "trigger pipeline failure", "include_documents": False},
            timeout=180,
        )
        # Must NOT be 402 (we have credits). Should be 502 (pipeline failed) or 200 if it somehow succeeds.
        assert r.status_code in (502, 500, 200), f"unexpected status: {r.status_code} {r.text}"

        # allow a brief moment for refund commit
        time.sleep(1)
        post_balance = user_a.get(f"{BASE_URL}/api/auth/me").json()["credits"]

        if r.status_code == 200:
            # pipeline miraculously succeeded — credits should be debited
            assert post_balance == pre_balance - 10
        else:
            # Refund path: balance should be back to pre_balance
            assert post_balance == pre_balance, f"credits not refunded: pre={pre_balance} post={post_balance}"

        # verify a refund transaction was written
        r = user_a.get(f"{BASE_URL}/api/payments/transactions")
        assert r.status_code == 200
        txs = r.json()["transactions"]
        if post_balance == pre_balance and r.status_code != 200:
            assert any(t["kind"] == "refund" for t in txs), "no refund tx recorded"


# ============================ Persistence sanity ============================

class TestPersistence:
    def test_user_persists_across_login(self):
        email = f"TEST_persist_{uuid.uuid4().hex[:8]}@example.com"
        s1 = _login(email)
        uid1 = s1.get(f"{BASE_URL}/api/auth/me").json()["id"]
        # new session
        s2 = _login(email)
        uid2 = s2.get(f"{BASE_URL}/api/auth/me").json()["id"]
        assert uid1 == uid2
