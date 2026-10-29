import os
import psycopg
from psycopg.rows import dict_row

def connection():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured on Render")
    return psycopg.connect(
        url,
        connect_timeout=8,
        row_factory=dict_row
    )

def init_db():
    statements = [
        """CREATE TABLE IF NOT EXISTS nabz_users (
            id BIGSERIAL PRIMARY KEY,
            telegram_id TEXT UNIQUE,
            username TEXT,
            display_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS nabz_direct_messages (
            id BIGSERIAL PRIMARY KEY,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS nabz_groups (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS nabz_group_members (
            group_id BIGINT NOT NULL REFERENCES nabz_groups(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (group_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS nabz_group_messages (
            id BIGSERIAL PRIMARY KEY,
            group_id BIGINT NOT NULL REFERENCES nabz_groups(id) ON DELETE CASCADE,
            sender_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS nabz_support_messages (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE INDEX IF NOT EXISTS idx_nabz_dm_pair
           ON nabz_direct_messages(sender_id, receiver_id, created_at)""",
        """CREATE INDEX IF NOT EXISTS idx_nabz_group_messages
           ON nabz_group_messages(group_id, created_at)"""
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)

def database_status():
    if not os.getenv("DATABASE_URL", "").strip():
        return {"status": "not_configured"}
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "connected"}
    except Exception:
        return {"status": "unavailable"}
