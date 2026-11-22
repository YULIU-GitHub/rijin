"""应用控制器：把数据、悬浮窗、任务中心、托盘和提醒引擎连接起来。"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon

from .core import backup
from .core.config import Config
from .core.database import Database
from .core.repository import Repository
from .services.reminders import ReminderService
from .services.store import TaskStore
from .ui.dialogs import ConfirmDialog, SettingsDialog, TaskDialog
from .ui.main_window import FloatWindow
from .ui.task_center import TaskCenter
from .ui.tray import TrayIcon

LOGGER = logging.getLogger(__name__)


class AppController(QObject):
    def __init__(self, app: QApplication, config: Config, database: Database, repository: Repository):
        super().__init__()
        self.app = app
        self.config = config
        self.database = database
        self.repo = repository
        self.store = TaskStore(repository)
        self.float_window: Optional[FloatWindow] = None
        self.center: Optional[TaskCenter] = None
        self.dialog_open = False
        self.first_run = False
        self._shutdown_done = False
        self.tray: Optional[TrayIcon] = None
        self.reminders = ReminderService(repository, config, self)
        self._build()

    def _build(self) -> None:
        self.float_window = FloatWindow(self.store, self.config)
        self.float_window.addRequested.connect(self.open_add)
        self.float_window.openCenterRequested.connect(self.open_center)
        self.float_window.settingsRequested.connect(self.open_settings)
        self.float_window.editRequested.connect(lambda task_id: self.edit_task(task_id, "float"))
        self.float_window.completeRequested.connect(lambda task_id: self.complete_task(task_id, "float"))
        self.float_window.undoRequested.connect(lambda task_id: self.reopen_task(task_id, "float"))
        self.float_window.deleteRequested.connect(lambda task_id: self.delete_task(task_id, "float"))
        self.float_window.quitRequested.connect(self.quit)
        self.float_window.hiddenToTray.connect(self._float_hidden)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = TrayIcon(self.store, self.config, self)
            self.tray.showPanelRequested.connect(lambda: self.float_window.show_panel(expand_seconds=7))
            self.tray.addTaskRequested.connect(self.open_add)
            self.tray.centerRequested.connect(lambda: self.open_center("today"))
            self.tray.settingsRequested.connect(self.open_settings)
            self.tray.quitRequested.connect(self.quit)
        self.store.changed.connect(self._on_changed)
        self.reminders.remindersReady.connect(self._on_reminders)

    # ------------------------------------------------------------------ start
    def start(self) -> None:
        self.config.save()
        self.float_window.show()
        if self.tray is not None:
            self.tray.show()
        self.reminders.start()
        self._refresh_summary()
        try:
            backup.daily_backup(self.database)
        except Exception:
            LOGGER.exception("每日数据库备份失败")
        if self.first_run:
            QTimer.singleShot(
                900,
                lambda: self.float_window.show_toast(
                    "欢迎使用日进 · 点击 + 记下第一件事", "", None, 7000
                ),
            )

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.reminders.stop()
        if self.float_window is not None:
            self.float_window.set_quitting()
        if self.center is not None:
            self.center.set_quitting()
        try:
            self.config.save()
        except OSError:
            pass
        if self.tray is not None:
            self.tray.hide()
        try:
            backup.daily_backup(self.database)
        except Exception:
            LOGGER.exception("退出前备份失败")
        self.database.close()

    # ------------------------------------------------------------------ windows
    def _ensure_center(self) -> TaskCenter:
        if self.center is None:
            self.center = TaskCenter(self.store, self.config)
            self.center.addRequested.connect(self.open_add)
            self.center.settingsRequested.connect(self.open_settings)
            self.center.editRequested.connect(lambda task_id: self.edit_task(task_id, "center"))
            self.center.completeRequested.connect(lambda task_id: self.complete_task(task_id, "center"))
            self.center.undoRequested.connect(lambda task_id: self.reopen_task(task_id, "center"))
            self.center.deleteRequested.connect(lambda task_id: self.delete_task(task_id, "center"))
            self.center.closedToTray.connect(self._center_hidden)
        return self.center

    def open_center(self, view: str = "today", project: Optional[str] = None) -> None:
        center = self._ensure_center()
        center.show_center(view=view, project=project)
        self._refresh_summary()

    def open_add(self) -> None:
        self._open_task_dialog(None, self._dialog_parent())

    def edit_task(self, task_id: int, source: str = "float") -> None:
        task = self.store.get(task_id)
        if task is None:
            return
        parent = self.center if source == "center" and self.center is not None else self.float_window
        self._open_task_dialog(task, parent)

    def _dialog_parent(self):
        if self.center is not None and self.center.isVisible():
            return self.center
        if self.float_window is not None and self.float_window.isVisible():
            return self.float_window
        return None

    def _open_task_dialog(self, task, parent) -> None:
        if self.dialog_open:
            return
        self.dialog_open = True
        if self.float_window is not None:
            self.float_window.begin_modal()
        try:
            dialog = TaskDialog(parent, self.repo, task)
            result = dialog.exec_()
            if result != QDialog.Accepted:
                return
            values = dialog.values()
            if task is None:
                created = self.store.create(**values)
                self._toast_for(parent, "任务已添加：%s" % _short(created.detail))
                if self.center is not None and self.center.isVisible():
                    self.center.set_view("today")
            elif dialog.delete_requested:
                self.store.delete(task.id)
                self._toast_for(parent, "任务已删除")
            else:
                self.store.update(task.id, **values)
                self._toast_for(parent, "任务已更新")
        except ValueError as exc:
            QMessageBox.warning(parent, "无法保存", str(exc))
        except Exception:
            LOGGER.exception("保存任务失败")
            QMessageBox.warning(parent, "出现错误", "任务保存失败，请稍后重试。详细信息已写入日志。")
        finally:
            self.dialog_open = False
            if self.float_window is not None:
                self.float_window.end_modal()

    def delete_task(self, task_id: int, source: str = "float") -> None:
        task = self.store.get(task_id)
        if task is None:
            return
        parent = self.center if source == "center" and self.center is not None else self.float_window
        confirmed = ConfirmDialog.ask(
            parent,
            "删除这个任务？",
            "「%s」将被永久删除，完成记录也会一并移除。\n这个操作无法撤销。"
            % _short(task.detail, 60),
            confirm_text="删除",
        )
        if not confirmed:
            return
        self.store.delete(task_id)
        self._toast_for(parent, "任务已删除")

    def complete_task(self, task_id: int, source: str = "float") -> None:
        task = self.store.get(task_id)
        if task is None or task.is_done:
            return
        self.store.complete(task_id)
        text = "已完成「%s」" % _short(task.detail, 24)
        target = self.center if source == "center" and self.center is not None else self.float_window
        target.show_toast(
            text,
            "撤销",
            lambda: self.reopen_task(task_id, "center" if source == "center" else "float"),
        )

    def reopen_task(self, task_id: int, source: str = "float") -> None:
        task = self.store.get(task_id)
        if task is None or not task.is_done:
            return
        self.store.reopen(task_id)
        target = self.center if source == "center" and self.center is not None else self.float_window
        target.show_toast("已撤销完成")

    def _toast_for(self, parent, text: str) -> None:
        if isinstance(parent, TaskCenter):
            parent.show_toast(text)
        else:
            self.float_window.show_toast(text)

    def open_settings(self) -> None:
        if self.dialog_open:
            return
        parent = self._dialog_parent()
        self.dialog_open = True
        self.float_window.begin_modal()
        try:
            dialog = SettingsDialog(parent, self.config, self.repo)
            if dialog.exec_() == QDialog.Accepted:
                self.float_window.apply_settings()
                if self.center is not None:
                    self.center.refresh()
                self._refresh_summary()
                self.float_window.show_toast("设置已保存")
        finally:
            self.dialog_open = False
            self.float_window.end_modal()

    # ------------------------------------------------------------------ events
    def _on_reminders(self, events) -> None:
        if not events:
            return
        enabled = bool(self.config.get("notifications_enabled", True))
        urgent = False
        should_expand = bool(self.config.get("auto_expand", True))
        for event in events:
            urgent = urgent or event.get("kind") == "due"
            if self.tray is not None:
                self.tray.notify(
                    event.get("title", "日进"),
                    event.get("body", ""),
                    urgent=event.get("kind") == "due",
                    enabled=enabled,
                )
        if should_expand:
            self.float_window.show_attention(16 if urgent else 14)
        self._refresh_summary()

    def _on_changed(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if self.tray is None:
            return
        stats = self.store.stats_today()
        self.tray.update_summary(stats["pending"], stats["completed"])

    def _float_hidden(self) -> None:
        if self.tray is not None:
            self.tray.showMessage(
                "日进仍在运行",
                "悬浮窗已隐藏。点击托盘图标，或右键托盘菜单即可重新显示。",
                QSystemTrayIcon.Information,
                4000,
            )

    def _center_hidden(self) -> None:
        pass

    def handle_command(self, command: str) -> None:
        if command == "add":
            self.open_add()
        elif command == "settings":
            self.open_settings()
        elif command == "center":
            self.open_center("today")
        else:
            self.float_window.show_panel(expand_seconds=7)

    def quit(self) -> None:
        self.shutdown()
        self.app.quit()


def _short(text: str, limit: int = 34) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
