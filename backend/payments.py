"""PayPal Checkout (Orders v2) — prepaid credit packs. Server-authoritative."""

import os
import uuid
import base64
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, desc, func

try:
    from .db import SessionLocal, User, CreditTransaction, credit_user
    from .auth import get_current_user
    from . import settings_store
except ImportError:
    from db import SessionLocal, User, CreditTransaction, credit_user
    from auth import get_current_user
    import settings_store

router = APIRouter(prefix="/api/payments", tags=["payments"])

PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
CURRENCY = "CAD"


def _api_base() -> str:
    return "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"


async def _access_token() -> str:
    if not (PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="PayPal non configuré")
    creds = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_api_base()}/v1/oauth2/token",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"PayPal auth failed: {r.text}")
    return r.json()["access_token"]


async def _find_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    packs = await settings_store.get_setting("credit_packs", [])
    for p in packs:
        if p.get("id") == pack_id:
            return p
    return None


@router.get("/config")
async def payments_config():
    return {"client_id": PAYPAL_CLIENT_ID, "currency": CURRENCY, "mode": PAYPAL_MODE}


# ===================== Free discovery pack =====================
# Admin setting `free_discovery` = {enabled, pack_id, max_credits}. Every free
# grant is logged as a CreditTransaction of kind "free_pack", so the per-user
# total is always recomputed from the ledger (no extra table / migration).
FREE_PACK_KIND = "free_pack"


_normalize_free_cfg = settings_store.normalize_free_discovery


async def _free_credits_used(session, user_id) -> int:
    used = await session.scalar(
        select(func.coalesce(func.sum(CreditTransaction.amount), 0))
        .where(CreditTransaction.user_id == user_id, CreditTransaction.kind == FREE_PACK_KIND)
    )
    return int(used or 0)


async def _free_status(user_id) -> Dict[str, Any]:
    cfg = _normalize_free_cfg(await settings_store.get_setting("free_discovery", {}))
    async with SessionLocal() as session:
        used = await _free_credits_used(session, user_id)
    remaining = max(0, cfg["max_credits"] - used)
    return {**cfg, "used": used, "remaining": remaining,
            "available": cfg["enabled"] and remaining > 0}


@router.get("/packs")
async def list_packs(user: User = Depends(get_current_user)):
    packs = await settings_store.get_setting("credit_packs", [])
    free = await _free_status(user.id)
    out = []
    for p in packs:
        item = dict(p)
        if free["available"] and p.get("id") == free["pack_id"]:
            # Credits granted by the next free claim (capped by what is left).
            item["free"] = True
            item["free_credits"] = min(int(p.get("credits", 0) or 0), free["remaining"])
        out.append(item)
    return {"packs": out, "free_discovery": {
        "enabled": free["enabled"], "pack_id": free["pack_id"],
        "max_credits": free["max_credits"], "used": free["used"],
        "remaining": free["remaining"], "available": free["available"],
    }}


@router.post("/free-claim")
async def claim_free_pack(body: dict, user: User = Depends(get_current_user)):
    """Grant the discovery pack for free (no PayPal), within the admin's cap."""
    cfg = _normalize_free_cfg(await settings_store.get_setting("free_discovery", {}))
    pack_id = body.get("pack_id") or cfg["pack_id"]
    if not cfg["enabled"]:
        raise HTTPException(status_code=403, detail="free_pack_disabled")
    if pack_id != cfg["pack_id"]:
        raise HTTPException(status_code=400, detail="pack_not_free")
    pack = await _find_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="pack_not_found")
    async with SessionLocal() as session:
        # Lock the user row so two simultaneous claims cannot exceed the cap.
        await session.execute(select(User.id).where(User.id == user.id).with_for_update())
        used = await _free_credits_used(session, user.id)
        remaining = max(0, cfg["max_credits"] - used)
        grant = min(int(pack.get("credits", 0) or 0), remaining)
        if grant <= 0:
            raise HTTPException(status_code=409, detail="free_quota_reached")
        new_balance = await credit_user(
            session, user.id, grant, FREE_PACK_KIND,
            reason=f"Pack {pack.get('name', pack_id)} gratuit",
        )
        await session.commit()
    return {"status": "completed", "credits": new_balance, "granted": grant,
            "remaining": remaining - grant}


@router.get("/transactions")
async def my_transactions(user: User = Depends(get_current_user)):
    async with SessionLocal() as session:
        rows = (await session.scalars(
            select(CreditTransaction).where(CreditTransaction.user_id == user.id)
            .order_by(desc(CreditTransaction.created_at)).limit(100)
        )).all()
    return {"transactions": [t.public_dict() for t in rows]}


@router.post("/orders")
async def create_order(body: dict, user: User = Depends(get_current_user)):
    pack = await _find_pack(body.get("pack_id", ""))
    if not pack:
        raise HTTPException(status_code=404, detail="pack_not_found")
    value = f"{float(pack['price_cad']):.2f}"  # amount ALWAYS from server settings
    token = await _access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_api_base()}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": pack["id"],
                    "custom_id": f"{user.id}:{pack['id']}",
                    "description": f"LLM Council - Pack {pack['name']}",
                    "amount": {"currency_code": CURRENCY, "value": value},
                }],
            },
        )
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"PayPal order failed: {r.text}")
    return {"order_id": r.json()["id"]}


async def _credit_from_capture(order_id: str, capture: Dict[str, Any]) -> Optional[int]:
    """Credit the account from a captured PayPal order. Idempotent + server-priced."""
    pus = capture.get("purchase_units", [])
    if not pus:
        return None
    pu = pus[0]
    custom_id = pu.get("custom_id") or (pu.get("payments", {}).get("captures", [{}])[0].get("custom_id"))
    if not custom_id or ":" not in custom_id:
        return None
    user_id_str, pack_id = custom_id.split(":", 1)
    pack = await _find_pack(pack_id)
    if not pack:
        return None
    # Verify captured amount matches the server-side pack price.
    caps = pu.get("payments", {}).get("captures", [])
    capture_id = caps[0]["id"] if caps else None
    amount_val = caps[0]["amount"]["value"] if caps else pu.get("amount", {}).get("value")
    if amount_val is None or abs(float(amount_val) - float(pack["price_cad"])) > 0.01:
        return None
    async with SessionLocal() as session:
        new_balance = await credit_user(
            session, uuid.UUID(user_id_str), int(pack["credits"]), "purchase",
            paypal_order_id=order_id, paypal_capture_id=capture_id,
            reason=f"Achat pack {pack['name']}",
        )
        await session.commit()
    return new_balance


@router.post("/orders/{order_id}/capture")
async def capture_order(order_id: str, user: User = Depends(get_current_user)):
    token = await _access_token()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_api_base()}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"PayPal capture failed: {r.text}")
    data = r.json()
    if data.get("status") != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"Order not completed: {data.get('status')}")
    new_balance = await _credit_from_capture(order_id, data)
    if new_balance is None:
        # Duplicate (already credited) or verification issue — return current balance.
        async with SessionLocal() as session:
            fresh = await session.get(User, user.id)
            return {"status": "already_processed", "credits": fresh.credits}
    return {"status": "completed", "credits": new_balance}


@router.post("/webhook")
async def paypal_webhook(request: Request):
    body_bytes = await request.body()
    event = await request.json()
    # Verify webhook signature with PayPal.
    verify_payload = {
        "auth_algo": request.headers.get("paypal-auth-algo"),
        "cert_url": request.headers.get("paypal-cert-url"),
        "transmission_id": request.headers.get("paypal-transmission-id"),
        "transmission_sig": request.headers.get("paypal-transmission-sig"),
        "transmission_time": request.headers.get("paypal-transmission-time"),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    if PAYPAL_WEBHOOK_ID:
        token = await _access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            vr = await client.post(
                f"{_api_base()}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=verify_payload,
            )
        if vr.status_code != 200 or vr.json().get("verification_status") != "SUCCESS":
            raise HTTPException(status_code=400, detail="invalid_signature")

    if event.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
        resource = event.get("resource", {})
        order_id = None
        # supplementary_data links the capture back to its order
        try:
            order_id = resource["supplementary_data"]["related_ids"]["order_id"]
        except Exception:
            order_id = resource.get("id")
        custom_id = resource.get("custom_id")
        capture_id = resource.get("id")
        amount_val = resource.get("amount", {}).get("value")
        if order_id and custom_id and ":" in custom_id:
            fake_pu = {"custom_id": custom_id, "payments": {"captures": [
                {"id": capture_id, "amount": {"value": amount_val}, "custom_id": custom_id}
            ]}}
            await _credit_from_capture(order_id, {"purchase_units": [fake_pu]})
    return {"ok": True}
