"""Regression tests for the Stage-2 NameError bug (advanced_config) and the
full SSE council stream reaching stage2_complete -> stage3_complete -> complete.

OpenRouter is NOT configured in this environment, so council.query_models_parallel
and council.query_model are mocked.
"""
import inspect
import json
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

import council  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://streaming-parser-fix.preview.emergentagent.com"
).rstrip("/")
ADMIN_EMAIL = "somecedric@gmail.com"

FAKE_STAGE1 = [
    {"model": "modelA", "response": "Answer from A"},
    {"model": "modelB", "response": "Answer from B"},
]


async def fake_query_models_parallel(models, messages, advanced_config=None, **kwargs):
    """Fake OpenRouter fan-out. Returns a ranking-shaped answer for stage 2."""
    is_ranking = "FINAL RANKING:" in json.dumps(messages)
    out = {}
    for i, m in enumerate(models or ["modelA", "modelB"]):
        if is_ranking:
            content = (
                "Response A is good. Response B is ok.\n\n"
                "FINAL RANKING:\n1. Response A\n2. Response B"
            )
        else:
            content = f"Answer from {m} #{i}"
        out[m] = {"content": content}
    return out


async def fake_query_model(model, messages, advanced_config=None, **kwargs):
    return {"content": "Chairman synthesis"}


@pytest.fixture
def mock_openrouter(monkeypatch):
    monkeypatch.setattr(council, "query_models_parallel", fake_query_models_parallel)
    monkeypatch.setattr(council, "query_model", fake_query_model)
    return True


# ===================== 1. Signature / static checks =====================

class TestSignatures:
    def test_stage2_signature_has_advanced_config(self):
        params = list(inspect.signature(council.stage2_collect_rankings).parameters)
        assert params == ["user_query", "stage1_results", "advanced_config"], params
        default = inspect.signature(council.stage2_collect_rankings).parameters[
            "advanced_config"
        ].default
        assert default is None

    def test_stage2_body_only_uses_local_advanced_config(self):
        src = inspect.getsource(council.stage2_collect_rankings)
        assert "advanced_config=advanced_config" in src
        # advanced_config must not be a free (global) variable -> would be NameError
        assert "advanced_config" not in council.stage2_collect_rankings.__code__.co_names

    def test_all_callers_pass_advanced_config(self):
        run_full_src = inspect.getsource(council.run_full_council)
        assert (
            "stage2_collect_rankings(user_query, stage1_results, advanced_config=advanced_config)"
            in run_full_src
        )
        main_src = open("/app/backend/main.py", encoding="utf-8").read()
        assert (
            "stage2_collect_rankings(query_content, stage1_results, advanced_config=request.advanced)"
            in main_src
        )


# ===================== 2. Stage unit tests (mocked) =====================

class TestStagesMocked:
    @pytest.mark.asyncio
    async def test_stage1_returns_results(self, mock_openrouter):
        res = await council.stage1_collect_responses("Q?", advanced_config={"mode": "openrouter"})
        assert isinstance(res, list) and len(res) >= 1
        assert set(res[0]) == {"model", "response"}

    @pytest.mark.asyncio
    async def test_stage2_with_advanced_config_no_nameerror(self, mock_openrouter):
        result = await council.stage2_collect_rankings(
            "Q?", FAKE_STAGE1, advanced_config={"mode": "openrouter", "throttle": {}}
        )
        assert isinstance(result, tuple) and len(result) == 2
        rankings, label_to_model = result
        assert isinstance(rankings, list) and len(rankings) >= 1
        assert set(rankings[0]) == {"model", "ranking", "parsed_ranking"}
        assert rankings[0]["parsed_ranking"] == ["Response A", "Response B"]
        assert label_to_model == {"Response A": "modelA", "Response B": "modelB"}

    @pytest.mark.asyncio
    async def test_stage2_without_advanced_config(self, mock_openrouter):
        rankings, mapping = await council.stage2_collect_rankings("Q?", FAKE_STAGE1)
        assert rankings and isinstance(mapping, dict)

    @pytest.mark.asyncio
    async def test_stage2_forwards_advanced_config(self, monkeypatch):
        seen = {}

        async def spy(models, messages, advanced_config=None, **kw):
            seen["advanced_config"] = advanced_config
            return await fake_query_models_parallel(models, messages, advanced_config)

        monkeypatch.setattr(council, "query_models_parallel", spy)
        cfg = {"mode": "hybrid", "marker": 42}
        await council.stage2_collect_rankings("Q?", FAKE_STAGE1, advanced_config=cfg)
        assert seen["advanced_config"] == cfg

    @pytest.mark.asyncio
    async def test_stage3_synthesis(self, mock_openrouter):
        rankings, _ = await council.stage2_collect_rankings("Q?", FAKE_STAGE1)
        out = await council.stage3_synthesize_final(
            "Q?", FAKE_STAGE1, rankings, advanced_config={"mode": "openrouter"}
        )
        assert out["response"] == "Chairman synthesis"
        assert out["model"] != "error"

    @pytest.mark.asyncio
    async def test_run_full_council_end_to_end(self, mock_openrouter):
        s1, s2, s3, meta = await council.run_full_council(
            "Q?", advanced_config={"mode": "openrouter"}
        )
        assert s1 and s2
        assert s3["model"] != "error"
        assert "label_to_model" in meta and "aggregate_rankings" in meta
        assert meta["aggregate_rankings"], "aggregate rankings should not be empty"


# ===================== 3. Full SSE stream (in-process, mocked) =====================

def _grant_credits(email: str, amount: int = 1000):
    import subprocess

    subprocess.run(
        [
            "psql",
            "-p",
            "5432",
            "-d",
            "llm_council",
            "-c",
            f"UPDATE users SET credits={amount} WHERE email='{email}';",
        ],
        check=False,
        env={**os.environ, "PGUSER": "postgres", "PGPASSWORD": "postgres", "PGHOST": "localhost"},
        capture_output=True,
    )


class TestSSEStreamMocked:
    @pytest.mark.asyncio
    async def test_stream_reaches_stage2_stage3_complete(self, mock_openrouter):
        """Drive the real ASGI app's SSE endpoint with OpenRouter mocked."""
        import importlib.util

        import httpx

        # Load /app/backend/main.py explicitly (a different /app/main.py shadows it)
        spec = importlib.util.spec_from_file_location(
            "backend_main_under_test", "/app/backend/main.py"
        )
        backend_main = importlib.util.module_from_spec(spec)
        sys.modules["backend_main_under_test"] = backend_main
        spec.loader.exec_module(backend_main)

        transport = httpx.ASGITransport(app=backend_main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            r = await client.post("/api/auth/dev-login", json={"email": ADMIN_EMAIL, "name": "Cedric"})
            assert r.status_code == 200, r.text
            _grant_credits(ADMIN_EMAIL)

            r = await client.post("/api/conversations", json={})
            assert r.status_code in (200, 201), r.text
            conv_id = r.json()["id"]

            events = []
            first_chunk = None
            async with client.stream(
                "POST",
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "What is 2+2?"},
                timeout=120.0,
            ) as resp:
                assert resp.status_code == 200, await resp.aread()
                assert "text/event-stream" in resp.headers.get("content-type", "")
                assert resp.headers.get("x-accel-buffering") == "no"
                buf = ""
                async for chunk in resp.aiter_text():
                    if first_chunk is None:
                        first_chunk = chunk
                    buf += chunk
                    while "\n\n" in buf:
                        raw, buf = buf.split("\n\n", 1)
                        raw = raw.strip()
                        if raw.startswith("data:"):
                            events.append(json.loads(raw[len("data:"):].strip()))
                        elif raw.startswith(":"):
                            events.append({"type": f"comment:{raw}"})

            types = [e["type"] for e in events]
            print("SSE event types:", types)
            assert first_chunk.startswith(": ping"), f"first chunk was {first_chunk!r}"
            assert "error" not in types, [e for e in events if e["type"] == "error"]
            for expected in (
                "stage1_start",
                "stage1_complete",
                "stage2_start",
                "stage2_complete",
                "stage3_start",
                "stage3_complete",
                "complete",
            ):
                assert expected in types, f"missing {expected} in {types}"
            assert types.index("stage2_complete") < types.index("stage3_start")
            assert types[-1] == "complete"

            s2 = next(e for e in events if e["type"] == "stage2_complete")
            assert isinstance(s2["data"], list) and s2["data"]
            assert "label_to_model" in s2["metadata"]
            assert "aggregate_rankings" in s2["metadata"]

            # persistence: assistant message stored with all 3 stages
            r = await client.get(f"/api/conversations/{conv_id}")
            assert r.status_code == 200
            msgs = r.json()["messages"]
            assistant = [m for m in msgs if m.get("role") == "assistant"]
            assert assistant, msgs
            last = assistant[-1]
            assert last.get("stage3", {}).get("response") == "Chairman synthesis"


# ===================== 4. Live regression (public URL, no mocks) =====================

class TestLiveRegression:
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        r = s.post(
            f"{BASE_URL}/api/auth/dev-login",
            json={"email": ADMIN_EMAIL, "name": "Cedric"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert "council_session" in s.cookies.get_dict()
        return s

    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text

    def test_me_and_credits(self, session):
        _grant_credits(ADMIN_EMAIL)
        r = session.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_conversation_create_and_list(self, session):
        r = session.post(f"{BASE_URL}/api/conversations", json={}, timeout=30)
        assert r.status_code in (200, 201), r.text
        conv_id = r.json()["id"]
        r = session.get(f"{BASE_URL}/api/conversations", timeout=30)
        assert r.status_code == 200
        assert any(c["id"] == conv_id for c in r.json())

    def test_stream_opens_with_ping_and_refunds(self, session):
        """No API key -> stage1 fails; verify ping framing + error event + refund."""
        _grant_credits(ADMIN_EMAIL)
        r = session.get(f"{BASE_URL}/api/auth/me", timeout=30)
        before = r.json()["credits"]

        conv = session.post(f"{BASE_URL}/api/conversations", json={}, timeout=30).json()
        events, first = [], None
        with session.post(
            f"{BASE_URL}/api/conversations/{conv['id']}/message/stream",
            json={"content": f"TEST_live_{uuid.uuid4().hex[:6]}"},
            stream=True,
            timeout=180,
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            buf = ""
            for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                if first is None:
                    first = chunk
                buf += chunk
                while "\n\n" in buf:
                    raw, buf = buf.split("\n\n", 1)
                    raw = raw.strip()
                    if raw.startswith("data:"):
                        events.append(json.loads(raw[len("data:"):].strip()))
        types = [e["type"] for e in events]
        print("live SSE types:", types, "first chunk:", repr(first))
        assert first.startswith(": ping"), repr(first)
        assert "stage1_start" in types
        assert "error" in types, types  # no OpenRouter key configured
        err = next(e for e in events if e["type"] == "error")
        assert err.get("refunded") is True
        assert "advanced_config" not in err.get("message", ""), err

        after = session.get(f"{BASE_URL}/api/auth/me", timeout=30).json()["credits"]
        assert after == before, f"credits not refunded: {before} -> {after}"
