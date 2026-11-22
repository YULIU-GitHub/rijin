"""提醒引擎。

职责：
- 每日固定时间汇总「今日到期 / 逾期 / 每日提示」任务；
- 任务到达提醒时间时提醒；
- 到达拟完成时间时发出「最后提醒」；
- 通过 reminder_log 去重，程序重启不会重复轰炸。

引擎只负责产生事件，不直接弹窗，便于将来替换为系统 Toast 或手机推送。
"""
from __future__ import annotations

import logging
from datetime import datetime, time as dt_time, timedelta
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from ..core.config import Config
from ..core.models import PRIORITY_HIGH, Task
from ..core.repository import Repository
from ..core.time_utils import combine_date_time, date_key, now_local

LOGGER = logging.getLogger(__name__)


class ReminderService(QObject):
    remindersReady = pyqtSignal(list)

    def __init__(self, repository: Repository, config: Config, parent: QObject = None):
        super().__init__(parent)
        self.repo = repository
        self.config = config
        self._timer = QTimer(self)
        self._timer.setInterval(20 * 1000)
        self._timer.timeout.connect(self._safe_tick)
        self._last_purge_date = ""

    def start(self) -> None:
        self._timer.start()
        QTimer.singleShot(1400, self._safe_tick)

    def stop(self) -> None:
        self._timer.stop()

    def tick(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        current = (now or now_local()).replace(microsecond=0)
        self._purge_once(current)
        events: List[Dict[str, Any]] = []
        due_event = self._due_event(current)
        if due_event:
            events.append(due_event)
        remind_event = self._reminder_event(current)
        if remind_event:
            events.append(remind_event)
        digest_event = self._digest_event(current)
        if digest_event:
            events.append(digest_event)
        if events:
            self.remindersReady.emit(events)
        return events

    def _safe_tick(self) -> None:
        try:
            self.tick()
        except Exception:
            LOGGER.exception("提醒检查失败")

    # ------------------------------------------------------------------ digest
    def _digest_event(self, now: datetime) -> Optional[Dict[str, Any]]:
        if not bool(self.config.get("digest_enabled", True)):
            return None
        target = self._parse_time(str(self.config.get("digest_time", "09:00")))
        if target is None or now.time() < target:
            return None
        today = date_key(now)
        if not self.repo.claim_daily_state("last_digest_date", today):
            return None
        tasks = self.repo.today_pending(now)
        if not tasks:
            return None
        high = len([task for task in tasks if task.priority == PRIORITY_HIGH])
        summary = "共 %d 项待办" % len(tasks)
        if high:
            summary += "，其中 %d 项高优先" % high
        lines = [self._task_line(task) for task in tasks[:4]]
        if len(tasks) > 4:
            lines.append("…另有 %d 项" % (len(tasks) - 4))
        body = summary + "：\n" + "\n".join(lines)
        return {
            "kind": "digest",
            "title": "日进 · 今日任务",
            "body": self._clip(body),
            "task_ids": [task.id for task in tasks],
            "count": len(tasks),
            "high": high,
        }

    # ------------------------------------------------------------------ overdue
    def _due_event(self, now: datetime) -> Optional[Dict[str, Any]]:
        selected: List[Task] = []
        for task in self.repo.all_pending():
            if task.due_at is None or task.due_at > now:
                continue
            occurrence = task.due_at.strftime("%Y-%m-%d %H:%M:%S")
            if not self.repo.claim_reminder(task.id, "due", occurrence, now):
                continue
            if task.due_at >= now - timedelta(days=7):
                selected.append(task)
        if not selected:
            return None
        selected.sort(key=lambda item: (-item.priority, item.due_at or now, item.id))
        lines = [
            "· " + task.priority_name + "｜" + self._detail(task)
            + (("（%s）" % task.project) if task.project else "")
            for task in selected[:4]
        ]
        if len(selected) > 4:
            lines.append("…另有 %d 项" % (len(selected) - 4))
        body = "已到拟完成时间（最后提醒），请确认进度：\n" + "\n".join(lines)
        return {
            "kind": "due",
            "title": "需要完成 · %d 项" % len(selected),
            "body": self._clip(body),
            "task_ids": [task.id for task in selected],
            "count": len(selected),
            "high": len([task for task in selected if task.priority == PRIORITY_HIGH]),
        }

    # ------------------------------------------------------------------ remind
    def _reminder_event(self, now: datetime) -> Optional[Dict[str, Any]]:
        selected: List[Task] = []
        for task in self.repo.all_pending():
            if task.remind_at is None:
                continue
            if task.daily_prompt:
                if now.date() < task.remind_at.date():
                    continue
                occurrence_dt = combine_date_time(now.date(), task.remind_at.strftime("%H:%M"))
                if now < occurrence_dt:
                    continue
                if self.repo.claim_reminder(task.id, "daily", date_key(now), now):
                    selected.append(task)
            else:
                if now < task.remind_at:
                    continue
                occurrence = task.remind_at.strftime("%Y-%m-%d %H:%M:%S")
                if not self.repo.claim_reminder(task.id, "remind", occurrence, now):
                    continue
                # 太久以前的提醒不再打扰，但仍标记为已处理。
                if task.remind_at >= now - timedelta(days=3):
                    selected.append(task)
        if not selected:
            return None
        selected.sort(key=lambda item: (-item.priority, item.due_at or now, item.id))
        lines = [
            "· " + task.priority_name + "｜" + self._detail(task)
            + (("（%s）" % task.project) if task.project else "")
            for task in selected[:4]
        ]
        if len(selected) > 4:
            lines.append("…另有 %d 项" % (len(selected) - 4))
        body = "到达提醒时间，记得推进：\n" + "\n".join(lines)
        return {
            "kind": "remind",
            "title": "任务提醒 · %d 项" % len(selected),
            "body": self._clip(body),
            "task_ids": [task.id for task in selected],
            "count": len(selected),
            "high": len([task for task in selected if task.priority == PRIORITY_HIGH]),
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _parse_time(value: str) -> Optional[dt_time]:
        try:
            hour, minute = [int(part) for part in value.split(":")]
            return dt_time(hour=hour, minute=minute)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _detail(task: Task, limit: int = 34) -> str:
        text = " ".join(task.detail.split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    @classmethod
    def _task_line(cls, task: Task) -> str:
        label = "高" if task.priority == PRIORITY_HIGH else task.priority_label
        project = ("（%s）" % task.project) if task.project else ""
        return "· [%s] %s%s" % (label, cls._detail(task, 30), project)

    @staticmethod
    def _clip(text: str, limit: int = 700) -> str:
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _purge_once(self, now: datetime) -> None:
        today = date_key(now)
        if self._last_purge_date == today:
            return
        self._last_purge_date = today
        try:
            self.repo.purge_old_reminder_logs(now - timedelta(days=60))
        except Exception:
            LOGGER.exception("清理提醒日志失败")
