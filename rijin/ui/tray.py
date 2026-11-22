"""系统托盘入口：隐藏后仍可随时唤回。"""
from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon

from ..core.config import Config
from ..services.store import TaskStore
from . import icons, theme


class TrayIcon(QSystemTrayIcon):
    showPanelRequested = pyqtSignal()
    addTaskRequested = pyqtSignal()
    centerRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(self, store: TaskStore, config: Config, parent: QObject = None):
        super().__init__(icons.app_icon(), parent)
        self.store = store
        self.config = config
        self.setToolTip("日进 · 每日任务")
        self.menu = QMenu()
        self._build_menu()
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)
        self.messageClicked.connect(lambda: self.showPanelRequested.emit())

    def _build_menu(self) -> None:
        show = QAction(icons.icon("eye", theme.INK_SOFT, 16), "显示悬浮窗", self.menu)
        show.triggered.connect(lambda: self.showPanelRequested.emit())
        self.menu.addAction(show)
        add = QAction(icons.icon("plus", theme.ACCENT, 16), "新建任务", self.menu)
        add.triggered.connect(lambda: self.addTaskRequested.emit())
        self.menu.addAction(add)
        center = QAction(icons.icon("calendar", theme.INK_SOFT, 16), "打开任务中心", self.menu)
        center.triggered.connect(lambda: self.centerRequested.emit())
        self.menu.addAction(center)
        self.menu.addSeparator()
        settings = QAction(icons.icon("settings", theme.INK_SOFT, 16), "设置", self.menu)
        settings.triggered.connect(lambda: self.settingsRequested.emit())
        self.menu.addAction(settings)
        self.menu.addSeparator()
        quit_action = QAction(icons.icon("close", theme.DANGER, 16), "退出日进", self.menu)
        quit_action.triggered.connect(lambda: self.quitRequested.emit())
        self.menu.addAction(quit_action)

    def update_summary(self, pending: int, completed: int = 0) -> None:
        if pending:
            text = "日进 · 今日 %d 项待办" % pending
        elif completed:
            text = "日进 · 今日已清空"
        else:
            text = "日进 · 今天还没有任务"
        self.setToolTip(text)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showPanelRequested.emit()

    def notify(self, title: str, body: str, urgent: bool = False, enabled: bool = True) -> None:
        if not enabled:
            return
        icon = QSystemTrayIcon.Warning if urgent else QSystemTrayIcon.Information
        self.showMessage(title, body, icon, 10000)
