"""app_settings accessor with a 60s in-memory cache and default seeding.

Settings live in Postgres (table app_settings, JSONB value). config_manager
reads council_models / chairman_model from here so the admin can change them at
runtime with no redeploy.
"""

import time
import asyncio
from typing import Any, Dict, Optional

from sqlalchemy import select

try:
    from .db import SessionLocal, AppSetting
    from . import config as base_config
except ImportError:
    from db import SessionLocal, AppSetting
    import config as base_config

_CACHE: Dict[str, Any] = {}
_CACHE_TS: Dict[str, float] = {}
_TTL = 60.0

DEFAULT_SETTINGS: Dict[str, Any] = {
    "council_models": base_config.COUNCIL_MODELS,
    "chairman_model": base_config.CHAIRMAN_MODEL,
    "credit_packs": [
        {"id": "decouverte", "name": "Découverte", "price_cad": 5, "credits": 50},
        {"id": "standard", "name": "Standard", "price_cad": 15, "credits": 200},
        {"id": "pro", "name": "Pro", "price_cad": 40, "credits": 650},
    ],
    "request_cost": {"standard": 10, "vision": 15},
}


async def seed_defaults():
    """Insert any missing default settings (idempotent)."""
    async with SessionLocal() as session:
        existing = set((await session.scalars(select(AppSetting.key))).all())
        changed = False
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing:
                session.add(AppSetting(key=key, value=value))
                changed = True
        if changed:
            await session.commit()
    _CACHE.clear()
    _CACHE_TS.clear()


async def get_setting(key: str, default: Any = None) -> Any:
    now = time.time()
    if key in _CACHE and (now - _CACHE_TS.get(key, 0)) < _TTL:
        return _CACHE[key]
    async with SessionLocal() as session:
        row = await session.get(AppSetting, key)
        value = row.value if row else DEFAULT_SETTINGS.get(key, default)
    _CACHE[key] = value
    _CACHE_TS[key] = now
    return value


async def set_setting(key: str, value: Any, updated_by=None) -> Any:
    from datetime import datetime, timezone
    async with SessionLocal() as session:
        row = await session.get(AppSetting, key)
        if row:
            row.value = value
            row.updated_at = datetime.now(timezone.utc)
            row.updated_by = updated_by
        else:
            session.add(AppSetting(key=key, value=value, updated_by=updated_by))
        await session.commit()
    _CACHE[key] = value
    _CACHE_TS[key] = time.time()
    _SYNC_CACHE.pop(key, None)
    _SYNC_TS.pop(key, None)
    return value


async def get_all_settings() -> Dict[str, Any]:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(AppSetting))).all()
    out = dict(DEFAULT_SETTINGS)
    for r in rows:
        out[r.key] = r.value
    return out


# ---- Synchronous helper for config_manager (called from sync/council code) ----
# Uses psycopg2 (loop-independent) so it is safe to call from inside the async
# request loop without touching the asyncpg engine (which is loop-bound).
_SYNC_CACHE: Dict[str, Any] = {}
_SYNC_TS: Dict[str, float] = {}


def get_setting_sync(key: str, default: Any = None) -> Any:
    now = time.time()
    if key in _SYNC_CACHE and (now - _SYNC_TS.get(key, 0)) < _TTL:
        return _SYNC_CACHE[key]
    import os
    value = DEFAULT_SETTINGS.get(key, default)
    dsn = os.environ.get("DATABASE_URL", "")
    if dsn:
        try:
            import psycopg2
            conn = psycopg2.connect(dsn, sslmode=os.environ.get("DB_SSLMODE", "require"))
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
                    row = cur.fetchone()
                    if row:
                        value = row[0]
            finally:
                conn.close()
        except Exception:
            pass
    _SYNC_CACHE[key] = value
    _SYNC_TS[key] = now
    return value
