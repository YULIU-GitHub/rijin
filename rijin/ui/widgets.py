"""可复用的自绘控件。

界面尽量用轻量自绘而不是大量 QSS 子控件：
- 圆角、留白、层级更可控；
- 高 DPI 下更稳定；
- 后续换主题只需要改 theme.py。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from ..core.models import Task
from ..core.time_utils import human_completed, human_due, human_short, now_local
from . import icons, theme


def add_shadow(widget: QWidget, blur: int = 44, y: int = 12, alpha: int = 46) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    color = QColor(31, 37, 30)
    color.setAlpha(alpha)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


def make_label(text: str = "", name: str = "", parent: QWidget = None) -> QLabel:
    label = QLabel(text, parent)
    if name:
        label.setObjectName(name)
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return label


def hline(parent: QWidget = None) -> QFrame:
    line = QFrame(parent)
    line.setObjectName("HairLine")
    line.setFixedHeight(1)
    return line


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_kind(widget: QWidget, kind: str) -> None:
    widget.setProperty("kind", kind)
    repolish(widget)


class LogoWidget(QWidget):
    def __init__(self, size: int = 36, parent: QWidget = None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        icons.LogoMark.draw(painter, QRectF(0, 0, self.width(), self.height()))


class VScrollArea(QScrollArea):
    """强制内容宽度跟随视口，避免任务行被压缩成窄条。"""

    def setWidget(self, widget: QWidget) -> None:
        super().setWidget(widget)
        self._sync_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_width()

    def _sync_width(self) -> None:
        widget = self.widget()
        if widget is None:
            return
        width = max(0, self.viewport().width())
        if width and widget.minimumWidth() != width:
            widget.setMinimumWidth(width)
        if width and widget.width() != width:
            widget.resize(width, widget.height())


class DragArea(QWidget):
    dragFinished = pyqtSignal()
    doubleClicked = pyqtSignal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._drag_offset: Optional[QPoint] = None
        self._moved = False
        self.setCursor(Qt.OpenHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.window().frameGeometry().topLeft()
            self._moved = False
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self._drag_offset)
            self._moved = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.setCursor(Qt.OpenHandCursor)
            if self._moved:
                self.dragFinished.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.doubleClicked.emit()
        event.accept()


class ProgressRing(QWidget):
    def __init__(self, parent: QWidget = None, size: int = 56):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._progress = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_progress(self, done: int, total: int) -> None:
        self._progress = 0.0 if total <= 0 else max(0.0, min(1.0, done / float(total)))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(5, 5, self.width() - 10, self.height() - 10)
        track = QPen(QColor("#EDE8DC"), 5)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)
        if self._progress > 0:
            arc = QPen(QColor(theme.ACCENT), 5)
            arc.setCapStyle(Qt.RoundCap)
            painter.setPen(arc)
            span = int(-360 * 16 * self._progress)
            painter.drawArc(rect, 90 * 16, span)
        painter.setPen(QColor(theme.INK))
        font = QFont("Microsoft YaHei UI")
        font.setPointSizeF(9.2)
        font.setWeight(QFont.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 0, self.width(), self.height()),
            int(Qt.AlignCenter),
            "%d%%" % int(round(self._progress * 100)),
        )


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._position = 1.0 if checked else 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_animation)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = False) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._position)
            self._animation.setEndValue(1.0 if checked else 0.0)
            self._animation.start()
        else:
            self._position = 1.0 if checked else 0.0
            self.update()
        self.toggled.emit(checked)

    def _on_animation(self, value) -> None:
        self._position = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        track = QColor(theme.ACCENT) if self._checked else QColor("#D8D5CA")
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 1, 42, 22), 11, 11)
        knob_x = 3 + self._position * 19
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, 4, 16, 16))
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
            painter.drawRoundedRect(QRectF(0.5, 0.5, 41, 23), 11, 11)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.setChecked(not self._checked, animate=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.setChecked(not self._checked, animate=True)
            event.accept()
            return
        super().keyPressEvent(event)


class TaskRow(QWidget):
    completeRequested = pyqtSignal(int)
    undoRequested = pyqtSignal(int)
    editRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)

    def __init__(self, task: Task, mode: str = "float", parent: QWidget = None):
        super().__init__(parent)
        self.task = task
        self.mode = mode
        self._hovered = False
        self._hover_zone = ""
        self._press_pos: Optional[QPoint] = None
        self._press_zone = ""
        self._completing = False
        self._now = now_local()
        self._font_detail = QFont("Microsoft YaHei UI")
        self._font_detail.setPointSizeF(10.6 if mode == "float" else 11.2)
        self._font_detail.setWeight(QFont.Medium)
        self._font_meta = QFont("Microsoft YaHei UI")
        self._font_meta.setPointSizeF(8.6 if mode == "float" else 9.2)
        self._font_time = QFont("Microsoft YaHei UI")
        self._font_time.setPointSizeF(8.6 if mode == "float" else 9.0)
        self._more_rect = QRectF()
        self._edit_rect = QRectF()
        self._delete_rect = QRectF()
        self._check_rect = QRectF()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setFixedHeight(58 if mode == "float" else 78)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.ArrowCursor)
        self._refresh_tooltip()
        self.setAccessibleName(task.detail)

    def set_task(self, task: Task, now: Optional[datetime] = None) -> None:
        self.task = task
        self._now = now or now_local()
        self._refresh_tooltip()
        self.update()

    def _refresh_tooltip(self) -> None:
        task = self.task
        project = task.project or "未归类"
        lines = [
            task.detail,
            "项目：%s" % project,
            "优先级：%s" % task.priority_name,
            "开始：%s" % human_short(task.started_at, self._now),
        ]
        if task.remind_at:
            lines.append("提醒：%s" % human_short(task.remind_at, self._now))
        if task.due_at:
            lines.append("拟完成：%s" % human_due(task.due_at, self._now))
        if task.note:
            lines.append("备注：%s" % task.note)
        lines.append("双击编辑 · 右键更多操作")
        self.setToolTip("\n".join(lines))

    # ------------------------------------------------------------------ painting
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = float(self.width())
        height = float(self.height())
        task = self.task

        if self._hovered or self.hasFocus():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#F7F3EA"))
            painter.drawRoundedRect(QRectF(0, 1, width - 1, height - 2), 11, 11)

        # 左侧优先级细线
        if task.is_done:
            bar_color = QColor(theme.FAINT)
        else:
            bar_color = QColor(task.priority_color)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bar_color)
        bar_h = 27 if self.mode == "float" else 34
        painter.drawRoundedRect(
            QRectF(7, (height - bar_h) / 2.0, 3, bar_h), 1.5, 1.5
        )

        # 完成圆点
        self._check_rect = QRectF(22, height / 2.0 - 9, 18, 18)
        checked = task.is_done or self._completing
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.ACCENT if not task.is_done else "#9BA79E"))
            painter.drawEllipse(self._check_rect)
            pen = QPen(QColor("#FFFFFF"), 1.9)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(self._check_rect.left() + 4.6, self._check_rect.top() + 9.2)
            path.lineTo(self._check_rect.left() + 7.8, self._check_rect.top() + 12.3)
            path.lineTo(self._check_rect.left() + 13.5, self._check_rect.top() + 5.8)
            painter.drawPath(path)
        else:
            border = QColor(theme.ACCENT) if self._hover_zone == "check" else QColor("#C4C9BF")
            painter.setPen(QPen(border, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self._check_rect)

        # 计算右侧区域
        action_space = 0.0
        if self.mode == "float":
            self._more_rect = QRectF(width - 29, height / 2.0 - 12, 24, 24)
            action_space = 24.0
        else:
            self._edit_rect = QRectF(width - 57, height / 2.0 - 12, 24, 24)
            self._delete_rect = QRectF(width - 29, height / 2.0 - 12, 24, 24)
            action_space = 62.0

        text_left = 47.0
        due_width = 0.0
        if self.mode == "float":
            due_width = 74.0
        elif not task.is_done and task.due_at:
            # 未悬停时右侧展示截止时间；悬停后让位给操作按钮。
            due_width = 0.0 if self._hovered else 150.0
        text_width = max(30.0, width - text_left - due_width - action_space - 6)

        detail_font = QFont(self._font_detail)
        if task.is_done:
            detail_font.setStrikeOut(True)
        painter.setFont(detail_font)
        painter.setPen(QColor(theme.MUTED if task.is_done else theme.INK))
        metrics = QFontMetrics(detail_font)
        detail = metrics.elidedText(task.detail, Qt.ElideRight, int(text_width))
        detail_top = 7.0 if self.mode == "float" else 12.0
        painter.drawText(
            QRectF(text_left, detail_top, text_width, 22),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            detail,
        )

        # 元信息：优先级胶囊 + 项目
        meta_top = 30.0 if self.mode == "float" else 39.0
        pill_rect = QRectF(text_left, meta_top + 1.5, 22, 15)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(task.priority_bg))
        painter.drawRoundedRect(pill_rect, 4.5, 4.5)
        painter.setFont(self._font_meta)
        painter.setPen(QColor(task.priority_color))
        painter.drawText(pill_rect, int(Qt.AlignCenter), task.priority_label)

        meta_x = text_left + 28
        meta_width = max(20.0, width - meta_x - due_width - action_space - 2)
        meta_parts = [task.project or "未归类"]
        if task.daily_prompt and not task.is_done:
            meta_parts.append("每日提示")
        if task.is_done and task.completed_at:
            meta_parts.append(human_completed(task.completed_at))
        elif self.mode == "center":
            meta_parts.append("开始 " + human_short(task.started_at, self._now))
        meta_text = "  ·  ".join(meta_parts)
        meta_metrics = QFontMetrics(self._font_meta)
        meta_text = meta_metrics.elidedText(meta_text, Qt.ElideRight, int(meta_width))
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(
            QRectF(meta_x, meta_top, meta_width, 18),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            meta_text,
        )

        # 右侧截止时间 / 操作
        if self.mode == "float":
            right_text = ""
            color = QColor(theme.MUTED)
            if task.is_done:
                right_text = human_completed(task.completed_at)
                color = QColor(theme.FAINT)
            elif task.due_at:
                right_text = human_due(task.due_at, self._now)
                color = QColor(theme.HIGH if task.is_overdue(self._now) else theme.MUTED)
            if right_text:
                painter.setFont(self._font_time)
                painter.setPen(color)
                painter.drawText(
                    QRectF(width - due_width - 2, 0, due_width, height),
                    int(Qt.AlignRight | Qt.AlignVCenter),
                    right_text,
                )
            if self._hovered and not task.is_done:
                self._paint_action(painter, self._more_rect, "more", theme.MUTED)
            elif self._hovered and task.is_done:
                self._paint_action(painter, self._more_rect, "more", theme.FAINT)
        else:
            if self._hovered:
                if task.is_done:
                    self._paint_action(painter, self._edit_rect, "undo", theme.ACCENT)
                else:
                    self._paint_action(painter, self._edit_rect, "edit", theme.MUTED)
                self._paint_action(painter, self._delete_rect, "trash", theme.MUTED)
            else:
                if task.due_at:
                    painter.setFont(self._font_time)
                    painter.setPen(QColor(theme.HIGH if task.is_overdue(self._now) else theme.MUTED))
                    painter.drawText(
                        QRectF(width - 150, 0, 140, height),
                        int(Qt.AlignRight | Qt.AlignVCenter),
                        human_due(task.due_at, self._now),
                    )

        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
            painter.drawRoundedRect(QRectF(1, 2, width - 3, height - 4), 10, 10)

    def _paint_action(self, painter: QPainter, rect: QRectF, name: str, color: str) -> None:
        zone = {"more": "more", "edit": "edit", "undo": "undo", "trash": "delete"}[name]
        if self._hover_zone == zone:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#EDE7DA"))
            painter.drawEllipse(rect)
        pixmap = icons.icon(name, color, 16).pixmap(16, 16)
        painter.drawPixmap(
            int(rect.center().x() - 8), int(rect.center().y() - 8), pixmap
        )

    # ------------------------------------------------------------------ interaction
    def _zone_at(self, point: QPoint) -> str:
        if self._check_rect.adjusted(-6, -6, 6, 6).contains(QPointF(point)):
            return "check"
        if self.mode == "float":
            if self._more_rect.adjusted(-4, -4, 4, 4).contains(QPointF(point)):
                return "more"
        else:
            if self._edit_rect.adjusted(-2, -4, 2, 4).contains(QPointF(point)):
                return "undo" if self.task.is_done else "edit"
            if self._delete_rect.adjusted(-2, -4, 2, 4).contains(QPointF(point)):
                return "delete"
        return ""

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            self._press_pos = event.pos()
            self._press_zone = self._zone_at(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._press_pos is not None:
            moved = (event.pos() - self._press_pos).manhattanLength()
            zone = self._zone_at(event.pos())
            self._press_pos = None
            if moved <= QApplication.startDragDistance() and zone == self._press_zone:
                self._activate_zone(zone)
            self._press_zone = ""
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _activate_zone(self, zone: str) -> None:
        if zone == "check":
            if self.task.is_done:
                self.undoRequested.emit(self.task.id)
            elif not self._completing:
                self._completing = True
                self.update()
                QTimer.singleShot(150, self._emit_complete)
        elif zone == "more":
            self._show_menu()
        elif zone == "edit":
            self.editRequested.emit(self.task.id)
        elif zone == "undo":
            self.undoRequested.emit(self.task.id)
        elif zone == "delete":
            self.deleteRequested.emit(self.task.id)

    def _emit_complete(self) -> None:
        if self._completing and self.task.is_pending:
            self.completeRequested.emit(self.task.id)
        self._completing = False

    def mouseMoveEvent(self, event) -> None:
        zone = self._zone_at(event.pos())
        if zone != self._hover_zone:
            self._hover_zone = zone
            self.update()
        cursor = Qt.PointingHandCursor if zone else Qt.ArrowCursor
        if self.cursor().shape() != cursor:
            self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._hover_zone = ""
        self.setCursor(Qt.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._zone_at(event.pos()):
            self.editRequested.emit(self.task.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        self._show_menu(event.globalPos())

    def _show_menu(self, position=None) -> None:
        menu = QMenu(self)
        edit_action = menu.addAction(icons.icon("edit", theme.INK_SOFT, 16), "编辑任务")
        if self.task.is_done:
            toggle_action = menu.addAction(icons.icon("undo", theme.ACCENT, 16), "撤销完成")
        else:
            toggle_action = menu.addAction(icons.icon("check", theme.ACCENT, 16), "标记完成")
        menu.addSeparator()
        delete_action = menu.addAction(icons.icon("trash", theme.DANGER, 16), "删除任务")
        chosen = menu.exec_(position or QCursor.pos())
        if chosen == edit_action:
            self.editRequested.emit(self.task.id)
        elif chosen == toggle_action:
            if self.task.is_done:
                self.undoRequested.emit(self.task.id)
            else:
                self._completing = True
                self.update()
                QTimer.singleShot(150, self._emit_complete)
        elif chosen == delete_action:
            self.deleteRequested.emit(self.task.id)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self._activate_zone("check")
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.editRequested.emit(self.task.id)
            event.accept()
            return
        if event.key() == Qt.Key_Delete:
            self.deleteRequested.emit(self.task.id)
            event.accept()
            return
        super().keyPressEvent(event)


class NavItem(QWidget):
    clicked = pyqtSignal()

    def __init__(
        self,
        text: str,
        icon_name: str = "",
        count: Optional[int] = None,
        dot_color: str = "",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.text = text
        self.icon_name = icon_name
        self.count = count
        self.dot_color = dot_color
        self.selected = False
        self._hovered = False
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    def set_selected(self, selected: bool) -> None:
        if self.selected != selected:
            self.selected = selected
            self.update()

    def set_count(self, count: Optional[int]) -> None:
        self.count = count
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width()
        if self.selected:
            painter.setPen(QPen(QColor(theme.LINE), 1))
            painter.setBrush(QColor(theme.CARD))
            painter.drawRoundedRect(QRectF(0.5, 0.5, width - 1, self.height() - 1), 10, 10)
        elif self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#EDE8DC"))
            painter.drawRoundedRect(QRectF(0, 1, width, self.height() - 2), 10, 10)
        x = 12.0
        if self.dot_color:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.dot_color))
            painter.drawEllipse(QRectF(12, 16, 7, 7))
            x = 28.0
        elif self.icon_name:
            pixmap = icons.icon(
                self.icon_name, theme.ACCENT if self.selected else theme.MUTED, 18
            ).pixmap(18, 18)
            painter.drawPixmap(12, int(self.height() / 2 - 9), pixmap)
            x = 39.0
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.setPen(QColor(theme.ACCENT if self.selected else theme.INK_SOFT))
        painter.drawText(
            QRectF(x, 0, width - x - 40, self.height()),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            self.text,
        )
        if self.count is not None:
            painter.setFont(QFont("Microsoft YaHei UI", 8))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(
                QRectF(width - 36, 0, 24, self.height()),
                int(Qt.AlignRight | Qt.AlignVCenter),
                str(self.count),
            )


class EmptyState(QWidget):
    def __init__(
        self,
        title: str = "今天还没有任务",
        subtitle: str = "点击右上角的 +，记下第一件事",
        icon_name: str = "check",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.icon_name = icon_name
        self.setMinimumHeight(144)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_texts(self, title: str, subtitle: str, icon_name: str = "check") -> None:
        self.title = title
        self.subtitle = subtitle
        self.icon_name = icon_name
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2.0, 42)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.CARD_ALT))
        painter.drawEllipse(center, 27, 27)
        pixmap = icons.icon(self.icon_name, theme.ACCENT, 24).pixmap(24, 24)
        painter.drawPixmap(int(center.x() - 12), int(center.y() - 12), pixmap)
        painter.setFont(self._font(10.8, QFont.DemiBold))
        painter.setPen(QColor(theme.INK_SOFT))
        painter.drawText(
            QRectF(0, 78, self.width(), 24), int(Qt.AlignCenter), self.title
        )
        painter.setFont(self._font(8.8))
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(
            QRectF(0, 102, self.width(), 22), int(Qt.AlignCenter), self.subtitle
        )

    @staticmethod
    def _font(size: float, weight=QFont.Normal) -> QFont:
        font = QFont("Microsoft YaHei UI")
        font.setPointSizeF(size)
        font.setWeight(weight)
        return font


class Toast(QFrame):
    """浮动卡片底部的轻提示，带即时撤销。"""

    hidden = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(44)
        self._callback: Optional[Callable[[], None]] = None
        self._full_text = ""
        self._showing = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(8)
        self.label = QLabel("")
        self.label.setObjectName("ToastText")
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.action = QPushButton("")
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.clicked.connect(self._on_action)
        self.action.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #BFD9CA;"
            " font-size: 12px; font-weight: 700; padding: 0 6px; }"
            "QPushButton:hover { color: #E6F1EA; }"
        )
        self.action.hide()
        self.close_button = QToolButton()
        self.close_button.setIcon(icons.icon("close", "#C8CEC5", 13))
        self.close_button.setIconSize(QSize(13, 13))
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 3px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 6px; }"
        )
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.action, 0)
        layout.addWidget(self.close_button, 0)
        add_shadow(self, 28, 6, 70)
        parent.installEventFilter(self)
        self.hide()

    def show_message(
        self,
        text: str,
        action_text: str = "",
        callback: Optional[Callable[[], None]] = None,
        msecs: int = 6000,
    ) -> None:
        self._full_text = text
        self.label.setToolTip(text)
        self._callback = callback
        if action_text and callback:
            self.action.setText(action_text)
            self.action.show()
        else:
            self.action.hide()
        self._timer.stop()
        self._timer.start(msecs)
        self._showing = True
        self.setFixedWidth(max(180, self.parentWidget().width() - 58))
        self._apply_elided_text()
        self.reposition()
        self.show()
        self.raise_()

    def _apply_elided_text(self) -> None:
        text = getattr(self, "_full_text", "")
        action_width = self.action.sizeHint().width() + 8 if not self.action.isHidden() else 0
        available = self.width() - 14 - 10 - action_width - 30 - 16
        metrics = QFontMetrics(self.label.font())
        self.label.setText(metrics.elidedText(text, Qt.ElideRight, max(40, available)))

    def _on_action(self) -> None:
        callback = self._callback
        self._callback = None
        self.hide()
        if callback:
            callback()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parentWidget() and event.type() == QEvent.Resize:
            self.reposition()
        return False

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = max(180, parent.width() - 58)
        if self.width() != width:
            self.setFixedWidth(width)
        self.move(
            int((parent.width() - self.width()) / 2),
            int(parent.height() - self.height() - 26),
        )

    def hideEvent(self, event) -> None:
        self._timer.stop()
        if self._showing:
            self._showing = False
            self.hidden.emit()
        super().hideEvent(event)
