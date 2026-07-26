"""Conversation storage on PostgreSQL (psycopg2), scoped by user.

Table: conversations(id TEXT PK, user_id TEXT, data JSONB, created_at, updated_at).
Kept sync + psycopg2 so it does not interfere with the asyncpg engine loop.
Conversations survive dyno/pod restarts.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

_POOL = None


def _get_pool():
    global _POOL, DATABASE_URL, DB_SSLMODE
    if _POOL is None:
        # Read env lazily: storage is imported before config.py runs load_dotenv().
        DATABASE_URL = os.getenv("DATABASE_URL", "") or DATABASE_URL
        DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
        from psycopg2 import pool as pgpool
        _POOL = pgpool.ThreadedConnectionPool(1, 8, dsn=DATABASE_URL, sslmode=DB_SSLMODE)
        _ensure_table()
    return _POOL


def _ensure_table():
    conn = _POOL.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        conn.commit()
    finally:
        _POOL.putconn(conn)


@contextmanager
def _pg():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def create_conversation(conversation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    conversation = {
        "id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "New Conversation",
        "messages": [],
    }
    from psycopg2.extras import Json
    with _pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, user_id, data) VALUES (%s, %s, %s)",
                (conversation_id, user_id, Json(conversation)),
            )
    return conversation


def get_conversation(conversation_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _pg() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "SELECT data FROM conversations WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id),
                )
            else:
                cur.execute("SELECT data FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
            return row[0] if row else None


def save_conversation(conversation: Dict[str, Any]):
    from psycopg2.extras import Json
    with _pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET data = %s, updated_at = now() WHERE id = %s",
                (Json(conversation), conversation["id"]),
            )


def list_conversations(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _pg() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "SELECT data FROM conversations WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
            else:
                cur.execute("SELECT data FROM conversations ORDER BY created_at DESC")
            rows = cur.fetchall()
    return [
        {
            "id": data["id"],
            "created_at": data["created_at"],
            "title": data.get("title", "New Conversation"),
            "message_count": len(data.get("messages", [])),
        }
        for (data,) in rows
    ]


def delete_conversation(conversation_id: str, user_id: Optional[str] = None) -> bool:
    with _pg() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id),
                )
            else:
                cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            return cur.rowcount > 0


# ===================== Higher-level helpers =====================

def add_user_message(conversation_id: str, content: str):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conversation["messages"].append({"role": "user", "content": content})
    save_conversation(conversation)


def add_assistant_message(conversation_id, stage1, stage2, stage3):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conversation["messages"].append(
        {"role": "assistant", "stage1": stage1, "stage2": stage2, "stage3": stage3}
    )
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conversation["title"] = title
    save_conversation(conversation)
