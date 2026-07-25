"""Tests for the catalogue model edit/delete endpoints (Settings picker).

Covers PUT/DELETE /api/models/custom/{model_id:path}:
  - edit with a valid vs invalid OpenRouter id
  - delete from the catalogue
  - cascade of a rename/removal into council_models & chairman_model
  - persistence via settings_store (visible in GET /api/admin/settings)

Self-cleaning: restores the original council_models/chairman_model and removes
any catalogue models it added.
"""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
ADMIN_EMAIL = "somecedric@gmail.com"


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/dev-login", json={"email": email}, timeout=30)
    assert r.status_code == 200, f"dev-login failed: {r.status_code} {r.text[:200]}"
    return s


def _catalogue_ids(s):
    r = s.get(f"{BASE_URL}/api/models/available", timeout=30)
    assert r.status_code == 200
    data = r.json()
    models = data.get("models", data if isinstance(data, list) else [])
    return [m["id"] for m in models]


def _valid_openrouter_ids(exclude, count=2):
    """Pick `count` real OpenRouter model ids not already in the catalogue."""
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=25)
    if r.status_code != 200:
        pytest.skip("OpenRouter catalogue unreachable")
    ids = [m["id"] for m in r.json().get("data", [])]
    picked = [i for i in ids if i not in exclude]
    if len(picked) < count:
        pytest.skip("Not enough OpenRouter ids to test")
    return picked[:count]


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL)


@pytest.fixture(scope="module")
def original_state(admin):
    r = admin.get(f"{BASE_URL}/api/admin/models", timeout=30)
    assert r.status_code == 200
    st = r.json()
    orig_council = list(st["council_models"])
    orig_chair = st["chairman_model"]
    added = []
    yield {"council": orig_council, "chairman": orig_chair, "added": added}
    # teardown: restore council/chairman then remove any added catalogue models
    admin.put(f"{BASE_URL}/api/config", json={"council_models": orig_council, "chairman_model": orig_chair}, timeout=30)
    for mid in added:
        admin.delete(f"{BASE_URL}/api/models/custom/{mid}", timeout=30)


# ============================ Edit ============================

def test_edit_invalid_id_rejected(admin):
    cat = _catalogue_ids(admin)
    target = cat[0]
    r = admin.put(f"{BASE_URL}/api/models/custom/{target}", json={"new_id": "foo/does-not-exist-xyz-9999"}, timeout=30)
    assert r.status_code == 400
    assert "OpenRouter" in r.json()["detail"]


def test_add_edit_cascade_and_persist(admin, original_state):
    cat = set(_catalogue_ids(admin))
    id_a, id_b = _valid_openrouter_ids(exclude=cat, count=2)

    # add id_a to catalogue
    r = admin.post(f"{BASE_URL}/api/models/custom",
                   json={"model_id": id_a, "model_name": "Test A", "provider": "TestProv"}, timeout=30)
    assert r.status_code == 200
    original_state["added"].append(id_b)  # after rename it becomes id_b
    assert id_a in _catalogue_ids(admin)

    # persistence: available_models must be stored in app_settings
    rs = admin.get(f"{BASE_URL}/api/admin/settings", timeout=30)
    assert rs.status_code == 200
    stored_ids = [m["id"] for m in rs.json().get("available_models", [])]
    assert id_a in stored_ids

    # put id_a into the council and make it chairman
    council = list(original_state["council"]) + [id_a]
    admin.put(f"{BASE_URL}/api/config", json={"council_models": council, "chairman_model": id_a}, timeout=30)

    # edit id_a -> id_b (valid) : catalogue + council + chairman must cascade
    r = admin.put(f"{BASE_URL}/api/models/custom/{id_a}",
                  json={"new_id": id_b, "model_name": "Test B"}, timeout=30)
    assert r.status_code == 200, r.text
    cat_after = _catalogue_ids(admin)
    assert id_b in cat_after and id_a not in cat_after

    st = admin.get(f"{BASE_URL}/api/admin/models", timeout=30).json()
    assert id_b in st["council_models"] and id_a not in st["council_models"]
    assert st["chairman_model"] == id_b


def test_delete_non_council_model(admin, original_state):
    cat = set(_catalogue_ids(admin))
    id_c = _valid_openrouter_ids(exclude=cat, count=1)[0]
    admin.post(f"{BASE_URL}/api/models/custom",
               json={"model_id": id_c, "model_name": "Temp C", "provider": "Tmp"}, timeout=30)
    assert id_c in _catalogue_ids(admin)
    r = admin.delete(f"{BASE_URL}/api/models/custom/{id_c}", timeout=30)
    assert r.status_code == 200
    assert id_c not in _catalogue_ids(admin)


def test_delete_council_member_cascades(admin, original_state):
    cat = set(_catalogue_ids(admin))
    id_d = _valid_openrouter_ids(exclude=cat, count=1)[0]
    admin.post(f"{BASE_URL}/api/models/custom",
               json={"model_id": id_d, "model_name": "Temp D", "provider": "Tmp"}, timeout=30)
    # council has original (>=2) + id_d  => removing id_d keeps >=2
    council = list(original_state["council"]) + [id_d]
    admin.put(f"{BASE_URL}/api/config", json={"council_models": council, "chairman_model": id_d}, timeout=30)

    r = admin.delete(f"{BASE_URL}/api/models/custom/{id_d}", timeout=30)
    assert r.status_code == 200
    assert id_d not in _catalogue_ids(admin)
    st = admin.get(f"{BASE_URL}/api/admin/models", timeout=30).json()
    assert id_d not in st["council_models"]
    assert st["chairman_model"] != id_d  # reassigned


def test_delete_below_min_two_refused(admin, original_state):
    cat = set(_catalogue_ids(admin))
    ids = _valid_openrouter_ids(exclude=cat, count=2)
    for mid in ids:
        admin.post(f"{BASE_URL}/api/models/custom",
                   json={"model_id": mid, "model_name": "min", "provider": "Tmp"}, timeout=30)
    original_state["added"].extend(ids)
    # set council to exactly these 2
    admin.put(f"{BASE_URL}/api/config", json={"council_models": ids, "chairman_model": ids[0]}, timeout=30)
    # deleting one (a council member) would drop council to 1 -> refused
    r = admin.delete(f"{BASE_URL}/api/models/custom/{ids[0]}", timeout=30)
    assert r.status_code == 400
    assert "2" in r.json()["detail"]
    # model must still exist in catalogue
    assert ids[0] in _catalogue_ids(admin)


def test_requires_auth(original_state):
    anon = requests.Session()
    r = anon.put(f"{BASE_URL}/api/models/custom/openai/gpt-4o", json={"new_id": "openai/gpt-4o"}, timeout=30)
    assert r.status_code == 401
    r2 = anon.delete(f"{BASE_URL}/api/models/custom/openai/gpt-4o", timeout=30)
    assert r2.status_code == 401
