"""任务编辑、设置、确认等对话框。"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional

from PyQt5.QtCore import QDateTime, QSize, QTime, QTimer, QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core import autostart, backup
from ..core.config import Config, valid_time
from ..core.models import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM, Task
from ..core.paths import data_dir
from ..core.repository import Repository
from ..core.time_utils import now_local
from . import icons, theme
from .widgets import (
    DragArea,
    ToggleSwitch,
    add_shadow,
    hline,
    make_label,
    repolish,
)


def _primary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "primary")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(38)
    return button


def _ghost(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "ghost")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(36)
    return button


def _danger(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", "danger")
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedHeight(36)
    return button


def _ceil_half_hour(value: datetime) -> datetime:
    value = value.replace(second=0, microsecond=0)
    remainder = value.minute % 30
    if remainder:
        value += timedelta(minutes=30 - remainder)
    elif value.minute == 0:
        pass
    return value


class BaseDialog(QDialog):
    """无边框、带阴影和可拖动标题栏的对话框基类。"""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget = None,
        width: int = 600,
        accent: bool = False,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setWindowTitle(title)
        self._centered = False
        self._design_width = width

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSizeConstraint(QLayout.SetMinimumSize)
        self.card = QFrame()
        self.card.setObjectName("DialogCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        add_shadow(self.card, 48, 12, 55)
        outer.addWidget(self.card)

        inner = QVBoxLayout(self.card)
        inner.setContentsMargins(26, 22, 26, 22)
        inner.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.drag_area = DragArea()
        self.drag_area.setFixedHeight(44)
        drag_layout = QVBoxLayout(self.drag_area)
        drag_layout.setContentsMargins(0, 0, 0, 0)
        drag_layout.setSpacing(2)
        self.title_label = make_label(title, "DialogTitle")
        self.sub_label = make_label(subtitle, "DialogSub")
        self.sub_label.setVisible(bool(subtitle))
        drag_layout.addWidget(self.title_label)
        drag_layout.addWidget(self.sub_label)
        self.close_button = QToolButton()
        self.close_button.setObjectName("WindowButton")
        self.close_button.setIcon(icons.icon("close", theme.MUTED, 16))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setFixedSize(30, 30)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip("关闭")
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.drag_area, 1)
        header.addWidget(self.close_button, 0, Qt.AlignTop)
        inner.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        inner.addLayout(self.body)

        self.setFixedWidth(width)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            self._center_on_parent()

    def _center_on_parent(self) -> None:
        hint = self.sizeHint()
        self.resize(self._design_width, hint.height())
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else self.rect()
        parent = self.parentWidget()
        if parent is not None:
            geo = parent.window().frameGeometry()
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        else:
            x = available.center().x() - self.width() // 2
            y = available.center().y() - self.height() // 2
        x = max(available.left() + 16, min(x, available.right() - self.width() - 16))
        y = max(available.top() + 16, min(y, available.bottom() - self.height() - 16))
        self.move(x, y)


class ConfirmDialog(BaseDialog):
    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget = None,
        confirm_text: str = "确认",
        danger: bool = True,
    ):
        super().__init__(title, "", parent, width=470)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 13px; color: #4B5148; line-height: 1.6;")
        label.setMinimumHeight(48)
        self.body.addWidget(label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = _ghost("取消")
        cancel.clicked.connect(self.reject)
        ok = _primary(confirm_text) if not danger else QPushButton(confirm_text)
        if danger:
            ok.setProperty("kind", "dangerSolid")
            ok.setCursor(Qt.PointingHandCursor)
            ok.setFixedHeight(38)
            ok.setMinimumWidth(96)
        ok.clicked.connect(self.accept)
        footer.addWidget(cancel)
        footer.addWidget(ok)
        self.body.addSpacing(4)
        self.body.addLayout(footer)

    @classmethod
    def ask(
        cls,
        parent: QWidget,
        title: str,
        message: str,
        confirm_text: str = "确认",
        danger: bool = True,
    ) -> bool:
        dialog = cls(title, message, parent, confirm_text=confirm_text, danger=danger)
        return dialog.exec_() == QDialog.Accepted


class TaskDialog(BaseDialog):
    """新建 / 编辑任务。"""

    def __init__(
        self,
        parent: QWidget,
        repository: Repository,
        task: Optional[Task] = None,
    ):
        self.task = task
        self.repo = repository
        self.delete_requested = False
        super().__init__(
            "编辑任务" if task else "新建任务",
            "把要做的事写下来，剩下的交给节奏。",
            parent,
            width=600,
        )
        self._build()
        if task:
            self._fill(task)
        self._update_time_state()
        QTimer.singleShot(80, self.detail_edit.setFocus)

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        self.detail_edit = QTextEdit()
        self.detail_edit.setPlaceholderText("具体要做什么？例如：完成第三季度复盘初稿")
        self.detail_edit.setFixedHeight(78)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setAcceptRichText(False)
        self.detail_error = make_label("", "Error")
        self.detail_error.hide()
        self.body.addWidget(make_label("任务明细", "FieldLabel"))
        self.body.addWidget(self.detail_edit)
        self.body.addWidget(self.detail_error)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        project_box = QVBoxLayout()
        project_box.setSpacing(7)
        project_box.addWidget(make_label("从属项目", "FieldLabel"))
        self.project_combo = QComboBox()
        self.project_combo.setEditable(True)
        self.project_combo.setInsertPolicy(QComboBox.NoInsert)
        projects = self.repo.projects()
        if projects:
            self.project_combo.addItems(projects)
        self.project_combo.setCurrentIndex(-1)
        if self.project_combo.lineEdit():
            self.project_combo.lineEdit().setPlaceholderText("例如：工作 / 学习 / 生活")
        project_box.addWidget(self.project_combo)
        columns.addLayout(project_box, 3)

        priority_box = QVBoxLayout()
        priority_box.setSpacing(7)
        priority_box.addWidget(make_label("优先级", "FieldLabel"))
        priority_row = QHBoxLayout()
        priority_row.setSpacing(6)
        self.priority_group = QButtonGroup(self)
        for value, text, tone in (
            (PRIORITY_HIGH, "高", "high"),
            (PRIORITY_MEDIUM, "中", "mid"),
            (PRIORITY_LOW, "低", "low"),
        ):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setProperty("kind", "seg")
            button.setProperty("tone", tone)
            button.setFixedHeight(36)
            button.setMinimumWidth(58)
            button.setCursor(Qt.PointingHandCursor)
            self.priority_group.addButton(button, value)
            priority_row.addWidget(button)
        self.priority_group.button(PRIORITY_MEDIUM).setChecked(True)
        priority_box.addLayout(priority_row)
        columns.addLayout(priority_box, 2)
        self.body.addLayout(columns)

        self.time_panel = QFrame()
        self.time_panel.setObjectName("SoftPanel")
        self.time_panel.setAttribute(Qt.WA_StyledBackground, True)
        time_layout = QVBoxLayout(self.time_panel)
        time_layout.setContentsMargins(14, 12, 14, 12)
        time_layout.setSpacing(9)

        remind_row = QHBoxLayout()
        remind_row.setSpacing(10)
        self.remind_check = QCheckBox("提醒时间")
        self.remind_check.setChecked(True)
        self.remind_check.setFixedWidth(94)
        self.remind_edit = QDateTimeEdit()
        self.remind_edit.setDisplayFormat("yyyy/MM/dd  HH:mm")
        self.remind_edit.setCalendarPopup(True)
        self.remind_edit.setMinimumWidth(205)
        remind_row.addWidget(self.remind_check)
        remind_row.addWidget(self.remind_edit, 1)
        time_layout.addLayout(remind_row)

        daily_row = QHBoxLayout()
        daily_row.setContentsMargins(94, 0, 0, 0)
        self.daily_check = QCheckBox("每天在这个时间提示我")
        self.daily_check.setToolTip("开启后，该任务会每天进入汇总，并在提醒时间再次提示。")
        daily_row.addWidget(self.daily_check)
        daily_row.addStretch(1)
        time_layout.addLayout(daily_row)

        time_layout.addWidget(hline())

        due_row = QHBoxLayout()
        due_row.setSpacing(10)
        self.due_check = QCheckBox("拟完成时间")
        self.due_check.setChecked(True)
        self.due_check.setFixedWidth(94)
        self.due_edit = QDateTimeEdit()
        self.due_edit.setDisplayFormat("yyyy/MM/dd  HH:mm")
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setMinimumWidth(205)
        due_row.addWidget(self.due_check)
        due_row.addWidget(self.due_edit, 1)
        time_layout.addLayout(due_row)
        self.due_hint = make_label("到达拟完成时间时，会发出最后完成提醒。", "Micro")
        self.due_hint.setContentsMargins(104, 0, 0, 0)
        time_layout.addWidget(self.due_hint)
        self.body.addWidget(self.time_panel)

        self.time_error = make_label("", "Error")
        self.time_error.hide()
        self.body.addWidget(self.time_error)

        self.body.addWidget(make_label("备注（可选）", "FieldLabel"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("补充上下文、链接或提醒事项，可留空")
        self.body.addWidget(self.note_edit)

        self.meta_label = make_label(
            "开始时间将在保存时自动记录 · 每个任务都可以随时编辑", "DialogMeta"
        )
        if self.task is not None:
            self.meta_label.setText("")
        self.body.addWidget(self.meta_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        if self.task is not None:
            delete_button = _danger("删除任务")
            delete_button.setIcon(icons.icon("trash", theme.DANGER, 15))
            delete_button.clicked.connect(self._confirm_delete)
            footer.addWidget(delete_button)
        footer.addStretch(1)
        cancel = _ghost("取消")
        cancel.clicked.connect(self.reject)
        save = _primary("保存任务")
        save.setMinimumWidth(116)
        save.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        self.body.addSpacing(2)
        self.body.addLayout(footer)

        now = now_local()
        due_today = datetime.combine(now.date(), time(18, 0))
        if now < due_today - timedelta(hours=1):
            due_default = due_today
        else:
            candidate = _ceil_half_hour(now + timedelta(hours=2))
            if candidate.date() == now.date():
                due_default = candidate
            else:
                late = datetime.combine(now.date(), time(23, 30))
                due_default = (
                    late
                    if late >= now + timedelta(minutes=30)
                    else datetime.combine(now.date() + timedelta(days=1), time(12, 0))
                )
        remind_default = due_default - timedelta(hours=1)
        if remind_default <= now:
            remind_default = now + timedelta(minutes=30)
        self.remind_edit.setDateTime(QDateTime(remind_default))
        self.due_edit.setDateTime(QDateTime(due_default))
        self._set_priority(PRIORITY_MEDIUM)
        self._update_time_state()

        self.remind_check.toggled.connect(self._update_time_state)
        self.due_check.toggled.connect(self._update_time_state)
        self.daily_check.toggled.connect(self._on_daily_toggled)

    # ------------------------------------------------------------------ state
    def _fill(self, task: Task) -> None:
        self.detail_edit.setPlainText(task.detail)
        self.note_edit.setText(task.note)
        if task.project:
            self.project_combo.setCurrentText(task.project)
        else:
            self.project_combo.setCurrentIndex(-1)
            if self.project_combo.lineEdit():
                self.project_combo.lineEdit().clear()
        self._set_priority(task.priority)
        self.remind_check.setChecked(task.remind_at is not None)
        if task.remind_at:
            self.remind_edit.setDateTime(QDateTime(task.remind_at))
        self.due_check.setChecked(task.due_at is not None)
        if task.due_at:
            self.due_edit.setDateTime(QDateTime(task.due_at))
        self.daily_check.setChecked(bool(task.daily_prompt))
        started = task.started_at.strftime("%Y/%m/%d %H:%M")
        completed = task.completed_at.strftime("%Y/%m/%d %H:%M") if task.completed_at else "未完成"
        self.meta_label.setText(
            "开始时间（自动记录）：%s    完成时间：%s" % (started, completed)
        )
        self._update_time_state()

    def _set_priority(self, value: int) -> None:
        button = self.priority_group.button(value)
        if button:
            button.setChecked(True)

    def _on_daily_toggled(self, checked: bool) -> None:
        if checked and not self.remind_check.isChecked():
            self.remind_check.setChecked(True)
        self._update_time_state()

    def _update_time_state(self) -> None:
        remind_on = self.remind_check.isChecked()
        due_on = self.due_check.isChecked()
        self.remind_edit.setEnabled(remind_on)
        self.daily_check.setEnabled(remind_on)
        self.due_edit.setEnabled(due_on)
        self.due_hint.setEnabled(due_on)
        if not remind_on:
            self.daily_check.setChecked(False)

    # ------------------------------------------------------------------ actions
    def _save(self) -> None:
        detail = self.detail_edit.toPlainText().strip()
        if not detail:
            self.detail_error.setText("请填写任务明细。")
            self.detail_error.show()
            self.detail_edit.setProperty("error", True)
            repolish(self.detail_edit)
            self.detail_edit.setFocus()
            return
        self.detail_error.hide()
        self.detail_edit.setProperty("error", False)
        repolish(self.detail_edit)

        remind_at = self.remind_edit.dateTime().toPyDateTime() if self.remind_check.isChecked() else None
        due_at = self.due_edit.dateTime().toPyDateTime() if self.due_check.isChecked() else None
        if remind_at and due_at and due_at <= remind_at:
            self.time_error.setText("拟完成时间需要晚于提醒时间。")
            self.time_error.show()
            return
        self.time_error.hide()
        self.accept()

    def _confirm_delete(self) -> None:
        if self.task is None:
            return
        confirmed = ConfirmDialog.ask(
            self,
            "删除这个任务？",
            "「%s」将被永久删除，完成记录也会一并移除。\n这个操作无法撤销。"
            % self.task.detail,
            confirm_text="删除",
        )
        if confirmed:
            self.delete_requested = True
            self.accept()

    def values(self) -> Dict[str, Any]:
        remind_at = self.remind_edit.dateTime().toPyDateTime() if self.remind_check.isChecked() else None
        due_at = self.due_edit.dateTime().toPyDateTime() if self.due_check.isChecked() else None
        return {
            "detail": self.detail_edit.toPlainText().strip(),
            "project": self.project_combo.currentText().strip(),
            "priority": self.priority_group.checkedId(),
            "remind_at": remind_at,
            "due_at": due_at,
            "daily_prompt": self.daily_check.isChecked() and remind_at is not None,
            "note": self.note_edit.text().strip(),
        }


class SettingsDialog(BaseDialog):
    settingsSaved = pyqtSignal()

    def __init__(self, parent: QWidget, config: Config, repository: Repository):
        self.config = config
        self.repo = repository
        super().__init__(
            "设置",
            "让提醒适应你的节奏，而不是反过来。",
            parent,
            width=640,
        )
        self._build()

    def _build(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._general_tab(), "常规")
        self.tabs.addTab(self._reminder_tab(), "提醒")
        self.tabs.addTab(self._data_tab(), "数据")
        self.body.addWidget(self.tabs)

        self.status_label = make_label("", "Error")
        self.status_label.setWordWrap(True)
        footer = QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        cancel = _ghost("取消")
        cancel.clicked.connect(self.reject)
        save = _primary("保存设置")
        save.setMinimumWidth(116)
        save.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        self.body.addLayout(footer)

    def _toggle_row(
        self,
        layout: QVBoxLayout,
        title: str,
        description: str,
        checked: bool,
    ) -> ToggleSwitch:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(2, 7, 2, 7)
        row_layout.setSpacing(16)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.addWidget(make_label(title, "FieldLabel"))
        desc = make_label(description, "Micro")
        desc.setWordWrap(True)
        text_box.addWidget(desc)
        row_layout.addLayout(text_box, 1)
        toggle = ToggleSwitch(checked)
        row_layout.addWidget(toggle, 0, Qt.AlignVCenter)
        layout.addWidget(row)
        layout.addWidget(hline())
        return toggle

    def _general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 12)
        layout.setSpacing(0)
        layout.addWidget(make_label("启动与窗口", "SectionTitle"))
        layout.addSpacing(6)
        self.autostart_toggle = self._toggle_row(
            layout,
            "开机自动启动",
            "登录 Windows 后自动出现悬浮窗，随时看到今日进度。",
            autostart.is_enabled(),
        )
        self.always_on_top_toggle = self._toggle_row(
            layout,
            "总在最前",
            "悬浮窗始终浮在其他窗口上方，不被遮挡。",
            bool(self.config.get("always_on_top", True)),
        )
        self.hover_toggle = self._toggle_row(
            layout,
            "悬停展开详情",
            "鼠标移到悬浮窗上时展开任务列表，移开后自动收起。",
            bool(self.config.get("hover_expand", True)),
        )
        self.pinned_default_toggle = self._toggle_row(
            layout,
            "启动时展开",
            "开启后，每次启动都直接展示完整任务列表。",
            bool(self.config.get("floating_pinned", False)),
        )
        layout.addSpacing(18)
        note = QFrame()
        note.setObjectName("SoftPanel")
        note.setAttribute(Qt.WA_StyledBackground, True)
        note_layout = QVBoxLayout(note)
        note_layout.setContentsMargins(14, 12, 14, 12)
        note_layout.setSpacing(4)
        note_layout.addWidget(make_label("小提示", "FieldLabel"))
        tip = make_label(
            "拖动悬浮窗顶部可以移动位置；位置会自动记住。右键悬浮窗可以快速新建任务。",
            "Micro",
        )
        tip.setWordWrap(True)
        note_layout.addWidget(tip)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _reminder_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 12)
        layout.setSpacing(0)
        layout.addWidget(make_label("每日汇总", "SectionTitle"))
        layout.addSpacing(6)
        self.digest_toggle = self._toggle_row(
            layout,
            "启用每日汇总",
            "每天固定时间汇总今日到期、逾期和需要每日提示的任务。",
            bool(self.config.get("digest_enabled", True)),
        )
        time_row = QWidget()
        time_layout = QHBoxLayout(time_row)
        time_layout.setContentsMargins(2, 7, 2, 7)
        time_layout.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.addWidget(make_label("汇总时间", "FieldLabel"))
        text_box.addWidget(make_label("修改后立即生效，每天只提醒一次。", "Micro"))
        time_layout.addLayout(text_box, 1)
        self.digest_time = QTimeEdit()
        self.digest_time.setDisplayFormat("HH:mm")
        self.digest_time.setFixedWidth(92)
        self.digest_time.setTime(QTime.fromString(valid_time(str(self.config.get("digest_time", "09:00"))), "HH:mm"))
        time_layout.addWidget(self.digest_time)
        layout.addWidget(time_row)
        layout.addWidget(hline())
        layout.addSpacing(12)
        layout.addWidget(make_label("提醒行为", "SectionTitle"))
        layout.addSpacing(6)
        self.notify_toggle = self._toggle_row(
            layout,
            "显示系统通知",
            "任务提醒和每日汇总同时通过右下角通知提示。",
            bool(self.config.get("notifications_enabled", True)),
        )
        self.auto_expand_toggle = self._toggle_row(
            layout,
            "提醒时展开悬浮窗",
            "收到每日汇总或最后提醒时，自动展开任务列表。",
            bool(self.config.get("auto_expand", True)),
        )
        layout.addSpacing(16)
        note = QFrame()
        note.setObjectName("SoftPanel")
        note.setAttribute(Qt.WA_StyledBackground, True)
        note_layout = QVBoxLayout(note)
        note_layout.setContentsMargins(14, 12, 14, 12)
        note_layout.setSpacing(4)
        note_layout.addWidget(make_label("两种提醒", "FieldLabel"))
        tip = make_label(
            "「提醒时间」用于开始推进；「拟完成时间」是最后提示时间，到达后会提醒你确认是否完成。",
            "Micro",
        )
        tip.setWordWrap(True)
        note_layout.addWidget(tip)
        layout.addWidget(note)
        layout.addStretch(1)
        self.digest_toggle.toggled.connect(self.digest_time.setEnabled)
        self.digest_time.setEnabled(self.digest_toggle.isChecked())
        return page

    def _data_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 16, 4, 12)
        layout.setSpacing(10)
        layout.addWidget(make_label("本地数据", "SectionTitle"))
        path_label = QLabel(str(data_dir()))
        path_label.setWordWrap(True)
        path_label.setStyleSheet(
            "background: #F7F3EA; border-radius: 8px; padding: 10px;"
            "font-size: 11px; color: #6E746B;"
        )
        layout.addWidget(path_label)
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        open_button = QPushButton("打开数据目录")
        open_button.setProperty("kind", "soft")
        open_button.setCursor(Qt.PointingHandCursor)
        open_button.clicked.connect(self._open_data_dir)
        export_button = QPushButton("导出任务数据")
        export_button.setProperty("kind", "soft")
        export_button.setCursor(Qt.PointingHandCursor)
        export_button.clicked.connect(self._export_data)
        backup_button = QPushButton("立即备份")
        backup_button.setProperty("kind", "ghost")
        backup_button.setCursor(Qt.PointingHandCursor)
        backup_button.clicked.connect(self._backup_now)
        button_row.addWidget(open_button)
        button_row.addWidget(export_button)
        button_row.addWidget(backup_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self.data_status = make_label("", "Micro")
        self.data_status.setWordWrap(True)
        layout.addWidget(self.data_status)
        layout.addSpacing(8)
        layout.addWidget(hline())
        layout.addWidget(make_label("关于", "SectionTitle"))
        about = make_label(
            "日进 %s\n本地优先 · 任务数据只保存在这台电脑 · 不联网、不上传。\n"
            "程序与数据分离，后续可直接升级程序而不影响任务。" % __version__,
            "Micro",
        )
        about.setWordWrap(True)
        about.setStyleSheet("line-height: 1.7;")
        layout.addWidget(about)
        layout.addStretch(1)
        return page

    def _open_data_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    def _export_data(self) -> None:
        default = str(data_dir() / ("日进备份-%s.json" % now_local().strftime("%Y%m%d")))
        target, _ = QFileDialog.getSaveFileName(
            self, "导出任务数据", default, "JSON 文件 (*.json)"
        )
        if not target:
            return
        try:
            backup.export_json(self.repo, target, self.config.as_dict())
            self.data_status.setStyleSheet("font-size: 11px; color: #2E5B4C;")
            self.data_status.setText("已导出：%s" % target)
        except Exception as exc:
            self.data_status.setStyleSheet("font-size: 11px; color: #B54A3B;")
            self.data_status.setText("导出失败：%s" % exc)

    def _backup_now(self) -> None:
        try:
            target = backup.daily_backup(self.repo.db)
            self.data_status.setStyleSheet("font-size: 11px; color: #2E5B4C;")
            self.data_status.setText("数据库备份已保存：%s" % target)
        except Exception as exc:
            self.data_status.setStyleSheet("font-size: 11px; color: #B54A3B;")
            self.data_status.setText("备份失败：%s" % exc)

    def _save(self) -> None:
        self.status_label.setText("")
        values = {
            "digest_enabled": self.digest_toggle.isChecked(),
            "digest_time": self.digest_time.time().toString("HH:mm"),
            "notifications_enabled": self.notify_toggle.isChecked(),
            "auto_expand": self.auto_expand_toggle.isChecked(),
            "always_on_top": self.always_on_top_toggle.isChecked(),
            "hover_expand": self.hover_toggle.isChecked(),
            "floating_pinned": self.pinned_default_toggle.isChecked(),
        }
        if not autostart.set_enabled(self.autostart_toggle.isChecked()):
            self.status_label.setText("无法写入开机自启配置，请检查系统权限后重试。")
            return
        self.config.update(values)
        try:
            self.config.save()
        except OSError as exc:
            self.status_label.setText("保存配置失败：%s" % exc)
            return
        self.settingsSaved.emit()
        self.accept()
