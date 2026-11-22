"""SQLite 数据访问基础设施。

设计原则：
- 单文件数据库，本地优先；
- 通过 user_version 做轻量迁移；
- 仓储层不依赖 Qt，便于测试与将来替换存储。
"""
from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project       TEXT NOT NULL DEFAULT '',
    detail        TEXT NOT NULL,
    priority      INTEGER NOT NULL DEFAULT 1 CHECK (priority IN (0, 1, 2)),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done')),
    remind_at     TEXT,
    due_at        TEXT,
    daily_prompt  INTEGER NOT NULL DEFAULT 0 CHECK (daily_prompt IN (0, 1)),
    note          TEXT NOT NULL DEFAULT '',
    started_at    TEXT NOT NULL,
    completed_at  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
    ON tasks(status, priority DESC, due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_due
    ON tasks(due_at);

CREATE TABLE IF NOT EXISTS reminder_log (
    task_id        INTEGER NOT NULL,
    kind           TEXT NOT NULL,
    occurrence     TEXT NOT NULL,
    fired_at       TEXT NOT NULL,
    PRIMARY KEY (task_id, kind, occurrence),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_state (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=3000")
        self._migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _migrate(self) -> None:
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version < 1:
            self.conn.executescript(SCHEMA_V1)
            self.conn.execute("PRAGMA user_version = 1")
            self.conn.commit()
            version = 1
        # 以后版本在此追加：
        # if version < 2:
        #     self.conn.execute("ALTER TABLE tasks ADD COLUMN ...")
        #     self.conn.execute("PRAGMA user_version = 2")
        #     version = 2

    def query(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params=()):
        with self.transaction() as conn:
            return conn.execute(sql, params)

    def backup_to(self, target: Path) -> Path:
        """使用 SQLite 在线备份，运行中也可安全备份。"""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        destination = sqlite3.connect(str(target))
        try:
            self.conn.backup(destination)
        finally:
            destination.close()
        return target

    def copy_file_backup(self, target: Path) -> Path:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, target)
        return target

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
