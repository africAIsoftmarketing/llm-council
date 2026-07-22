"""Admin panel endpoints. Every route requires role='admin' (backend-enforced)."""

import uuid
from typing import Optional
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc

try:
    from .db import SessionLocal, User, CreditTransaction, credit_user
    from .auth import get_current_admin
    from . import settings_store
except ImportError:
    from db import SessionLocal, User, CreditTransaction, credit_user
    from auth import get_current_admin
    import settings_store

router = APIRouter(prefix="/api/admin", tags=["admin"])

_MODELS_CACHE = {"ids": None, "ts": 0.0}


async def _openrouter_model_ids():
    """Fetch the public OpenRouter model catalogue (no API key required)."""
    import time
    if _MODELS_CACHE["ids"] and time.time() - _MODELS_CACHE["ts"] < 300:
        return _MODELS_CACHE["ids"]
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://openrouter.ai/api/v1/models")
    if r.status_code != 200:
        return None
    ids = {m["id"] for m in r.json().get("data", [])}
    _MODELS_CACHE["ids"] = ids
    _MODELS_CACHE["ts"] = time.time()
    return ids


# ===================== Models =====================

@router.get("/models")
async def get_models(admin: User = Depends(get_current_admin)):
    return {
        "council_models": await settings_store.get_setting("council_models", []),
        "chairman_model": await settings_store.get_setting("chairman_model", ""),
    }


@router.post("/models")
async def add_model(body: dict, admin: User = Depends(get_current_admin)):
    model_id = (body.get("model_id") or "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id required")
    ids = await _openrouter_model_ids()
    if ids is not None and model_id not in ids:
        raise HTTPException(status_code=400, detail=f"Modèle invalide: '{model_id}' introuvable sur OpenRouter")
    models = list(await settings_store.get_setting("council_models", []))
    if model_id not in models:
        models.append(model_id)
        await settings_store.set_setting("council_models", models, updated_by=admin.id)
    return {"council_models": models}


@router.delete("/models/{model_id:path}")
async def delete_model(model_id: str, admin: User = Depends(get_current_admin)):
    models = list(await settings_store.get_setting("council_models", []))
    if model_id not in models:
        raise HTTPException(status_code=404, detail="model_not_found")
    if len(models) <= 2:
        raise HTTPException(status_code=400, detail="Minimum 2 modèles requis")
    models.remove(model_id)
    await settings_store.set_setting("council_models", models, updated_by=admin.id)
    chairman = await settings_store.get_setting("chairman_model", "")
    if chairman == model_id:
        await settings_store.set_setting("chairman_model", models[0], updated_by=admin.id)
    return {"council_models": models}


@router.put("/chairman")
async def set_chairman(body: dict, admin: User = Depends(get_current_admin)):
    model_id = (body.get("model_id") or "").strip()
    models = await settings_store.get_setting("council_models", [])
    if model_id not in models:
        raise HTTPException(status_code=400, detail="Le chairman doit faire partie des modèles du council")
    await settings_store.set_setting("chairman_model", model_id, updated_by=admin.id)
    return {"chairman_model": model_id}


# ===================== Users =====================

@router.get("/users")
async def list_users(
    admin: User = Depends(get_current_admin),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with SessionLocal() as session:
        stmt = select(User)
        if search:
            stmt = stmt.where(User.email.ilike(f"%{search}%"))
        total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = (await session.scalars(
            stmt.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)
        )).all()
        result = []
        for u in rows:
            req_count = await session.scalar(
                select(func.count()).select_from(CreditTransaction)
                .where(CreditTransaction.user_id == u.id, CreditTransaction.kind == "usage")
            )
            d = u.public_dict()
            d["request_count"] = req_count or 0
            result.append(d)
    return {"users": result, "total": total or 0, "page": page, "page_size": page_size}


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: dict, admin: User = Depends(get_current_admin)):
    async with SessionLocal() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")
        if "is_active" in body:
            user.is_active = bool(body["is_active"])
        if "role" in body and body["role"] in ("user", "admin"):
            user.role = body["role"]
        await session.commit()
        await session.refresh(user)
        return user.public_dict()


@router.post("/users/{user_id}/credits")
async def adjust_credits(user_id: str, body: dict, admin: User = Depends(get_current_admin)):
    amount = int(body.get("amount", 0))
    reason = body.get("reason") or "Ajustement admin"
    if amount == 0:
        raise HTTPException(status_code=400, detail="amount must be non-zero")
    async with SessionLocal() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")
        new_balance = await credit_user(session, user.id, amount, "admin_grant", reason=reason)
        await session.commit()
    return {"credits": new_balance}


# ===================== Settings =====================

@router.get("/settings")
async def get_settings(admin: User = Depends(get_current_admin)):
    return await settings_store.get_all_settings()


@router.put("/settings/{key}")
async def update_setting(key: str, body: dict, admin: User = Depends(get_current_admin)):
    if "value" not in body:
        raise HTTPException(status_code=400, detail="value required")
    await settings_store.set_setting(key, body["value"], updated_by=admin.id)
    return {"key": key, "value": body["value"]}


# ===================== Stats =====================

@router.get("/stats")
async def get_stats(admin: User = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)
    packs = await settings_store.get_setting("credit_packs", [])
    credits_to_price = {int(p["credits"]): float(p["price_cad"]) for p in packs}
    async with SessionLocal() as session:
        purchases = (await session.scalars(
            select(CreditTransaction).where(CreditTransaction.kind == "purchase")
        )).all()
        total_revenue = sum(credits_to_price.get(p.amount, 0.0) for p in purchases)
        credits_purchased = sum(p.amount for p in purchases)
        credits_consumed = await session.scalar(
            select(func.coalesce(func.sum(-CreditTransaction.amount), 0))
            .where(CreditTransaction.kind == "usage")
        )
        active_users = await session.scalar(select(func.count()).where(User.is_active == True))  # noqa: E712
        total_users = await session.scalar(select(func.count()).select_from(User))
        req_7d = await session.scalar(
            select(func.count()).where(CreditTransaction.kind == "usage", CreditTransaction.created_at >= d7)
        )
        req_30d = await session.scalar(
            select(func.count()).where(CreditTransaction.kind == "usage", CreditTransaction.created_at >= d30)
        )
        recent = (await session.scalars(
            select(CreditTransaction).order_by(desc(CreditTransaction.created_at)).limit(50)
        )).all()
        # attach email to recent
        user_ids = {t.user_id for t in recent}
        emails = {}
        if user_ids:
            for u in (await session.scalars(select(User).where(User.id.in_(user_ids)))).all():
                emails[u.id] = u.email
    recent_out = []
    for t in recent:
        d = t.public_dict()
        d["email"] = emails.get(t.user_id)
        recent_out.append(d)
    return {
        "total_revenue_cad": round(total_revenue, 2),
        "credits_purchased": credits_purchased,
        "credits_consumed": credits_consumed or 0,
        "active_users": active_users or 0,
        "total_users": total_users or 0,
        "requests_7d": req_7d or 0,
        "requests_30d": req_30d or 0,
        "recent_transactions": recent_out,
    }
