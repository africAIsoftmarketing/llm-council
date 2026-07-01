"""Conversation storage.

Two backends, selected automatically:
  * PostgreSQL  — used when the DATABASE_URL env var is set (e.g. Heroku Postgres
    add-on). Conversations survive dyno restarts/redeploys. Single table
    `conversations (id TEXT PK, data JSONB, created_at, updated_at)`.
  * JSON files  — local fallback in DATA_DIR when DATABASE_URL is not set.

Only the 5 primitives (create/get/save/list/delete) are backend-aware; every
other helper is built on top of them, so the rest of the app is unchanged.
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from .config import DATA_DIR
except ImportError:
    from config import DATA_DIR

DATABASE_URL = os.getenv("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

# ===================== PostgreSQL backend =====================
_PG_POOL = None


def _get_pool():
    global _PG_POOL
    if _PG_POOL is None:
        from psycopg2 import pool as pgpool
        # Heroku provides a postgres:// URL; psycopg2 accepts it as-is.
        sslmode = os.getenv("DB_SSLMODE", "require")
        _PG_POOL = pgpool.ThreadedConnectionPool(
            1, 8, dsn=DATABASE_URL, sslmode=sslmode
        )
        _ensure_table()
    return _PG_POOL


def _ensure_table():
    conn = _PG_POOL.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        conn.commit()
    finally:
        _PG_POOL.putconn(conn)


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


# ===================== JSON backend helpers =====================
def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


# ===================== Backend-aware primitives =====================
def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create and persist a new (empty) conversation."""
    conversation = {
        "id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "New Conversation",
        "messages": [],
    }
    save_conversation(conversation)
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation, or None if not found."""
    if USE_PG:
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM conversations WHERE id = %s", (conversation_id,)
                )
                row = cur.fetchone()
                return row[0] if row else None

    path = get_conversation_path(conversation_id)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """Insert or update a conversation."""
    if USE_PG:
        from psycopg2.extras import Json
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (id, data, created_at, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (id) DO UPDATE
                        SET data = EXCLUDED.data, updated_at = now();
                    """,
                    (
                        conversation["id"],
                        Json(conversation),
                        conversation.get("created_at")
                        or datetime.now(timezone.utc).isoformat(),
                    ),
                )
        return

    ensure_data_dir()
    path = get_conversation_path(conversation["id"])
    with open(path, "w") as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only), newest first."""
    if USE_PG:
        with _pg() as conn:
            with conn.cursor() as cur:
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

    ensure_data_dir()
    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(DATA_DIR, filename)
            with open(path, "r") as f:
                data = json.load(f)
                conversations.append(
                    {
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"]),
                    }
                )
    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation. Returns True if it existed."""
    if USE_PG:
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM conversations WHERE id = %s", (conversation_id,)
                )
                return cur.rowcount > 0

    path = get_conversation_path(conversation_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


# ===================== Higher-level helpers (backend-agnostic) =====================
def add_user_message(conversation_id: str, content: str):
    """Add a user message to a conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({"role": "user", "content": content})
    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
):
    """Add a completed assistant message with all 3 stages."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append(
        {"role": "assistant", "stage1": stage1, "stage2": stage2, "stage3": stage3}
    )
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """Update the title of a conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def add_running_assistant_message(conversation_id: str):
    """Append a placeholder assistant message marked as 'running'.

    Stages are persisted incrementally as the council progresses, so a page
    refresh mid-run can reload the partial progress.
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append(
        {
            "role": "assistant",
            "status": "running",
            "stage1": None,
            "stage2": None,
            "stage3": None,
            "metadata": None,
        }
    )
    save_conversation(conversation)


def update_last_assistant_message(conversation_id: str, **fields):
    """Update fields on the most recent assistant message (in place)."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    for i in range(len(conversation["messages"]) - 1, -1, -1):
        if conversation["messages"][i].get("role") == "assistant":
            conversation["messages"][i].update(fields)
            break
    save_conversation(conversation)
