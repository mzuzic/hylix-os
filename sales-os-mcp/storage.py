"""SQLite storage for the Sales OS Second Brain. One DB, tenant-scoped by client_id."""

import os
import sqlite3
import threading
from datetime import datetime, timezone

import re

DB_PATH = os.environ.get("SALES_OS_DB", "sales_os.db")

# Well-known categories (documented conventions). Writes are NOT limited to
# these: any lowercase slug is accepted, so SOPs can introduce new areas
# (finance, marketing, events, ...) without a server change.
KNOWN_CATEGORIES = {"profile", "deal", "transcript", "finance", "marketing", "events", "other"}

_CATEGORY_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def normalize_category(category: str) -> str:
    """Lowercase and validate a category slug; raises ValueError if unusable."""
    slug = (category or "").strip().lower()
    if not _CATEGORY_RE.fullmatch(slug):
        raise ValueError(
            "category must be a short lowercase slug (letters/digits/-/_), "
            f"e.g. one of {sorted(KNOWN_CATEGORIES)}"
        )
    return slug

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass  # WAL unsupported on some filesystems; default journal is fine
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                client_id  TEXT NOT NULL,
                category   TEXT NOT NULL,
                name       TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (client_id, category, name)
            )
            """
        )
        # Generic key-value store — used by the OAuth layer to persist the token
        # signing secret and registered (DCR) clients across restarts.
        conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")


def kv_get(key: str) -> str | None:
    with _conn() as conn:
        r = conn.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return r["v"] if r else None


def kv_set(key: str, value: str) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO kv (k, v) VALUES (?, ?) "
            "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, value),
        )


def kv_delete(key: str) -> None:
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM kv WHERE k=?", (key,))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_docs(client_id: str, category: str | None = None) -> list[dict]:
    q = "SELECT category, name, updated_at, length(content) AS size FROM docs WHERE client_id=?"
    args: list = [client_id]
    if category:
        q += " AND category=?"
        args.append(category)
    q += " ORDER BY category, name"
    with _conn() as conn:
        return [dict(r) for r in conn.execute(q, args).fetchall()]


def read_doc(client_id: str, category: str, name: str) -> dict | None:
    with _conn() as conn:
        r = conn.execute(
            "SELECT category, name, content, updated_at FROM docs "
            "WHERE client_id=? AND category=? AND name=?",
            (client_id, category, name),
        ).fetchone()
        return dict(r) if r else None


def write_doc(client_id: str, category: str, name: str, content: str, append: bool = False) -> dict:
    category = normalize_category(category)
    with _lock, _conn() as conn:
        if append:
            existing = conn.execute(
                "SELECT content FROM docs WHERE client_id=? AND category=? AND name=?",
                (client_id, category, name),
            ).fetchone()
            if existing:
                content = existing["content"].rstrip() + "\n\n" + content
        conn.execute(
            "INSERT INTO docs (client_id, category, name, content, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(client_id, category, name) DO UPDATE SET "
            "content=excluded.content, updated_at=excluded.updated_at",
            (client_id, category, name, content, _now()),
        )
    return {"category": category, "name": name, "updated_at": _now(), "size": len(content)}


def delete_doc(client_id: str, category: str, name: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM docs WHERE client_id=? AND category=? AND name=?",
            (client_id, category, name),
        )
        return cur.rowcount > 0


def search_docs(client_id: str, term: str, category: str | None = None) -> list[dict]:
    """Case-insensitive substring match on doc name or content."""
    q = (
        "SELECT category, name, content, updated_at FROM docs "
        "WHERE client_id=? AND (name LIKE ? OR content LIKE ?)"
    )
    like = f"%{term}%"
    args: list = [client_id, like, like]
    if category:
        q += " AND category=?"
        args.append(category)
    q += " ORDER BY updated_at DESC LIMIT 10"
    with _conn() as conn:
        return [dict(r) for r in conn.execute(q, args).fetchall()]
