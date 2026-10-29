"""基于 SQLite FTS5 的笔记全文索引。

设计要点：
- ``notes`` 表保存 path/mtime/size/title/body，``note_fts`` 用 FTS5 存 title/body；
- FTS5 优先 ``trigram``（支持中文子串），不可用时退 ``unicode61``，再不可用则只用 LIKE；
- 搜索前按 mtime/size 做增量同步；关键词少于 3 字符时直接走 LIKE（trigram 限制）；
- 所有函数都是同步的，由调用方放进 ``asyncio.to_thread``。
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

try:  # 包方式加载
    from .vault_paths import extract_snippets, iter_note_files, relative_display
except ImportError:  # pragma: no cover - 兼容脚本方式加载
    from vault_paths import extract_snippets, iter_note_files, relative_display  # type: ignore[no-redef]

_SYNC_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect(db_path: Path, readonly: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    if readonly:
        conn.execute("PRAGMA query_only=ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> str:
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT value FROM meta WHERE key='tokenizer'").fetchone()
    if row:
        return row[0]

    existing = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='note_fts'"
    ).fetchone()
    if existing:
        conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('tokenizer', 'trigram')")
        return "trigram"

    for tokenizer in ("trigram", "unicode61"):
        try:
            conn.execute(
                f"CREATE VIRTUAL TABLE note_fts USING fts5(title, body, tokenize='{tokenizer}')"
            )
        except sqlite3.OperationalError:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('tokenizer', ?)",
            (tokenizer,),
        )
        return tokenizer

    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('tokenizer', 'none')")
    return "none"


def _tokenizer(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='tokenizer'").fetchone()
    except sqlite3.DatabaseError:
        return "none"
    return row[0] if row else "none"


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return stripped[:80]
    return fallback


def _like_pattern(keyword: str) -> str:
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def sync_index(
    db_path: Path,
    root: Path,
    max_file_bytes: int = 2 * 1024 * 1024,
    force: bool = False,
) -> dict:
    """把 root 下的笔记增量同步进索引，返回统计信息。"""
    root = Path(root)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _SYNC_LOCK:
        conn = _connect(db_path)
        try:
            tokenizer = _ensure_schema(conn)
            conn.execute("PRAGMA journal_mode=WAL")
            known = {
                row[0]: (row[1], row[2])
                for row in conn.execute("SELECT path, mtime, size FROM notes")
            }
            seen: set[str] = set()
            added = updated = skipped = 0

            with conn:
                for file_path in iter_note_files(root):
                    try:
                        stat = file_path.stat()
                    except OSError:
                        continue
                    if stat.st_size > max_file_bytes:
                        continue

                    relative = relative_display(root, file_path)
                    seen.add(relative)
                    previous = known.get(relative)
                    if (
                        not force
                        and previous
                        and abs(previous[0] - stat.st_mtime) < 1e-6
                        and previous[1] == stat.st_size
                    ):
                        skipped += 1
                        continue

                    try:
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue

                    title = _title(text, file_path.stem)
                    conn.execute(
                        "INSERT INTO notes(path, mtime, size, title, body) "
                        "VALUES(?, ?, ?, ?, ?) "
                        "ON CONFLICT(path) DO UPDATE SET "
                        "mtime=excluded.mtime, size=excluded.size, "
                        "title=excluded.title, body=excluded.body",
                        (relative, stat.st_mtime, stat.st_size, title, text),
                    )
                    row_id = conn.execute(
                        "SELECT id FROM notes WHERE path=?", (relative,)
                    ).fetchone()[0]
                    if tokenizer != "none":
                        conn.execute("DELETE FROM note_fts WHERE rowid=?", (row_id,))
                        conn.execute(
                            "INSERT INTO note_fts(rowid, title, body) VALUES(?, ?, ?)",
                            (row_id, title, text),
                        )
                    if previous is None:
                        added += 1
                    else:
                        updated += 1

                for stale in set(known) - seen:
                    row = conn.execute("SELECT id FROM notes WHERE path=?", (stale,)).fetchone()
                    if not row:
                        continue
                    if tokenizer != "none":
                        conn.execute("DELETE FROM note_fts WHERE rowid=?", (row[0],))
                    conn.execute("DELETE FROM notes WHERE id=?", (row[0],))

                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES('last_sync', ?)",
                    (str(int(time.time())),),
                )

            removed = len(set(known) - seen)
        finally:
            conn.close()

    size = db_path.stat().st_size if db_path.exists() else 0
    return {
        "indexed": len(seen),
        "added": added,
        "updated": updated,
        "removed": removed,
        "skipped": skipped,
        "tokenizer": tokenizer,
        "db_bytes": size,
    }


def search_index(
    db_path: Path,
    keyword: str,
    limit: int = 5,
    snippet_chars: int = 300,
    snippets_per_note: int = 2,
) -> list[dict]:
    """查询索引，返回 [{path, snippets}]；索引不可用时返回空列表。"""
    kw = str(keyword or "").strip()
    if not kw or not Path(db_path).is_file():
        return []

    rows: list[tuple[str, str]] = []
    conn = _connect(Path(db_path), readonly=True)
    try:
        tokenizer = _tokenizer(conn)
        if tokenizer == "trigram" and len(kw) >= 3:
            try:
                match = '"' + kw.replace('"', '""') + '"'
                rows = conn.execute(
                    "SELECT notes.path, notes.body FROM note_fts "
                    "JOIN notes ON notes.id = note_fts.rowid "
                    "WHERE note_fts MATCH ? ORDER BY rank LIMIT ?",
                    (match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        if not rows:
            pattern = _like_pattern(kw)
            rows = conn.execute(
                "SELECT path, body FROM notes "
                "WHERE body LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' "
                "OR path LIKE ? ESCAPE '\\' ORDER BY mtime DESC LIMIT ?",
                (pattern, pattern, pattern, limit),
            ).fetchall()
    finally:
        conn.close()

    results = []
    for path, body in rows:
        snippets = extract_snippets(body, kw, snippet_chars, snippets_per_note)
        results.append({"path": path, "snippets": snippets or ["（文件名匹配）"]})
    return results


def index_stats(db_path: Path) -> dict | None:
    """返回索引概况；索引不存在或损坏时返回 None。"""
    path = Path(db_path)
    if not path.is_file():
        return None
    try:
        conn = _connect(path, readonly=True)
    except sqlite3.Error:
        return None
    try:
        notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        row = conn.execute("SELECT value FROM meta WHERE key='last_sync'").fetchone()
        tokenizer = _tokenizer(conn)
    except sqlite3.DatabaseError:
        return None
    finally:
        conn.close()
    return {
        "notes": notes,
        "last_sync": float(row[0]) if row else 0.0,
        "bytes": path.stat().st_size,
        "tokenizer": tokenizer,
    }
