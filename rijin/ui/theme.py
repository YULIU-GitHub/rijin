"""视觉主题：暖白纸感 + 墨绿强调色。

所有颜色和尺寸集中在这里，后续换肤只需要改这一处。
"""
from __future__ import annotations

from pathlib import Path

INK = "#20251F"
INK_SOFT = "#41473F"
MUTED = "#8B9085"
FAINT = "#B7BAAE"
CARD = "#FFFDF8"
CARD_ALT = "#F7F3EA"
CANVAS = "#F4F1E8"
LINE = "#E9E4D8"
LINE_STRONG = "#DCD5C5"
ACCENT = "#2E5B4C"
ACCENT_HOVER = "#254C3F"
ACCENT_SOFT = "#E8F0EA"
HIGH = "#C15B43"
HIGH_SOFT = "#F8E8E2"
AMBER = "#B58432"
AMBER_SOFT = "#F7EFDD"
LOW = "#718078"
LOW_SOFT = "#EBF0EC"
DANGER = "#B54A3B"
WHITE = "#FFFFFF"

FONT_STACK = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'


def _asset_url(asset_dir: Path, name: str) -> str:
    path = (Path(asset_dir) / name).resolve().as_posix()
    return 'url("%s")' % path


def stylesheet(asset_dir: Path) -> str:
    check = _asset_url(asset_dir, "check-white.png")
    chevron = _asset_url(asset_dir, "chevron-down.png")
    return """
* {
    font-family: %(font)s;
    outline: none;
}
QWidget {
    color: %(ink)s;
    font-size: 14px;
}
QMainWindow, QDialog {
    background: transparent;
}
QFrame#FloatCard, QFrame#CenterCard, QFrame#DialogCard {
    background: %(card)s;
    border: 1px solid %(line)s;
}
QFrame#FloatCard { border-radius: 22px; }
QFrame#CenterCard { border-radius: 24px; }
QFrame#DialogCard { border-radius: 22px; }
QWidget#Transparent { background: transparent; }
QFrame#SoftPanel {
    background: %(card_alt)s;
    border: none;
    border-radius: 16px;
}
QFrame#HairLine { background: %(line)s; border: none; max-height: 1px; }
QFrame#Toast {
    background: #242A24;
    border-radius: 13px;
}
QLabel { background: transparent; }
QLabel#AppTitle { font-size: 17px; font-weight: 700; color: %(ink)s; }
QLabel#AppSub { font-size: 11px; color: %(muted)s; }
QLabel#DialogTitle { font-size: 20px; font-weight: 700; color: %(ink)s; }
QLabel#DialogSub { font-size: 12px; color: %(muted)s; }
QLabel#PageTitle { font-size: 24px; font-weight: 700; color: %(ink)s; }
QLabel#PageSub { font-size: 12px; color: %(muted)s; }
QLabel#Hero { font-size: 25px; font-weight: 700; color: %(ink)s; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: %(ink_soft)s; }
QLabel#Muted { font-size: 12px; color: %(muted)s; }
QLabel#Micro { font-size: 11px; color: %(muted)s; }
QLabel#FieldLabel { font-size: 12px; font-weight: 600; color: %(ink_soft)s; }
QLabel#Error { font-size: 11px; color: %(danger)s; }
QLabel#ToastText { font-size: 12px; color: #F7F5EE; }
QLabel#ToastAction { font-size: 12px; color: #BFD9CA; font-weight: 700; }
QLabel#StatValue { font-size: 22px; font-weight: 700; color: %(ink)s; }
QLabel#StatLabel { font-size: 11px; color: %(muted)s; }
QLabel#NavCount { font-size: 10px; color: %(muted)s; }
QLabel#EmptyTitle { font-size: 13px; font-weight: 600; color: %(ink_soft)s; }
QLabel#EmptySub { font-size: 11px; color: %(muted)s; }
QLabel#DialogMeta { font-size: 11px; color: %(muted)s; }

QPushButton {
    font-family: %(font)s;
    border: none;
    background: transparent;
    color: %(ink)s;
    font-size: 13px;
    padding: 0 14px;
}
QPushButton[kind="primary"] {
    background: %(accent)s;
    color: #F9F7F0;
    border-radius: 10px;
    font-weight: 600;
    min-height: 38px;
}
QPushButton[kind="primary"]:hover { background: %(accent_hover)s; }
QPushButton[kind="primary"]:pressed { background: #1E4035; }
QPushButton[kind="primary"]:disabled { background: #B9C5BC; color: #EEF1EB; }
QPushButton[kind="soft"] {
    background: %(accent_soft)s;
    color: %(accent)s;
    border-radius: 10px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton[kind="soft"]:hover { background: #DDEAE2; }
QPushButton[kind="ghost"] {
    background: transparent;
    color: %(ink_soft)s;
    border-radius: 9px;
    min-height: 34px;
}
QPushButton[kind="ghost"]:hover { background: %(card_alt)s; }
QPushButton[kind="danger"] {
    background: transparent;
    color: %(danger)s;
    border-radius: 9px;
    min-height: 34px;
}
QPushButton[kind="danger"]:hover { background: %(high_soft)s; }
QPushButton[kind="dangerSolid"] {
    background: %(danger)s;
    color: white;
    border-radius: 10px;
    font-weight: 600;
    min-height: 38px;
}
QPushButton[kind="dangerSolid"]:hover { background: #9F3E31; }
QPushButton[kind="link"] {
    color: %(accent)s;
    padding: 0;
    font-size: 12px;
    text-align: left;
}
QPushButton[kind="link"]:hover { color: %(accent_hover)s; }
QPushButton[kind="seg"] {
    background: %(card_alt)s;
    color: %(muted)s;
    border-radius: 9px;
    min-height: 34px;
    padding: 0 18px;
    font-weight: 600;
}
QPushButton[kind="seg"]:hover { background: #EEEAE0; color: %(ink_soft)s; }
QPushButton[kind="seg"]:checked { background: %(accent)s; color: white; }
QPushButton[kind="seg"][tone="high"]:checked { background: %(high)s; color: white; }
QPushButton[kind="seg"][tone="mid"]:checked { background: %(amber)s; color: white; }
QPushButton[kind="nav"] {
    text-align: left;
    padding: 0 12px;
    min-height: 38px;
    border-radius: 10px;
    color: %(ink_soft)s;
    font-size: 13px;
}
QPushButton[kind="nav"]:hover { background: #EEEADF; }
QPushButton[kind="nav"]:checked {
    background: %(card)s;
    color: %(accent)s;
    font-weight: 700;
    border: 1px solid %(line)s;
}
QPushButton[kind="chip"] {
    background: transparent;
    border: 1px solid %(line_strong)s;
    border-radius: 14px;
    padding: 0 11px;
    min-height: 27px;
    font-size: 11px;
    color: %(muted)s;
}
QPushButton[kind="chip"]:hover { background: %(card_alt)s; color: %(ink_soft)s; }
QPushButton[kind="chip"]:checked {
    background: %(accent_soft)s;
    border-color: #C9DED2;
    color: %(accent)s;
    font-weight: 600;
}
QToolButton {
    border: none;
    background: transparent;
    border-radius: 9px;
    padding: 4px;
}
QToolButton:hover { background: %(card_alt)s; }
QToolButton:pressed { background: #ECE6DA; }
QToolButton#AccentButton {
    background: %(accent)s;
    border-radius: 13px;
    padding: 0;
}
QToolButton#AccentButton:hover { background: %(accent_hover)s; }
QToolButton#WindowButton { border-radius: 7px; }
QToolButton#WindowButton:hover { background: #EEE9DE; }
QToolButton#DangerButton:hover { background: %(high_soft)s; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateTimeEdit, QTimeEdit, QSpinBox {
    background: #FBFAF5;
    border: 1px solid %(line)s;
    border-radius: 9px;
    padding: 0 11px;
    color: %(ink)s;
    selection-background-color: %(accent)s;
    selection-color: white;
    min-height: 36px;
    font-size: 13px;
}
QTextEdit { padding: 9px 11px; }
QLineEdit:hover, QTextEdit:hover, QComboBox:hover, QDateTimeEdit:hover, QTimeEdit:hover {
    border-color: %(line_strong)s;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QTimeEdit:focus {
    border: 1px solid %(accent)s;
    background: %(card)s;
}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QDateTimeEdit:disabled, QTimeEdit:disabled {
    color: %(faint)s;
    background: #F5F2EA;
}
QTextEdit[error="true"] {
    border: 1px solid %(danger)s;
    background: #FFF9F7;
}
QComboBox::drop-down, QDateTimeEdit::drop-down, QTimeEdit::drop-down {
    border: none;
    width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow, QDateTimeEdit::down-arrow, QTimeEdit::down-arrow {
    image: %(chevron)s;
    width: 12px;
    height: 12px;
}
QComboBox QLineEdit {
    border: none;
    background: transparent;
    padding: 0;
    min-height: 0;
}
QComboBox QAbstractItemView {
    background: %(card)s;
    border: 1px solid %(line)s;
    border-radius: 8px;
    padding: 5px;
    outline: none;
    selection-background-color: %(accent_soft)s;
    selection-color: %(ink)s;
}
QDateTimeEdit::up-button, QDateTimeEdit::down-button,
QTimeEdit::up-button, QTimeEdit::down-button {
    width: 0px;
    height: 0px;
}
QCheckBox {
    spacing: 8px;
    color: %(ink_soft)s;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid %(line_strong)s;
    background: #FBFAF5;
}
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked {
    background: %(accent)s;
    border-color: %(accent)s;
    image: %(check)s;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0 2px 0;
}
QScrollBar::handle:vertical {
    background: #D9D3C5;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #C6BEAD; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu {
    background: %(card)s;
    border: 1px solid %(line)s;
    border-radius: 11px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 26px 8px 12px;
    border-radius: 7px;
    font-size: 12px;
    color: %(ink_soft)s;
}
QMenu::item:selected { background: %(accent_soft)s; color: %(accent)s; }
QMenu::separator { height: 1px; background: %(line)s; margin: 5px 8px; }
QMenu::icon { padding-left: 8px; }
QToolTip {
    background: #2A302A;
    color: #F7F5EE;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
QTabWidget::pane {
    border: none;
    background: transparent;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: %(muted)s;
    padding: 8px 16px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:hover { color: %(ink_soft)s; background: %(card_alt)s; }
QTabBar::tab:selected { color: %(accent)s; background: %(accent_soft)s; }
QDialog QLabel { color: %(ink)s; }
QMessageBox { background: %(card)s; }
""" % {
        "font": FONT_STACK,
        "ink": INK,
        "ink_soft": INK_SOFT,
        "muted": MUTED,
        "faint": FAINT,
        "card": CARD,
        "card_alt": CARD_ALT,
        "line": LINE,
        "line_strong": LINE_STRONG,
        "accent": ACCENT,
        "accent_hover": ACCENT_HOVER,
        "accent_soft": ACCENT_SOFT,
        "high": HIGH,
        "high_soft": HIGH_SOFT,
        "amber": AMBER,
        "danger": DANGER,
        "check": check,
        "chevron": chevron,
    }


def shadow_color():
    from PyQt5.QtGui import QColor

    return QColor(34, 39, 33, 46)
