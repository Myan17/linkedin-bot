import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "connections.db")

# SQLite datetime() uses this exact format for comparisons — always store in this form.
_FMT = "%Y-%m-%d %H:%M:%S"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime(_FMT)


def _fmt(dt: datetime) -> str:
    """Format a datetime for SQLite storage. Treats naive datetimes as UTC."""
    return dt.strftime(_FMT)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                linkedin_profile_url      TEXT UNIQUE NOT NULL,
                first_name                TEXT NOT NULL,
                full_name                 TEXT,
                detected_at               TIMESTAMP NOT NULL,
                initial_message_sent_at   TIMESTAMP,
                followup_due_at           TIMESTAMP,
                followup_sent_at          TIMESTAMP,
                is_umn_student            INTEGER DEFAULT 0,
                status                    TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()


def upsert_connection(profile_url: str, first_name: str, full_name: str):
    """Insert a new connection if not already tracked. Returns True if new."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM connections WHERE linkedin_profile_url = ?",
            (profile_url,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """INSERT INTO connections (linkedin_profile_url, first_name, full_name, detected_at)
               VALUES (?, ?, ?, ?)""",
            (profile_url, first_name, full_name, _utcnow())
        )
        conn.commit()
        return True


def mark_umn_student(profile_url: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE connections SET is_umn_student=1, status='skipped_umn' WHERE linkedin_profile_url=?",
            (profile_url,)
        )
        conn.commit()


def mark_initial_sent(profile_url: str, followup_due: datetime):
    with get_conn() as conn:
        conn.execute(
            """UPDATE connections
               SET initial_message_sent_at=?, followup_due_at=?, status='initial_sent'
               WHERE linkedin_profile_url=?""",
            (_utcnow(), _fmt(followup_due), profile_url)
        )
        conn.commit()


def mark_followup_sent(profile_url: str):
    with get_conn() as conn:
        conn.execute(
            """UPDATE connections
               SET followup_sent_at=?, status='followup_sent'
               WHERE linkedin_profile_url=?""",
            (_utcnow(), profile_url)
        )
        conn.commit()


def get_pending_initial(window_hours: int = 2, limit: int = 5):
    """
    Returns pending connections to message:
    - Any already-tracked 'pending' connection (retry failed sends), OR
    - Newly detected connections within window_hours
    This ensures failed sends are always retried on the next run.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM connections
               WHERE status='pending'
               LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_followup(limit: int = 3):
    """Connections where follow-up is due and not yet sent."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM connections
               WHERE status='initial_sent'
               AND followup_due_at <= datetime('now')
               AND followup_sent_at IS NULL
               LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM connections GROUP BY status"
        ).fetchall()
    return {r["status"]: r["count"] for r in rows}
