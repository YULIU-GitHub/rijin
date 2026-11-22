"""任务中心：集中查看、筛选、编辑与回退所有任务。"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QShortcut,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.config import Config
from ..core.models import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM, Task
from ..core.time_utils import date_key, human_date, now_local
from ..services.store import TaskStore
from . import icons, theme
from .widgets import (
    DragArea,
    EmptyState,
    LogoWidget,
    NavItem,
    TaskRow,
    Toast,
    VScrollArea,
    add_shadow,
    hline,
    make_label,
    set_kind,
)

PROJECT_COLORS = ("#2E5B4C", "#B58432", "#C15B43", "#718078", "#5E7192", "#8A6E9C", "#9A7652")


class TaskCenter(QWidget):
    addRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    editRequested = pyqtSignal(int)
    completeRequested = pyqtSignal(int)
    undoRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)
    closedToTray = pyqtSignal()

    def __init__(self, store: TaskStore, config: Config, parent: QWidget = None):
        super().__init__(parent)
        self.store = store
        self.config = config
        self.view = "today"
        self.project: Optional[str] = None
        self._quitting = False
        self._rows: List[TaskRow] = []
        self._nav_items: Dict[str, NavItem] = {}
        self._project_items: List[NavItem] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self.refresh)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_position)
        self._current_date = date_key()
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(60 * 1000)
        self._clock_timer.timeout.connect(self._clock_tick)
        self._clock_timer.start()

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else self.rect()
        self.WIDTH = min(1080, max(900, available.width() - 90))
        self.HEIGHT = min(720, max(620, available.height() - 90))

        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("任务中心")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(self.WIDTH, self.HEIGHT)
        self.resize(self.WIDTH, self.HEIGHT)

        self._build_ui()
        self._restore_position()
        self.store.changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)
        self.card = QFrame()
        self.card.setObjectName("CenterCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        add_shadow(self.card, 55, 16, 58)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 18, 24, 20)
        card_layout.setSpacing(0)
        card_layout.addLayout(self._build_header())
        card_layout.addSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_sidebar(), 0)
        body.addLayout(self._build_content(), 1)
        card_layout.addLayout(body, 1)

        self.toast = Toast(self)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)
        self.drag_area = DragArea()
        self.drag_area.setFixedHeight(46)
        self.drag_area.dragFinished.connect(self.save_position)
        drag_layout = QHBoxLayout(self.drag_area)
        drag_layout.setContentsMargins(0, 0, 0, 0)
        drag_layout.setSpacing(11)
        drag_layout.addWidget(LogoWidget(38))
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(make_label("任务中心", "DialogTitle"))
        self.header_sub = make_label("把今天，过成想要的样子。", "AppSub")
        text.addWidget(self.header_sub)
        drag_layout.addLayout(text)
        drag_layout.addStretch(1)
        header.addWidget(self.drag_area, 1)

        minimize = QToolButton()
        minimize.setObjectName("WindowButton")
        minimize.setIcon(icons.icon("minimize", theme.MUTED, 16))
        minimize.setIconSize(QSize(16, 16))
        minimize.setFixedSize(30, 30)
        minimize.setCursor(Qt.PointingHandCursor)
        minimize.setToolTip("最小化")
        minimize.clicked.connect(self.showMinimized)
        header.addWidget(minimize, 0, Qt.AlignTop)

        close = QToolButton()
        close.setObjectName("WindowButton")
        close.setIcon(icons.icon("close", theme.MUTED, 16))
        close.setIconSize(QSize(16, 16))
        close.setFixedSize(30, 30)
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("隐藏到托盘")
        close.clicked.connect(self.close)
        header.addWidget(close, 0, Qt.AlignTop)
        return header

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("SoftPanel")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(218)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(11, 14, 11, 12)
        layout.setSpacing(3)

        layout.addWidget(make_label("视图", "SectionTitle"))
        layout.addSpacing(4)
        for key, text, icon_name in (
            ("today", "今日", "calendar"),
            ("pending", "全部待办", "check"),
            ("daily", "每日提示", "refresh"),
            ("completed", "已完成", "database"),
        ):
            item = NavItem(text, icon_name)
            item.clicked.connect(lambda checked=False, key=key: self.set_view(key))
            layout.addWidget(item)
            self._nav_items[key] = item
        layout.addSpacing(14)
        layout.addWidget(make_label("项目", "SectionTitle"))
        layout.addSpacing(3)
        self.project_box = QVBoxLayout()
        self.project_box.setSpacing(2)
        layout.addLayout(self.project_box)

        layout.addStretch(1)
        layout.addWidget(hline())
        layout.addSpacing(8)
        week_panel = QFrame()
        week_panel.setObjectName("WeekPanel")
        week_panel.setFixedHeight(84)
        week_panel.setStyleSheet(
            "QFrame#WeekPanel { background: #FFFDF8; border: 1px solid #E9E4D8; border-radius: 12px; }"
        )
        week_layout = QVBoxLayout(week_panel)
        week_layout.setContentsMargins(13, 10, 13, 10)
        week_layout.setSpacing(0)
        week_layout.addWidget(make_label("本周节奏", "Micro"))
        self.week_value = make_label("0 项", "StatValue")
        self.week_value.setStyleSheet("font-size: 20px; font-weight: 700; color: #2E5B4C;")
        week_layout.addWidget(self.week_value)
        week_layout.addWidget(make_label("已完成任务", "Micro"))
        layout.addWidget(week_panel)
        layout.addSpacing(8)
        footnote = make_label("高优先会自动排在前面", "Micro")
        footnote.setWordWrap(True)
        layout.addWidget(footnote)
        return sidebar

    def _build_content(self) -> QVBoxLayout:
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(14)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(9)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.page_title = make_label("今日任务", "PageTitle")
        self.page_sub = make_label("", "PageSub")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_sub)
        toolbar.addLayout(title_box, 1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索任务")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(188)
        self.search_edit.addAction(icons.icon("search", theme.MUTED, 16), QLineEdit.LeadingPosition)
        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())
        toolbar.addWidget(self.search_edit, 0, Qt.AlignBottom)

        self.priority_combo = QComboBox()
        self.priority_combo.setFixedWidth(124)
        self.priority_combo.addItem("全部优先级", None)
        self.priority_combo.addItem("高优先", PRIORITY_HIGH)
        self.priority_combo.addItem("中优先", PRIORITY_MEDIUM)
        self.priority_combo.addItem("低优先", PRIORITY_LOW)
        self.priority_combo.currentIndexChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self.priority_combo, 0, Qt.AlignBottom)

        settings = QToolButton()
        settings.setObjectName("WindowButton")
        settings.setIcon(icons.icon("settings", theme.MUTED, 17))
        settings.setIconSize(QSize(17, 17))
        settings.setFixedSize(36, 36)
        settings.setCursor(Qt.PointingHandCursor)
        settings.setToolTip("设置")
        settings.clicked.connect(lambda: self.settingsRequested.emit())
        toolbar.addWidget(settings, 0, Qt.AlignBottom)

        add = QPushButton("新建任务")
        set_kind(add, "primary")
        add.setIcon(icons.icon("plus", "#FFFFFF", 15))
        add.setIconSize(QSize(15, 15))
        add.setFixedSize(110, 38)
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self.addRequested.emit())
        toolbar.addWidget(add, 0, Qt.AlignBottom)
        content.addLayout(toolbar)

        self.scroll = VScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 4, 8)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_host)
        content.addWidget(self.scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.footer_label = make_label("", "Micro")
        footer.addWidget(self.footer_label)
        footer.addStretch(1)
        self.footer_week = make_label("", "Micro")
        footer.addWidget(self.footer_week)
        content.addLayout(footer)

        shortcut_add = QShortcut(QKeySequence("Ctrl+N"), self)
        shortcut_add.activated.connect(lambda: self.addRequested.emit())
        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_search.activated.connect(self.search_edit.setFocus)
        shortcut_close = QShortcut(QKeySequence("Esc"), self)
        shortcut_close.activated.connect(self.close)
        return content

    # ------------------------------------------------------------------ data
    def set_view(self, view: str, project: Optional[str] = None, focus: bool = False) -> None:
        self.view = view
        self.project = project
        for key, item in self._nav_items.items():
            item.set_selected(key == view and not project)
        for item in self._project_items:
            item.set_selected(bool(project) and item.text == project)
        self.refresh()
        if focus:
            self.raise_()
            self.activateWindow()
            self.search_edit.setFocus()

    def refresh(self) -> None:
        now = now_local()
        self._current_date = date_key(now)
        self._update_nav_counts(now)
        self._rebuild_projects()
        view, project = self.view, self.project
        priority = self.priority_combo.currentData()
        search = self.search_edit.text().strip()
        tasks = self.store.list_tasks(
            view=view,
            search=search,
            priority=priority,
            project=project,
            now=now,
            limit=500,
        )
        titles = {
            "today": "今日任务",
            "pending": "全部待办",
            "daily": "每日提示",
            "completed": "已完成",
        }
        if project:
            title = "项目 · %s" % project
        else:
            title = titles.get(view, "任务")
        self.page_title.setText(title)
        if view == "today":
            sub = "%s · 高优先自动置顶" % human_date(now)
        elif view == "completed":
            sub = "每一次完成，都算数"
        elif view == "daily":
            sub = "每天都会出现在汇总里的任务"
        else:
            sub = "所有未完成的任务，按优先级排列"
        if search:
            sub = "搜索「%s」" % search
        self.page_sub.setText(sub)
        self.header_sub.setText("%s · %d 项任务" % (human_date(now), len(tasks)))

        self._rebuild_rows(tasks, now)
        self.footer_label.setText("共 %d 项" % len(tasks))
        self.footer_week.setText("本周完成 %d 项 · 数据仅存本机" % self.store.week_completed())
        self.week_value.setText("%d 项" % self.store.week_completed())

    def _update_nav_counts(self, now: datetime) -> None:
        today = self.store.today_pending(now)
        all_pending = self.store.list_tasks(view="pending", limit=1000)
        daily = self.store.list_tasks(view="daily", limit=1000)
        completed = self.store.list_tasks(view="completed", limit=1000)
        self._nav_items["today"].set_count(len(today))
        self._nav_items["pending"].set_count(len(all_pending))
        self._nav_items["daily"].set_count(len(daily))
        self._nav_items["completed"].set_count(len(completed))
        self._pending_by_project = {}
        for task in all_pending:
            key = task.project or "未归类"
            self._pending_by_project[key] = self._pending_by_project.get(key, 0) + 1

    def _rebuild_projects(self) -> None:
        while self.project_box.count():
            item = self.project_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._project_items = []
        projects = [p for p in self.store.projects() if p][:8]
        if not projects:
            empty = make_label("还没有项目", "Micro")
            empty.setContentsMargins(12, 4, 0, 4)
            self.project_box.addWidget(empty)
            return
        for index, project in enumerate(projects):
            item = NavItem(
                project,
                count=self._pending_by_project.get(project, 0),
                dot_color=PROJECT_COLORS[index % len(PROJECT_COLORS)],
            )
            item.clicked.connect(
                lambda checked=False, project=project: self.set_view("pending", project=project)
            )
            item.set_selected(bool(self.project) and self.project == project)
            self.project_box.addWidget(item)
            self._project_items.append(item)

    def _rebuild_rows(self, tasks: List[Task], now: datetime) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        if not tasks:
            if self.view == "completed":
                empty = EmptyState("还没有完成记录", "完成任务后，会在这里留下痕迹", "database")
            elif self.view == "daily":
                empty = EmptyState("没有每日提示任务", "在任务中勾选「每天提示」即可加入", "refresh")
            elif self.project:
                empty = EmptyState("这个项目还没有待办", "点击右上角「新建任务」添加一项", "folder")
            elif self.view == "pending":
                empty = EmptyState("所有事情都在掌控中", "暂时没有待办任务", "check")
            else:
                empty = EmptyState("今天还没有任务", "点击「新建任务」，开始今天", "sun")
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            return
        for task in tasks:
            row = TaskRow(task, "center")
            row.set_task(task, now)
            row.completeRequested.connect(self.completeRequested.emit)
            row.undoRequested.connect(self.undoRequested.emit)
            row.editRequested.connect(self.editRequested.emit)
            row.deleteRequested.connect(self.deleteRequested.emit)
            self._rows.append(row)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)

    # ------------------------------------------------------------------ window
    def _restore_position(self) -> None:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else self.rect()
        pos = self.config.get("center_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            x = available.center().x() - self.WIDTH // 2
            y = available.center().y() - self.HEIGHT // 2
        x = max(available.left() + 8, min(x, available.right() - self.WIDTH - 8))
        y = max(available.top() + 8, min(y, available.bottom() - self.HEIGHT - 8))
        self.move(x, y)

    def save_position(self) -> None:
        self.config.set("center_pos", [self.x(), self.y()])
        try:
            self.config.save()
        except OSError:
            pass

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.isVisible():
            self._save_timer.start(700)

    def show_center(self, view: Optional[str] = None, project: Optional[str] = None) -> None:
        if self.isMinimized():
            self.showNormal()
        if view:
            self.set_view(view, project=project)
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        self.hide()
        self.closedToTray.emit()
        event.ignore()

    def set_quitting(self) -> None:
        self._quitting = True

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def show_toast(
        self,
        text: str,
        action_text: str = "",
        callback=None,
        msecs: int = 6000,
    ) -> None:
        self.toast.show_message(text, action_text, callback, msecs)

    def _clock_tick(self) -> None:
        now = now_local()
        if date_key(now) != self._current_date:
            self.refresh()
            return
        for row in self._rows:
            row.set_task(row.task, now)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast.reposition()
