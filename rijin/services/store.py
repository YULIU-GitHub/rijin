"""任务服务：在仓储之上发出变更信号，界面无需彼此直接调用。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from ..core.models import Task
from ..core.repository import Repository


class TaskStore(QObject):
    changed = pyqtSignal()
    taskCompleted = pyqtSignal(int)
    taskReopened = pyqtSignal(int)
    taskDeleted = pyqtSignal(int)

    def __init__(self, repository: Repository):
        super().__init__()
        self.repo = repository

    def get(self, task_id: int) -> Optional[Task]:
        return self.repo.get_task(task_id)

    def create(self, **fields: Any) -> Task:
        task = self.repo.create_task(**fields)
        self.changed.emit()
        return task

    def update(self, task_id: int, **fields: Any) -> Task:
        task = self.repo.update_task(task_id, **fields)
        self.changed.emit()
        return task

    def complete(self, task_id: int, at: Optional[datetime] = None) -> Task:
        task = self.repo.complete_task(task_id, at=at)
        self.changed.emit()
        self.taskCompleted.emit(int(task_id))
        return task

    def reopen(self, task_id: int, at: Optional[datetime] = None) -> Task:
        task = self.repo.reopen_task(task_id, at=at)
        self.changed.emit()
        self.taskReopened.emit(int(task_id))
        return task

    def delete(self, task_id: int) -> bool:
        deleted = self.repo.delete_task(task_id)
        if deleted:
            self.changed.emit()
            self.taskDeleted.emit(int(task_id))
        return deleted

    def today_pending(self, now: Optional[datetime] = None) -> List[Task]:
        return self.repo.today_pending(now)

    def list_tasks(self, **kwargs: Any) -> List[Task]:
        return self.repo.list_tasks(**kwargs)

    def stats_today(self) -> Dict[str, int]:
        return self.repo.stats_today()

    def projects(self) -> List[str]:
        return self.repo.projects()

    def week_completed(self) -> int:
        return self.repo.week_completed()
