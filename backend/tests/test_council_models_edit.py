"""Tests for Council Models edit/delete persistence via PUT /api/config.

Verifies that PUT /api/config mirrors council_models & chairman_model into
app_settings (settings_store), so admin API GET /api/admin/models reflects
the edits (this is what the live council pipeline reads).
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "somecedric@gmail.com"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": ADMIN_EMAIL})
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def original_state(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/models")
    assert r.status_code == 200
    data = r.json()
    return {
        "council_models": list(data.get("council_models", [])),
        "chairman_model": data.get("chairman_model", ""),
    }


def test_get_admin_models_ok(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/models")
    assert r.status_code == 200
    data = r.json()
    assert "council_models" in data
    assert isinstance(data["council_models"], list)
    assert len(data["council_models"]) >= 1


def test_get_config_ok(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/config")
    assert r.status_code == 200
    data = r.json()
    assert "council_models" in data
    assert "chairman_model" in data


def test_edit_council_models_persists_to_app_settings(admin_session, original_state):
    # Simulate the frontend "Save Council" click: PUT /api/config with edited list
    edited = list(original_state["council_models"])
    # Replace first entry with a new OpenRouter id (edit flow)
    old_first = edited[0]
    new_id = "openai/gpt-4o-mini-TEST"
    # Ensure new_id not already there
    edited = [new_id if x == old_first else x for x in edited if x != new_id]
    if new_id not in edited:
        edited[0] = new_id
    chairman = new_id  # also test chairman mirror

    r = admin_session.put(
        f"{BASE_URL}/api/config",
        json={"council_models": edited, "chairman_model": chairman},
    )
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["council_models"] == edited
    assert cfg["chairman_model"] == chairman

    # Now verify app_settings mirror via admin endpoint (live source of truth)
    r2 = admin_session.get(f"{BASE_URL}/api/admin/models")
    assert r2.status_code == 200
    admin_data = r2.json()
    assert new_id in admin_data["council_models"], (
        f"edited id not mirrored: {admin_data['council_models']}"
    )
    assert old_first not in admin_data["council_models"], (
        f"old id still present in app_settings: {admin_data['council_models']}"
    )
    assert admin_data["chairman_model"] == chairman

    # GET /api/config also reflects change
    r3 = admin_session.get(f"{BASE_URL}/api/config")
    assert r3.status_code == 200
    assert new_id in r3.json()["council_models"]


def test_delete_council_model_persists(admin_session):
    # Current list from admin (post-edit)
    r = admin_session.get(f"{BASE_URL}/api/admin/models")
    current = list(r.json()["council_models"])
    assert len(current) >= 2, "need >=2 to test delete"
    to_remove = current[-1]
    remaining = [m for m in current if m != to_remove]

    r2 = admin_session.put(
        f"{BASE_URL}/api/config",
        json={"council_models": remaining, "chairman_model": remaining[0]},
    )
    assert r2.status_code == 200
    assert to_remove not in r2.json()["council_models"]

    # Verify persistence in app_settings
    r3 = admin_session.get(f"{BASE_URL}/api/admin/models")
    assert to_remove not in r3.json()["council_models"]
    assert r3.json()["council_models"] == remaining


def test_restore_original_state(admin_session, original_state):
    # Cleanup: restore original council_models & chairman
    r = admin_session.put(
        f"{BASE_URL}/api/config",
        json={
            "council_models": original_state["council_models"],
            "chairman_model": original_state["chairman_model"],
        },
    )
    assert r.status_code == 200
    r2 = admin_session.get(f"{BASE_URL}/api/admin/models")
    assert r2.json()["council_models"] == original_state["council_models"]
    assert r2.json()["chairman_model"] == original_state["chairman_model"]


def test_anonymous_me_401():
    r = requests.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 401
