"""SQLite database operations for influencer-agent.

Supports dual backend: local SQLite (default) or Turso (libsql).
Set DB_BACKEND=turso + TURSO_EDDIE_URL + TURSO_EDDIE_TOKEN to use Turso.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import PROJECT_ROOT, load_config

_DB_PATH: Path | None = None


def _is_turso() -> bool:
    return os.getenv("DB_BACKEND", "").lower() == "turso"


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        config = load_config()
        rel_path = config.get("database", {}).get("path", "data/influencer_agent.db")
        _DB_PATH = PROJECT_ROOT / rel_path
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


class _DictRow:
    """Lightweight dict-like row for libsql compatibility."""
    __slots__ = ("_keys", "_values", "_map")

    def __init__(self, keys, values):
        self._keys = keys
        self._values = values
        self._map = dict(zip(keys, values))

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        return self._map[key]

    def __iter__(self):
        return iter(self._map.items())

    def __len__(self):
        return len(self._keys)

    def keys(self):
        return self._keys


class _LibsqlWrapper:
    """Wraps a libsql connection to return dict-compatible rows from queries."""

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=()):
        cursor = self._conn.execute(sql, params)
        return _CursorWrapper(cursor)

    def executescript(self, sql):
        return self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def sync(self):
        self._conn.sync()


class _CursorWrapper:
    """Wraps a libsql cursor to return _DictRow objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows or not self._cursor.description:
            return rows
        keys = [col[0] for col in self._cursor.description]
        return [_DictRow(keys, r) for r in rows]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None or not self._cursor.description:
            return row
        keys = [col[0] for col in self._cursor.description]
        return _DictRow(keys, row)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    if _is_turso():
        import libsql_experimental as libsql
        url = os.environ["TURSO_EDDIE_URL"]
        token = os.environ["TURSO_EDDIE_TOKEN"]
        raw = libsql.connect("eddie.db", sync_url=url, auth_token=token)
        raw.sync()
        c = _LibsqlWrapper(raw)
        try:
            yield c
            c.commit()
            c.sync()
        except Exception:
            c.rollback()
            raise
    else:
        c = sqlite3.connect(str(_get_db_path()))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


def init_db():
    """Initialize database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS influencers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instagram_username TEXT UNIQUE NOT NULL,
                full_name TEXT,
                biography TEXT,
                followers_count INTEGER,
                avg_views INTEGER,
                avg_engagement_rate REAL,
                email TEXT,
                email_source TEXT,
                website_url TEXT,
                niche TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                is_business_account BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'discovered',
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contacted_at TIMESTAMP,
                replied_at TIMESTAMP,
                notes TEXT,
                raw_data JSON
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smartlead_campaign_id INTEGER,
                name TEXT NOT NULL,
                niche TEXT,
                template_name TEXT,
                status TEXT DEFAULT 'drafted',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                config JSON
            );

            CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                influencer_id INTEGER REFERENCES influencers(id),
                campaign_id INTEGER REFERENCES campaigns(id),
                smartlead_lead_id INTEGER,
                email_sent_at TIMESTAMP,
                sequence_number INTEGER DEFAULT 1,
                email_subject TEXT,
                email_body TEXT,
                status TEXT DEFAULT 'pending',
                reply_text TEXT,
                reply_category TEXT,
                reply_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dm_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                influencer_id INTEGER REFERENCES influencers(id),
                dm_text TEXT,
                sent_at TIMESTAMP,
                status TEXT DEFAULT 'sent',
                reply_text TEXT,
                reply_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_kpi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                influencers_discovered INTEGER DEFAULT 0,
                emails_sent INTEGER DEFAULT 0,
                emails_opened INTEGER DEFAULT 0,
                emails_replied INTEGER DEFAULT 0,
                dms_sent INTEGER DEFAULT 0,
                leads_interested INTEGER DEFAULT 0,
                leads_contracted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_influencers_status ON influencers(status);
            CREATE INDEX IF NOT EXISTS idx_influencers_email ON influencers(email);
            CREATE INDEX IF NOT EXISTS idx_influencers_username ON influencers(instagram_username);
            CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_logs(status);
            CREATE INDEX IF NOT EXISTS idx_daily_kpi_date ON daily_kpi(date);
        """)


def upsert_influencer(data: dict) -> int:
    """Insert or update an influencer. Returns the row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO influencers
               (instagram_username, full_name, biography, followers_count,
                avg_views, avg_engagement_rate, email, email_source,
                website_url, niche, is_verified, is_business_account, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(instagram_username) DO UPDATE SET
                 full_name = excluded.full_name,
                 biography = excluded.biography,
                 followers_count = excluded.followers_count,
                 avg_views = excluded.avg_views,
                 avg_engagement_rate = excluded.avg_engagement_rate,
                 email = COALESCE(excluded.email, influencers.email),
                 email_source = COALESCE(excluded.email_source, influencers.email_source),
                 website_url = excluded.website_url,
                 is_verified = excluded.is_verified,
                 is_business_account = excluded.is_business_account,
                 raw_data = excluded.raw_data
            """,
            (
                data["instagram_username"],
                data.get("full_name"),
                data.get("biography"),
                data.get("followers_count"),
                data.get("avg_views"),
                data.get("avg_engagement_rate"),
                data.get("email"),
                data.get("email_source"),
                data.get("website_url"),
                data.get("niche"),
                data.get("is_verified", False),
                data.get("is_business_account", False),
                data.get("raw_data"),
            ),
        )
        return cursor.lastrowid


def get_influencers_by_status(status: str, limit: int = 100) -> list[dict]:
    """Fetch influencers by status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM influencers WHERE status = ? ORDER BY avg_engagement_rate DESC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_uncontacted_with_email(limit: int = 100) -> list[dict]:
    """Fetch discovered influencers who have an email and haven't been contacted."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM influencers
               WHERE status = 'discovered' AND email IS NOT NULL AND email != ''
               ORDER BY avg_engagement_rate DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_influencer_status(username: str, status: str):
    """Update an influencer's pipeline status."""
    with get_connection() as conn:
        ts_field = {
            "contacted": "contacted_at",
            "replied": "replied_at",
        }.get(status)
        if ts_field:
            conn.execute(
                f"UPDATE influencers SET status = ?, {ts_field} = CURRENT_TIMESTAMP WHERE instagram_username = ?",
                (status, username),
            )
        else:
            conn.execute(
                "UPDATE influencers SET status = ? WHERE instagram_username = ?",
                (status, username),
            )


def create_campaign(name: str, niche: str, smartlead_id: int | None = None) -> int:
    """Create a new campaign record."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO campaigns (name, niche, smartlead_campaign_id) VALUES (?, ?, ?)",
            (name, niche, smartlead_id),
        )
        return cursor.lastrowid


def log_outreach(influencer_id: int, campaign_id: int, subject: str, body: str, smartlead_lead_id: int | None = None):
    """Log an outreach email."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO outreach_logs
               (influencer_id, campaign_id, smartlead_lead_id, email_subject, email_body)
               VALUES (?, ?, ?, ?, ?)""",
            (influencer_id, campaign_id, smartlead_lead_id, subject, body),
        )


def update_outreach_status(lead_email: str, status: str, reply_text: str | None = None, reply_category: str | None = None):
    """Update outreach log status by lead email."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE outreach_logs SET status = ?, reply_text = ?, reply_category = ?, reply_at = CURRENT_TIMESTAMP
               WHERE influencer_id IN (SELECT id FROM influencers WHERE email = ?)
               AND status NOT IN ('replied', 'bounced', 'unsubscribed')""",
            (status, reply_text, reply_category, lead_email),
        )


def get_kpi_summary(date: str | None = None) -> dict:
    """Get KPI summary for a given date or today."""
    with get_connection() as conn:
        date_clause = "date = ?" if date else "date = DATE('now')"
        params = (date,) if date else ()
        row = conn.execute(
            f"SELECT * FROM daily_kpi WHERE {date_clause}", params
        ).fetchone()
        if row:
            return dict(row)
        return {}


def get_pipeline_counts() -> dict:
    """Get counts for each pipeline stage."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM influencers GROUP BY status"
        ).fetchall()
        return {r["status"]: r["count"] for r in rows}


def get_total_counts() -> dict:
    """Get total counts for dashboard."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM influencers").fetchone()[0]
        with_email = conn.execute("SELECT COUNT(*) FROM influencers WHERE email IS NOT NULL AND email != ''").fetchone()[0]
        return {"total": total, "with_email": with_email}
