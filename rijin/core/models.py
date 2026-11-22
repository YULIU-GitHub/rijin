"""任务领域模型。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .time_utils import parse_dt

PRIORITY_HIGH = 2
PRIORITY_MEDIUM = 1
PRIORITY_LOW = 0

PRIORITY_LABELS = {2: "高", 1: "中", 0: "低"}
PRIORITY_NAMES = {2: "高优先", 1: "中优先", 0: "低优先"}
PRIORITY_COLORS = {2: "#C15B43", 1: "#B58432", 0: "#718078"}
PRIORITY_BG = {2: "#F7E7E1", 1: "#F6EEDC", 0: "#EAF0EC"}

STATUS_PENDING = "pending"
STATUS_DONE = "done"


@dataclass
class Task:
    id: int
    project: str
    detail: str
    priority: int
    status: str
    remind_at: Optional[datetime]
    due_at: Optional[datetime]
    daily_prompt: bool
    note: str
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @property
    def is_done(self) -> bool:
        return self.status == STATUS_DONE

    @property
    def is_pending(self) -> bool:
        return self.status == STATUS_PENDING

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS.get(self.priority, "中")

    @property
    def priority_name(self) -> str:
        return PRIORITY_NAMES.get(self.priority, "中优先")

    @property
    def priority_color(self) -> str:
        return PRIORITY_COLORS.get(self.priority, PRIORITY_COLORS[1])

    @property
    def priority_bg(self) -> str:
        return PRIORITY_BG.get(self.priority, PRIORITY_BG[1])

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        if not self.is_pending or self.due_at is None:
            return False
        return self.due_at < (now or datetime.now())

    def is_due_today(self, now: Optional[datetime] = None) -> bool:
        if self.due_at is None:
            return False
        return self.due_at.date() == (now or datetime.now()).date()

    def is_remind_today(self, now: Optional[datetime] = None) -> bool:
        if self.remind_at is None:
            return False
        return self.remind_at.date() == (now or datetime.now()).date()

    @classmethod
    def from_row(cls, row: Any) -> "Task":
        started = parse_dt(row["started_at"]) or datetime.now()
        created = parse_dt(row["created_at"]) or started
        updated = parse_dt(row["updated_at"]) or created
        return cls(
            id=int(row["id"]),
            project=row["project"] or "",
            detail=row["detail"] or "",
            priority=int(row["priority"]),
            status=row["status"] or STATUS_PENDING,
            remind_at=parse_dt(row["remind_at"]),
            due_at=parse_dt(row["due_at"]),
            daily_prompt=bool(row["daily_prompt"]),
            note=row["note"] or "",
            started_at=started,
            completed_at=parse_dt(row["completed_at"]),
            created_at=created,
            updated_at=updated,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project": self.project,
            "detail": self.detail,
            "priority": self.priority,
            "status": self.status,
            "remind_at": self.remind_at.strftime("%Y-%m-%d %H:%M:%S") if self.remind_at else None,
            "due_at": self.due_at.strftime("%Y-%m-%d %H:%M:%S") if self.due_at else None,
            "daily_prompt": self.daily_prompt,
            "note": self.note,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
