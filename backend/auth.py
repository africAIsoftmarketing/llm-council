"""Google SSO (authlib) + JWT session cookie + auth dependencies.

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, Request, Response, HTTPException, Depends, Body
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select

try:
    from .db import SessionLocal, User
except ImportError:
    from db import SessionLocal, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALG = "HS256"
JWT_TTL_DAYS = 7
COOKIE_NAME = "council_session"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
DEV_AUTH = os.environ.get("DEV_AUTH", "0") == "1"

oauth = OAuth()
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _make_jwt(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _set_session_cookie(response: Response, token: str):
    secure = os.environ.get("COOKIE_SECURE", "1") == "1"
    response.set_cookie(
        key=COOKIE_NAME, value=token, httponly=True, secure=secure,
        samesite="lax", max_age=JWT_TTL_DAYS * 24 * 3600, path="/",
    )


async def _upsert_user(google_sub: str, email: str, name: Optional[str], avatar: Optional[str]) -> User:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.google_sub == google_sub))
        if user is None:
            user = await session.scalar(select(User).where(User.email == email))
        is_admin_email = email.lower() in ADMIN_EMAILS
        if user is None:
            user = User(
                google_sub=google_sub, email=email, display_name=name, avatar_url=avatar,
                role="admin" if is_admin_email else "user", is_active=True, credits=0,
            )
            session.add(user)
        else:
            user.google_sub = google_sub
            user.display_name = name or user.display_name
            user.avatar_url = avatar or user.avatar_url
            if is_admin_email and user.role != "admin":
                user.role = "admin"
            if not user.is_active:
                raise HTTPException(status_code=403, detail="account_disabled")
        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)
        return user


@router.get("/login")
async def login(request: Request):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="Google OAuth non configuré (GOOGLE_CLIENT_ID manquant)")
    redirect_uri = _public_base_url(request) + "/api/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")
    userinfo = token.get("userinfo") or {}
    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="No user info from Google")
    try:
        user = await _upsert_user(google_sub, email, userinfo.get("name"), userinfo.get("picture"))
    except HTTPException:
        return RedirectResponse(url="/login?error=account_disabled")
    resp = RedirectResponse(url="/")
    _set_session_cookie(resp, _make_jwt(user))
    return resp


@router.post("/dev-login")
async def dev_login(response: Response, body: dict = Body(...)):
    """Preview-only login without Google, gated by DEV_AUTH=1. Never enabled in prod."""
    if not DEV_AUTH:
        raise HTTPException(status_code=404, detail="Not found")
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email required")
    name = body.get("name") or email.split("@")[0]
    user = await _upsert_user(f"dev:{email}", email, name, None)
    _set_session_cookie(response, _make_jwt(user))
    return user.public_dict()


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


# ===================== Dependencies =====================

async def get_current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")
    async with SessionLocal() as session:
        user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="not_authenticated")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin_required")
    return user


@router.get("/me")
async def me_real(user: User = Depends(get_current_user)):
    return user.public_dict()
