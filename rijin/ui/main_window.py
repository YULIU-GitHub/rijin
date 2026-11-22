"""桌面悬浮窗：日常主界面。

交互：
- 默认只展示今日摘要；鼠标悬停自动展开详情；
- 顶部可拖动，松开后贴近屏幕边缘；
- 任务行支持完成、撤销、编辑、删除；
- 右下角可进入任务中心与设置。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.config import Config
from ..core.models import Task
from ..core.time_utils import date_key, human_date, human_due, now_local
from ..services.store import TaskStore
from . import icons, theme
from .widgets import (
    DragArea,
    EmptyState,
    LogoWidget,
    ProgressRing,
    TaskRow,
    Toast,
    VScrollArea,
    add_shadow,
    hline,
    make_label,
    set_kind,
)


class NextTaskCard(QWidget):
    """摘要区下方的一张“下一件事”卡片。"""

    activated = pyqtSignal(object)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.task: Optional[Task] = None
        self.empty_text = "今天暂无待办 · 点击记下一件事"
        self._hovered = False
        self._now = now_local()
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("点击编辑")

    def set_task(self, task: Optional[Task], empty_text: str, now: Optional[datetime] = None) -> None:
        self.task = task
        self.empty_text = empty_text
        self._now = now or now_local()
        self.setToolTip(task.detail if task else "点击新建任务")
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.activated.emit(self.task)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#F1ECE1" if self._hovered else "#F7F3EA"))
        painter.drawRoundedRect(rect, 12, 12)
        task = self.task
        if task is None:
            painter.setBrush(QColor(theme.ACCENT_SOFT))
            painter.drawEllipse(QRectF(13, 13, 20, 20))
            painter.setPen(QPen(QColor(theme.ACCENT), 1.6))
            painter.drawLine(23, 18, 23, 28)
            painter.drawLine(18, 23, 28, 23)
            painter.setFont(self._font(9.8, QFont.Medium))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(
                QRectF(44, 0, self.width() - 58, self.height()),
                int(Qt.AlignLeft | Qt.AlignVCenter),
                self.empty_text,
            )
            return

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(task.priority_color))
        painter.drawEllipse(QRectF(16, 19, 8, 8))
        text_left = 34.0
        right_width = 104.0
        detail_font = self._font(9.9, QFont.DemiBold)
        painter.setFont(detail_font)
        painter.setPen(QColor(theme.INK))
        metrics = QFontMetrics(detail_font)
        detail = metrics.elidedText(task.detail, Qt.ElideRight, int(self.width() - text_left - right_width))
        painter.drawText(
            QRectF(text_left, 7, self.width() - text_left - right_width, 18),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            detail,
        )
        painter.setFont(self._font(8.2))
        painter.setPen(QColor(theme.MUTED))
        meta = task.project or "未归类"
        if task.daily_prompt:
            meta += "  ·  每日"
        painter.drawText(
            QRectF(text_left, 25, self.width() - text_left - right_width, 15),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            meta,
        )
        if task.due_at:
            painter.setFont(self._font(8.4, QFont.Medium))
            painter.setPen(QColor(theme.HIGH if task.is_overdue(self._now) else theme.MUTED))
            painter.drawText(
                QRectF(self.width() - right_width - 6, 0, right_width - 8, self.height()),
                int(Qt.AlignRight | Qt.AlignVCenter),
                human_due(task.due_at, self._now),
            )

    @staticmethod
    def _font(size: float, weight=QFont.Normal) -> QFont:
        font = QFont("Microsoft YaHei UI")
        font.setPointSizeF(size)
        font.setWeight(weight)
        return font


class FloatWindow(QWidget):
    addRequested = pyqtSignal()
    openCenterRequested = pyqtSignal(str)
    settingsRequested = pyqtSignal()
    editRequested = pyqtSignal(int)
    completeRequested = pyqtSignal(int)
    undoRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)
    quitRequested = pyqtSignal()
    hiddenToTray = pyqtSignal()

    WIDTH = 384
    MARGIN = 18
    # 收起态只保留标题与今日进度，不展示任何具体任务信息。
    COMPACT_HEIGHT = 186
    TOAST_SPACE = 54

    def __init__(self, store: TaskStore, config: Config, parent: QWidget = None):
        super().__init__(parent)
        self.store = store
        self.config = config
        self._expanded = False
        self._pinned = bool(config.get("floating_pinned", False))
        self._hover_expand = bool(config.get("hover_expand", True))
        self._always_on_top = bool(config.get("always_on_top", True))
        self._modal_open = False
        self._menu_open = False
        self._quitting = False
        self._animating = False
        self._rows: List[TaskRow] = []
        self._attention_timer = QTimer(self)
        self._attention_timer.setSingleShot(True)
        self._attention_timer.timeout.connect(self._attention_timeout)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._maybe_hover_expand)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._maybe_hover_collapse)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_position)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(60 * 1000)
        self._clock_timer.timeout.connect(self._clock_tick)
        self._clock_timer.start()
        self._current_date = date_key()

        self._height_anim = QPropertyAnimation(self, b"windowHeight", self)
        self._height_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._build_window()
        self._build_ui()
        self._restore_position()
        self.setFixedSize(self.WIDTH, self.COMPACT_HEIGHT)
        self.store.changed.connect(self.refresh)
        self.refresh()
        if self._pinned:
            QTimer.singleShot(0, lambda: self.set_expanded(True, animate=False))

    # ------------------------------------------------------------------ window
    def _build_window(self) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("日进")
        self.setWindowIcon(icons.app_icon())
        self.setMouseTracking(True)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("FloatCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        add_shadow(self.card, 42, 10, 48)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_header())

        self.summary_widget = QWidget()
        self.summary_widget.setFixedHeight(70)
        summary = QHBoxLayout(self.summary_widget)
        summary.setContentsMargins(0, 0, 0, 0)
        summary.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        self.kicker = make_label("今日进度", "Micro")
        self.hero = make_label("今天还没有任务", "Hero")
        self.hero.setFixedHeight(32)
        self.summary_sub = make_label("点击 + 记下第一件事", "Micro")
        text_box.addWidget(self.kicker)
        text_box.addWidget(self.hero)
        text_box.addWidget(self.summary_sub)
        summary.addLayout(text_box, 1)
        self.ring = ProgressRing(size=56)
        summary.addWidget(self.ring, 0, Qt.AlignVCenter)
        layout.addWidget(self.summary_widget)

        self.next_card = NextTaskCard()
        self.next_card.activated.connect(self._on_next_activated)

        self.details = QWidget()
        self.details.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        details_layout.addWidget(hline())
        section_row = QHBoxLayout()
        section_row.setSpacing(8)
        section_row.addWidget(make_label("今日任务", "SectionTitle"))
        section_row.addStretch(1)
        self.section_count = make_label("", "Micro")
        section_row.addWidget(self.section_count)
        details_layout.addLayout(section_row)

        self.scroll = VScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setFixedHeight(150)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 2, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_host)
        details_layout.addWidget(self.scroll)

        self.completed_btn = QPushButton("")
        set_kind(self.completed_btn, "link")
        self.completed_btn.setCursor(Qt.PointingHandCursor)
        self.completed_btn.setFixedHeight(24)
        self.completed_btn.clicked.connect(lambda: self.openCenterRequested.emit("completed"))
        details_layout.addWidget(self.completed_btn)

        footer = QHBoxLayout()
        footer.setSpacing(4)
        center_btn = QPushButton("任务中心  ›")
        set_kind(center_btn, "link")
        center_btn.setCursor(Qt.PointingHandCursor)
        center_btn.clicked.connect(lambda: self.openCenterRequested.emit("today"))
        footer.addWidget(center_btn)
        footer.addStretch(1)
        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(icons.icon("settings", theme.MUTED, 17))
        self.settings_btn.setIconSize(QSize(17, 17))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("设置")
        self.settings_btn.clicked.connect(lambda: self.settingsRequested.emit())
        footer.addWidget(self.settings_btn)
        details_layout.addLayout(footer)

        # 折叠/展开时让这块内容保持固定高度并交给窗口裁切，
        # 而不是让 QVBoxLayout 把标题、进度和任务行压在一起。
        self.expandable = QWidget()
        self.expandable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        expandable_layout = QVBoxLayout(self.expandable)
        expandable_layout.setContentsMargins(0, 0, 0, 0)
        expandable_layout.setSpacing(10)
        expandable_layout.addWidget(self.next_card)
        expandable_layout.addWidget(self.details)
        self.expandable.setVisible(False)
        layout.addWidget(self.expandable)
        # 收起态为提示条预留高度时，多出来的空间应留在底部，
        # 而不是把标题和今日进度整体往下推。
        layout.addStretch(1)

        self.toast = Toast(self)
        self.toast.hidden.connect(self._on_toast_hidden)
        self._update_pin_icon()

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(6)
        self.drag_area = DragArea()
        self.drag_area.setFixedHeight(38)
        self.drag_area.dragFinished.connect(self._on_drag_finished)
        self.drag_area.doubleClicked.connect(self._toggle_expanded)
        drag_layout = QHBoxLayout(self.drag_area)
        drag_layout.setContentsMargins(0, 0, 0, 0)
        drag_layout.setSpacing(10)
        logo = LogoWidget(36)
        drag_layout.addWidget(logo)
        text = QVBoxLayout()
        text.setSpacing(0)
        title = make_label("日进", "AppTitle")
        self.date_label = make_label(human_date(), "AppSub")
        text.addWidget(title)
        text.addWidget(self.date_label)
        drag_layout.addLayout(text)
        drag_layout.addStretch(1)
        header.addWidget(self.drag_area, 1)

        self.pin_btn = QToolButton()
        self.pin_btn.setObjectName("WindowButton")
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.clicked.connect(self._toggle_pin)
        header.addWidget(self.pin_btn, 0, Qt.AlignVCenter)

        self.add_btn = QToolButton()
        self.add_btn.setObjectName("AccentButton")
        self.add_btn.setIcon(icons.icon("plus", "#FFFFFF", 16))
        self.add_btn.setIconSize(QSize(16, 16))
        self.add_btn.setFixedSize(34, 34)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("新建任务")
        self.add_btn.clicked.connect(lambda: self.addRequested.emit())
        header.addWidget(self.add_btn, 0, Qt.AlignVCenter)

        self.more_btn = QToolButton()
        self.more_btn.setObjectName("WindowButton")
        self.more_btn.setIcon(icons.icon("more", theme.MUTED, 18))
        self.more_btn.setIconSize(QSize(18, 18))
        self.more_btn.setFixedSize(28, 28)
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.setToolTip("更多")
        # 等按钮的鼠标释放事件完全结束后再弹菜单，
        # 避免菜单刚打开就被同一次释放事件关掉，也避免定位漂移。
        self.more_btn.clicked.connect(lambda: QTimer.singleShot(0, self._show_menu_at_button))
        header.addWidget(self.more_btn, 0, Qt.AlignVCenter)
        return header

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        now = now_local()
        self._current_date = date_key(now)
        self.date_label.setText(human_date(now))
        all_today = self.store.today_pending(now)
        stats = self.store.stats_today()
        pending = stats["pending"]
        done = stats["completed"]
        total = pending + done

        if pending:
            self.hero.setText("%d 件待办" % pending)
        elif done:
            self.hero.setText("今天已清空")
        else:
            self.hero.setText("今天还没有任务")

        overdue = [task for task in all_today if task.is_overdue(now)]
        if pending:
            parts = []
            if overdue:
                parts.append("%d 项已逾期" % len(overdue))
            if stats["high"]:
                parts.append("%d 项高优先" % stats["high"])
            due_times = [task.due_at for task in all_today if task.due_at]
            if due_times:
                parts.append("最近截止 " + human_due(min(due_times), now))
            sub = " · ".join(parts) if parts else "保持自己的节奏"
            self.summary_sub.setStyleSheet(
                "font-size: 11px; color: %s;" % (theme.HIGH if overdue else theme.MUTED)
            )
        elif done:
            sub = "已完成 %d 项 · 做得不错" % done
            self.summary_sub.setStyleSheet("font-size: 11px; color: %s;" % theme.MUTED)
        else:
            sub = "点击 + 记下第一件事"
            self.summary_sub.setStyleSheet("font-size: 11px; color: %s;" % theme.MUTED)
        self.summary_sub.setText(sub)
        self.ring.set_progress(done, total)
        self.section_count.setText("%d 项" % pending if pending else "无待办")

        next_task = all_today[0] if all_today else None
        empty_text = (
            "今天的任务都完成了 · 点击添加新任务"
            if done
            else "今天暂无待办 · 点击记下一件事"
        )
        self.next_card.set_task(next_task, empty_text, now)

        self._rebuild_rows(all_today, now)
        completed = self.store.repo.completed_today(now)
        if completed:
            self.completed_btn.setText("已完成 %d 项  ›" % len(completed))
            self.completed_btn.show()
        else:
            self.completed_btn.hide()
        if self._expanded and not self._animating:
            QTimer.singleShot(0, self._sync_expanded_height)

    def _rebuild_rows(self, tasks: List[Task], now: datetime) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        if tasks:
            for task in tasks:
                row = TaskRow(task, "float")
                row.set_task(task, now)
                row.completeRequested.connect(self.completeRequested.emit)
                row.undoRequested.connect(self.undoRequested.emit)
                row.editRequested.connect(self.editRequested.emit)
                row.deleteRequested.connect(self.deleteRequested.emit)
                self._rows.append(row)
                self.list_layout.addWidget(row)
            self.list_layout.addStretch(1)
            self.scroll.setFixedHeight(min(len(tasks), 5) * 60 + 4)
        else:
            empty = EmptyState("从一件小事开始", "点击上方 +，记下第一件事", "sun")
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            self.scroll.setFixedHeight(150)
        self.scroll.verticalScrollBar().setValue(0)

    # ------------------------------------------------------------------ expand
    @pyqtProperty(int)
    def windowHeight(self) -> int:
        return self.height()

    @windowHeight.setter
    def windowHeight(self, value: int) -> None:
        self.setFixedHeight(int(value))

    def _expanded_height(self) -> int:
        self.details.layout().activate()
        content_height = 46 + 10 + self.details.sizeHint().height()
        self.expandable.setFixedHeight(content_height)
        height = self.COMPACT_HEIGHT + 10 + content_height
        return max(self.COMPACT_HEIGHT + 10, min(690, int(height)))

    def _sync_expanded_height(self) -> None:
        if not self._expanded or self._animating:
            return
        target = self._expanded_height()
        if abs(target - self.height()) > 2:
            self._animate_height(target, 180, None)

    def set_expanded(self, expanded: bool, animate: bool = True, temporary: bool = False) -> None:
        expanded = bool(expanded)
        if temporary and expanded:
            self._attention_timer.start(14000)
        if not animate:
            self._height_anim.stop()
        if expanded == self._expanded:
            if expanded:
                self._sync_expanded_height()
            return
        self._expanded = expanded
        if expanded:
            self._expanded_height()
            self.expandable.setVisible(True)
            target = self._expanded_height()
            if animate:
                self._animate_height(target, 230, None)
            else:
                self._animating = False
                self.setFixedHeight(target)
        else:
            target = self._compact_height()
            # 收起时立刻移除全部任务详情，避免收缩动画里标题、进度和
            # 任务图标互相挤压；随后只让空白区域平滑收短。
            self.expandable.setVisible(False)
            if animate:
                self._animate_height(target, 180, self._after_collapse)
            else:
                self._animating = False
                self._after_collapse()

    def _animate_height(self, target: int, duration: int, finished) -> None:
        self._height_anim.stop()
        try:
            self._height_anim.finished.disconnect()
        except TypeError:
            pass
        self._animating = True
        self._height_anim.setStartValue(self.height())
        self._height_anim.setEndValue(int(target))
        self._height_anim.setDuration(duration)
        self._height_anim.setEasingCurve(QEasingCurve.OutCubic)
        if finished is not None:
            self._height_anim.finished.connect(finished)
        self._height_anim.finished.connect(self._animation_done)
        if duration <= 0:
            self.setFixedHeight(target)
            self._animation_done()
            return
        self._height_anim.start()

    def _animation_done(self) -> None:
        self._animating = False
        if self._expanded:
            self.setFixedHeight(self._expanded_height())
        else:
            self.setFixedHeight(self._compact_height())

    def _after_collapse(self) -> None:
        self.expandable.setVisible(False)
        self.setFixedHeight(self._compact_height())

    def _toast_visible(self) -> bool:
        return hasattr(self, "toast") and self.toast.isVisible()

    def _compact_height(self) -> int:
        """提示条显示时在底部留出一块空白，避免盖住进度摘要。"""
        return self.COMPACT_HEIGHT + (self.TOAST_SPACE if self._toast_visible() else 0)

    def _reserve_toast_space(self) -> None:
        if not self._expanded and not self._animating:
            self.setFixedHeight(self.COMPACT_HEIGHT + self.TOAST_SPACE)

    def _on_toast_hidden(self) -> None:
        if not self._expanded and not self._animating:
            self.setFixedHeight(self.COMPACT_HEIGHT)

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded, animate=True, temporary=not self._pinned)

    def _toggle_pin(self) -> None:
        self.set_pinned(not self._pinned)

    def set_pinned(self, pinned: bool, persist: bool = True) -> None:
        self._pinned = bool(pinned)
        if persist:
            self.config.set("floating_pinned", self._pinned)
            try:
                self.config.save()
            except OSError:
                pass
        self._update_pin_icon()
        if self._pinned:
            self._attention_timer.stop()
            self.set_expanded(True)
        elif not self.underMouse():
            self.set_expanded(False)

    def _update_pin_icon(self) -> None:
        if self._pinned:
            self.pin_btn.setIcon(icons.icon("pin_filled", theme.ACCENT, 16))
            self.pin_btn.setToolTip("取消固定展开")
        else:
            self.pin_btn.setIcon(icons.icon("pin", theme.MUTED, 16))
            self.pin_btn.setToolTip("固定展开")
        self.pin_btn.setIconSize(QSize(16, 16))

    # ------------------------------------------------------------------ hover
    def enterEvent(self, event) -> None:
        self._collapse_timer.stop()
        if self._hover_expand and not self._expanded and not self._modal_open:
            self._hover_timer.start(240)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_timer.stop()
        if self._expanded and not self._pinned and not self._modal_open and not self._menu_open:
            self._collapse_timer.start(620)
        super().leaveEvent(event)

    def _maybe_hover_expand(self) -> None:
        if (
            self._hover_expand
            and self.underMouse()
            and not self._expanded
            and not self._modal_open
            and not self._menu_open
        ):
            self.set_expanded(True, temporary=True)

    def _maybe_hover_collapse(self) -> None:
        if (
            self._expanded
            and not self._pinned
            and not self._modal_open
            and not self._menu_open
            and not self.underMouse()
        ):
            self.set_expanded(False)

    def _attention_timeout(self) -> None:
        if not self._pinned and not self.underMouse() and not self._modal_open:
            self.set_expanded(False)

    def begin_modal(self) -> None:
        self._modal_open = True
        self._collapse_timer.stop()

    def end_modal(self) -> None:
        self._modal_open = False
        if self._expanded and not self._pinned and not self.underMouse():
            self._collapse_timer.start(350)

    # ------------------------------------------------------------------ position
    def _restore_position(self) -> None:
        self.setFixedWidth(self.WIDTH)
        pos = self.config.get("floating_pos")
        available = QApplication.primaryScreen().availableGeometry()
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            x = available.right() - self.WIDTH - 24
            y = available.top() + 26
        x = max(available.left() + 8, min(x, available.right() - self.WIDTH - 8))
        y = max(available.top() + 8, min(y, available.bottom() - self.COMPACT_HEIGHT - 8))
        self.move(x, y)

    def _on_drag_finished(self) -> None:
        self._snap_to_screen()
        self.save_position()

    def _snap_to_screen(self) -> None:
        available = QApplication.primaryScreen().availableGeometry()
        x, y = self.x(), self.y()
        margin = 20
        if abs(x - (available.left() + 12)) <= margin:
            x = available.left() + 12
        if abs((x + self.width()) - (available.right() - 12)) <= margin:
            x = available.right() - self.width() - 12
        if abs(y - (available.top() + 12)) <= margin:
            y = available.top() + 12
        if abs((y + self.height()) - (available.bottom() - 12)) <= margin:
            y = available.bottom() - self.height() - 12
        x = max(available.left() + 6, min(x, available.right() - self.width() - 6))
        y = max(available.top() + 6, min(y, available.bottom() - self.height() - 6))
        self.move(x, y)

    def save_position(self) -> None:
        self.config.set("floating_pos", [self.x(), self.y()])
        try:
            self.config.save()
        except OSError:
            pass

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.isVisible():
            self._save_timer.start(700)

    def hideEvent(self, event) -> None:
        self.save_position()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        self.hide()
        self.hiddenToTray.emit()
        event.ignore()

    def set_quitting(self) -> None:
        self._quitting = True

    # ------------------------------------------------------------------ actions
    def _on_next_activated(self, task: Optional[Task]) -> None:
        if task is None:
            self.addRequested.emit()
        else:
            self.editRequested.emit(task.id)

    def _show_menu_at_button(self) -> None:
        if self._menu_open:
            return
        menu = self._build_menu()
        menu.ensurePolished()
        menu.adjustSize()
        # 菜单右边缘对齐“更多”按钮，并整体落在标题栏下方，
        # 这样不会盖住图钉、加号或三个点本身。
        anchor = self.more_btn.mapToGlobal(
            QPoint(self.more_btn.width(), self.more_btn.height() + 8)
        )
        x = anchor.x() - menu.width()
        y = anchor.y()
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(available.left() + 8, min(x, available.right() - menu.width() - 8))
            y = max(available.top() + 8, min(y, available.bottom() - menu.height() - 8))
        self._show_menu(QPoint(x, y), menu)

    def contextMenuEvent(self, event) -> None:
        self._show_menu(event.globalPos())

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        toggle = menu.addAction(
            icons.icon("chevron_up" if self._expanded else "chevron_down", theme.INK_SOFT, 16),
            "收起详情" if self._expanded else "展开详情",
        )
        toggle.triggered.connect(self._toggle_expanded)
        center = menu.addAction(icons.icon("calendar", theme.INK_SOFT, 16), "打开任务中心")
        center.triggered.connect(lambda: self.openCenterRequested.emit("today"))
        add = menu.addAction(icons.icon("plus", theme.ACCENT, 16), "新建任务")
        add.triggered.connect(self.addRequested.emit)
        settings = menu.addAction(icons.icon("settings", theme.INK_SOFT, 16), "设置")
        settings.triggered.connect(self.settingsRequested.emit)
        menu.addSeparator()
        hide_action = menu.addAction(icons.icon("eye_off", theme.MUTED, 16), "隐藏到托盘")
        hide_action.triggered.connect(self._hide_to_tray)
        quit_action = menu.addAction(icons.icon("close", theme.DANGER, 16), "退出日进")
        quit_action.triggered.connect(self.quitRequested.emit)
        return menu

    def _show_menu(self, position: QPoint, menu: QMenu = None) -> None:
        if self._menu_open:
            return
        self._menu_open = True
        self._hover_timer.stop()
        self._collapse_timer.stop()
        if menu is None:
            menu = self._build_menu()
        menu.exec_(position)
        self._menu_open = False
        if (
            self._expanded
            and not self._pinned
            and not self._modal_open
            and not self.underMouse()
        ):
            self._collapse_timer.start(400)

    def _hide_to_tray(self) -> None:
        self.hide()
        self.hiddenToTray.emit()

    def show_panel(self, expand_seconds: int = 0) -> None:
        self.show()
        self.raise_()
        if expand_seconds:
            self.set_expanded(True, temporary=True)
            self._attention_timer.start(expand_seconds * 1000)
        else:
            self.activateWindow()

    def show_attention(self, seconds: int = 14) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        if bool(self.config.get("auto_expand", True)):
            self.set_expanded(True, temporary=True)
            self._attention_timer.start(seconds * 1000)

    def show_toast(
        self,
        text: str,
        action_text: str = "",
        callback=None,
        msecs: int = 6000,
    ) -> None:
        self._reserve_toast_space()
        self.toast.show_message(text, action_text, callback, msecs)

    def apply_settings(self) -> None:
        self._hover_expand = bool(self.config.get("hover_expand", True))
        on_top = bool(self.config.get("always_on_top", True))
        if on_top != self._always_on_top:
            was_visible = self.isVisible()
            self._always_on_top = on_top
            flags = self.windowFlags()
            if on_top:
                flags |= Qt.WindowStaysOnTopHint
            else:
                flags &= ~Qt.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            if was_visible:
                self.show()
        if not self._hover_expand and self._expanded and not self._pinned:
            self.set_expanded(False)
        if bool(self.config.get("floating_pinned", False)) and not self._pinned:
            self.set_pinned(True, persist=False)

    def _clock_tick(self) -> None:
        now = now_local()
        if date_key(now) != self._current_date:
            self.refresh()
            return
        for row in self._rows:
            row.set_task(row.task, now)
        self.next_card._now = now
        self.next_card.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast.reposition()
