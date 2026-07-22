"""Async SQLAlchemy 2.x database layer for LLM Council monetization (v9).

Holds users, credit_transactions, app_settings. Conversations remain in
storage.py (psycopg2, same Postgres) to keep council.py untouched.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String, Integer, Boolean, Text, DateTime, ForeignKey, func, select, update, text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _async_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is required for the monetization layer")
    # Normalize to asyncpg driver.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg doesn't accept libpq sslmode in the query string; strip it.
    if "?" in url:
        base, _, query = url.partition("?")
        parts = [p for p in query.split("&") if not p.startswith("sslmode")]
        url = base + ("?" + "&".join(parts) if parts else "")
    return url


engine = create_async_engine(_async_database_url(), pool_size=5, max_overflow=10, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "credits": self.credits,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # purchase|usage|admin_grant|refund
    paypal_order_id: Mapped[Optional[str]] = mapped_column(Text)
    paypal_capture_id: Mapped[Optional[str]] = mapped_column(Text)
    conversation_id: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "amount": self.amount,
            "kind": self.kind,
            "paypal_order_id": self.paypal_order_id,
            "conversation_id": self.conversation_id,
            "reason": self.reason,
            "balance_after": self.balance_after,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))


async def init_db():
    """Create tables and the partial unique index for idempotent purchases."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_tx_paypal_order "
            "ON credit_transactions (paypal_order_id) WHERE paypal_order_id IS NOT NULL"
        ))


# ===================== Credit primitives (atomic) =====================

async def credit_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    kind: str,
    *,
    paypal_order_id: Optional[str] = None,
    paypal_capture_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[int]:
    """Add credits (positive) and log a transaction in the same SQL transaction.

    Returns the new balance, or None if a duplicate paypal_order_id was detected.
    """
    if paypal_order_id:
        existing = await session.scalar(
            select(CreditTransaction.id).where(CreditTransaction.paypal_order_id == paypal_order_id)
        )
        if existing:
            return None
    row = await session.execute(
        update(User).where(User.id == user_id)
        .values(credits=User.credits + amount)
        .returning(User.credits)
    )
    new_balance = row.scalar_one()
    session.add(CreditTransaction(
        user_id=user_id, amount=amount, kind=kind,
        paypal_order_id=paypal_order_id, paypal_capture_id=paypal_capture_id,
        conversation_id=conversation_id, reason=reason, balance_after=new_balance,
    ))
    return new_balance


async def debit_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    cost: int,
    *,
    conversation_id: Optional[str] = None,
    kind: str = "usage",
) -> Optional[int]:
    """Atomic debit: UPDATE ... WHERE credits >= cost. Returns new balance or None
    if insufficient funds (0 rows affected)."""
    row = await session.execute(
        update(User)
        .where(User.id == user_id, User.credits >= cost)
        .values(credits=User.credits - cost)
        .returning(User.credits)
    )
    new_balance = row.scalar_one_or_none()
    if new_balance is None:
        return None
    session.add(CreditTransaction(
        user_id=user_id, amount=-cost, kind=kind,
        conversation_id=conversation_id, balance_after=new_balance,
    ))
    return new_balance
