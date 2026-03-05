"""SQLite database for ai-hub (unified KPI + mail + approvals).

Supports dual backend: local SQLite (default) or Turso (libsql).
Set DB_BACKEND=turso + TURSO_HUB_URL + TURSO_HUB_TOKEN to use Turso.
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
        cfg = load_config()
        rel = cfg.get("database", {}).get("path", "data/hub.db")
        _DB_PATH = PROJECT_ROOT / rel
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def _dict_factory(cursor, row):
    """Row factory that returns dict-like objects compatible with sqlite3.Row."""
    cols = [col[0] for col in cursor.description]
    return sqlite3.Row(sqlite3.connect(":memory:", check_same_thread=False).cursor(), tuple(range(len(cols))))


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
def conn():
    if _is_turso():
        import libsql_experimental as libsql
        url = os.environ["TURSO_HUB_URL"]
        token = os.environ["TURSO_HUB_TOKEN"]
        raw = libsql.connect("hub.db", sync_url=url, auth_token=token)
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
    with conn() as c:
        c.executescript("""
            -- メール処理ログ
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                from_addr TEXT,
                subject TEXT,
                body_preview TEXT,
                received_at TIMESTAMP,
                category TEXT,          -- urgent/needs_reply/info_only/spam
                draft_reply TEXT,
                status TEXT DEFAULT 'pending',  -- pending/approved/sent/ignored/auto_archived
                slack_ts TEXT,          -- Slack message timestamp (for updates)
                approved_at TIMESTAMP,
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- KPIスナップショット
            CREATE TABLE IF NOT EXISTS kpi_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,   -- eddie/cfo/trading/note
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_unit TEXT,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 承認ログ (append-only)
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,       -- mail/eddie/cfo/trading
                action_type TEXT NOT NULL,  -- email_reply/influencer_contract/journal_entry
                action_summary TEXT,
                action_data JSON,
                status TEXT DEFAULT 'pending',  -- pending/approved/rejected/auto_approved
                slack_ts TEXT,
                decided_by TEXT,           -- user_id or 'auto'
                decided_at TIMESTAMP,
                decision_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 自動承認ルール学習データ
            CREATE TABLE IF NOT EXISTS approval_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                action_type TEXT,
                condition_hash TEXT,
                times_approved INTEGER DEFAULT 0,
                times_rejected INTEGER DEFAULT 0,
                auto_approve_enabled BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
            CREATE INDEX IF NOT EXISTS idx_emails_msgid ON emails(message_id);
            CREATE INDEX IF NOT EXISTS idx_kpi_source ON kpi_snapshots(source, captured_at);
            CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
            CREATE INDEX IF NOT EXISTS idx_approvals_source ON approvals(source);

            -- ニュース記事
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                summary TEXT,
                feed_name TEXT,
                published_at TEXT,
                summarized BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- ニュースサマリー
            CREATE TABLE IF NOT EXISTS news_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_text TEXT NOT NULL,
                article_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_news_items_date ON news_items(created_at);
            CREATE INDEX IF NOT EXISTS idx_news_summaries_date ON news_summaries(created_at);
        """)
