"""任务仓储。所有 SQL 集中在这里，方便测试和后续迁移。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .database import Database
from .models import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    STATUS_DONE,
    STATUS_PENDING,
    Task,
)
from .time_utils import date_key, now_local, to_iso

_UNSET = object()
_TASK_COLUMNS = (
    "id, project, detail, priority, status, remind_at, due_at, daily_prompt, "
    "note, started_at, completed_at, created_at, updated_at"
)
_SORT_PENDING = (
    "priority DESC, "
    "CASE WHEN due_at IS NULL OR due_at = '' THEN 1 ELSE 0 END ASC, "
    "due_at ASC, id ASC"
)


class Repository:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------ create
    def create_task(
        self,
        detail: str,
        project: str = "",
        priority: int = PRIORITY_MEDIUM,
        remind_at: Optional[datetime] = None,
        due_at: Optional[datetime] = None,
        daily_prompt: bool = False,
        note: str = "",
        at: Optional[datetime] = None,
    ) -> Task:
        detail = (detail or "").strip()
        if not detail:
            raise ValueError("任务明细不能为空")
        priority = self._priority(priority)
        stamp = at or now_local()
        stamp_iso = to_iso(stamp)
        with self.db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (project, detail, priority, status, remind_at, due_at,
                     daily_prompt, note, started_at, completed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    (project or "").strip(),
                    detail,
                    priority,
                    STATUS_PENDING,
                    to_iso(remind_at),
                    to_iso(due_at),
                    1 if daily_prompt else 0,
                    (note or "").strip(),
                    stamp_iso,
                    stamp_iso,
                    stamp_iso,
                ),
            )
            task_id = int(cur.lastrowid)
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("创建任务失败")
        return task

    # -------------------------------------------------------------------- read
    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.db.query_one("SELECT %s FROM tasks WHERE id = ?" % _TASK_COLUMNS, (int(task_id),))
        return Task.from_row(row) if row else None

    def list_tasks(
        self,
        view: str = "today",
        search: str = "",
        priority: Optional[int] = None,
        project: Optional[str] = None,
        now: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Task]:
        current = now or now_local()
        today = date_key(current)
        clauses = []
        params: List[Any] = []
        if view == "today":
            clauses.append(
                "((status = 'pending' AND (daily_prompt = 1 "
                "OR substr(due_at, 1, 10) <= ? OR substr(remind_at, 1, 10) = ?)) "
                "OR (status = 'done' AND substr(completed_at, 1, 10) = ?))"
            )
            params.extend([today, today, today])
        elif view == "daily":
            clauses.append("status = 'pending' AND daily_prompt = 1")
        elif view == "completed":
            clauses.append("status = 'done'")
        else:
            clauses.append("status = 'pending'")
        if search and search.strip():
            needle = "%" + search.strip() + "%"
            clauses.append("(detail LIKE ? OR project LIKE ? OR note LIKE ?)")
            params.extend([needle, needle, needle])
        if priority is not None and int(priority) in (0, 1, 2):
            clauses.append("priority = ?")
            params.append(int(priority))
        if project:
            clauses.append("project = ?")
            params.append(project)
        if view == "completed":
            order = "completed_at DESC, id DESC"
        elif view == "today":
            order = "CASE WHEN status = 'done' THEN 1 ELSE 0 END, " + _SORT_PENDING
        else:
            order = _SORT_PENDING
        sql = "SELECT %s FROM tasks WHERE %s ORDER BY %s LIMIT ?" % (
            _TASK_COLUMNS,
            " AND ".join(clauses),
            order,
        )
        params.append(int(limit))
        return [Task.from_row(row) for row in self.db.query(sql, tuple(params))]

    def today_pending(self, now: Optional[datetime] = None) -> List[Task]:
        current = now or now_local()
        today = date_key(current)
        rows = self.db.query(
            """
            SELECT %s FROM tasks
            WHERE status = 'pending'
              AND (daily_prompt = 1
                   OR substr(due_at, 1, 10) <= ?
                   OR substr(remind_at, 1, 10) = ?)
            ORDER BY %s
            """
            % (_TASK_COLUMNS, _SORT_PENDING),
            (today, today),
        )
        return [Task.from_row(row) for row in rows]

    def all_pending(self) -> List[Task]:
        rows = self.db.query(
            "SELECT %s FROM tasks WHERE status = 'pending' ORDER BY %s"
            % (_TASK_COLUMNS, _SORT_PENDING)
        )
        return [Task.from_row(row) for row in rows]

    def completed_today(self, now: Optional[datetime] = None) -> List[Task]:
        today = date_key(now)
        rows = self.db.query(
            "SELECT %s FROM tasks WHERE status = 'done' AND substr(completed_at, 1, 10) = ? "
            "ORDER BY completed_at DESC, id DESC" % _TASK_COLUMNS,
            (today,),
        )
        return [Task.from_row(row) for row in rows]

    def recent_completed(self, limit: int = 5) -> List[Task]:
        rows = self.db.query(
            "SELECT %s FROM tasks WHERE status = 'done' ORDER BY completed_at DESC, id DESC LIMIT ?"
            % _TASK_COLUMNS,
            (int(limit),),
        )
        return [Task.from_row(row) for row in rows]

    def projects(self) -> List[str]:
        rows = self.db.query(
            "SELECT DISTINCT project FROM tasks WHERE project <> '' ORDER BY project COLLATE NOCASE"
        )
        return [row["project"] for row in rows]

    def stats_today(self, now: Optional[datetime] = None) -> Dict[str, int]:
        pending = self.today_pending(now)
        done = self.completed_today(now)
        return {
            "pending": len(pending),
            "high": len([task for task in pending if task.priority == PRIORITY_HIGH]),
            "completed": len(done),
            "total": len(pending) + len(done),
        }

    def week_completed(self, now: Optional[datetime] = None) -> int:
        current = now or now_local()
        start = (current - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00")
        row = self.db.query_one(
            "SELECT COUNT(*) AS n FROM tasks WHERE status = 'done' AND completed_at >= ?",
            (start,),
        )
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------ update
    def update_task(self, task_id: int, at: Optional[datetime] = None, **fields: Any) -> Task:
        allowed = {"project", "detail", "priority", "remind_at", "due_at", "daily_prompt", "note"}
        values: Dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "detail":
                value = (value or "").strip()
                if not value:
                    raise ValueError("任务明细不能为空")
            elif key == "project":
                value = (value or "").strip()
            elif key == "priority":
                value = self._priority(value)
            elif key in ("remind_at", "due_at"):
                value = to_iso(value)
            elif key == "daily_prompt":
                value = 1 if value else 0
            elif key == "note":
                value = (value or "").strip()
            values[key] = value
        if not values:
            task = self.get_task(task_id)
            if task is None:
                raise KeyError("任务不存在")
            return task
        values["updated_at"] = to_iso(at or now_local())
        columns = ", ".join("%s = ?" % key for key in values)
        params = list(values.values()) + [int(task_id)]
        with self.db.transaction() as conn:
            cur = conn.execute("UPDATE tasks SET %s WHERE id = ?" % columns, tuple(params))
            if cur.rowcount == 0:
                raise KeyError("任务不存在")
        task = self.get_task(task_id)
        if task is None:
            raise KeyError("任务不存在")
        return task

    def complete_task(self, task_id: int, at: Optional[datetime] = None) -> Task:
        stamp = to_iso(at or now_local())
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (STATUS_DONE, stamp, stamp, int(task_id), STATUS_PENDING),
            )
            if cur.rowcount == 0:
                task = self.get_task(task_id)
                if task is None:
                    raise KeyError("任务不存在")
                return task
        task = self.get_task(task_id)
        if task is None:
            raise KeyError("任务不存在")
        return task

    def reopen_task(self, task_id: int, at: Optional[datetime] = None) -> Task:
        stamp = to_iso(at or now_local())
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, completed_at = NULL, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (STATUS_PENDING, stamp, int(task_id), STATUS_DONE),
            )
            if cur.rowcount == 0:
                task = self.get_task(task_id)
                if task is None:
                    raise KeyError("任务不存在")
                return task
        task = self.get_task(task_id)
        if task is None:
            raise KeyError("任务不存在")
        return task

    def delete_task(self, task_id: int) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
            return cur.rowcount > 0

    # ------------------------------------------------------------------ reminders
    def claim_reminder(
        self,
        task_id: int,
        kind: str,
        occurrence: str,
        at: Optional[datetime] = None,
    ) -> bool:
        """原子地占用一条提醒；True 表示本次应该真正提醒。"""
        try:
            with self.db.transaction() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO reminder_log(task_id, kind, occurrence, fired_at) "
                    "VALUES (?, ?, ?, ?)",
                    (int(task_id), kind, occurrence, to_iso(at or now_local())),
                )
                return cur.rowcount > 0
        except Exception:
            return False

    def claim_daily_state(self, key: str, value: str) -> bool:
        """按天占用一个全局状态（如每日汇总），保证进程重启后不重复。

        只有值发生变化时才返回 True，因此同一个日期不会重复提醒；
        新的一天会自动覆盖旧值。
        """
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO app_state(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value "
                "WHERE app_state.value <> excluded.value",
                (key, value),
            )
            return cur.rowcount > 0

    def get_state(self, key: str) -> Optional[str]:
        row = self.db.query_one("SELECT value FROM app_state WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO app_state(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def purge_old_reminder_logs(self, before: datetime) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM reminder_log WHERE fired_at < ?", (to_iso(before),))

    # ------------------------------------------------------------------ export
    def export_snapshot(self) -> List[Dict[str, Any]]:
        rows = self.db.query("SELECT %s FROM tasks ORDER BY id ASC" % _TASK_COLUMNS)
        return [Task.from_row(row).to_dict() for row in rows]

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _priority(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = PRIORITY_MEDIUM
        return max(0, min(2, number))
