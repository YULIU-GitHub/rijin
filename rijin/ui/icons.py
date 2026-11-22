"""矢量风格图标与品牌标记，避免依赖外部图标包。"""
from __future__ import annotations

import math
from functools import lru_cache

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from . import theme


def _qcolor(value: str) -> QColor:
    return QColor(value)


def _pen(painter: QPainter, color: str, width: float = 1.8) -> None:
    pen = QPen(_qcolor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)


def _draw(name: str, painter: QPainter, color: str, s: float = 24.0) -> None:
    painter.save()
    painter.scale(s / 24.0, s / 24.0)
    painter.setRenderHint(QPainter.Antialiasing, True)
    _pen(painter, color, 1.8)
    if name == "plus":
        painter.drawLine(QPointF(12, 5.2), QPointF(12, 18.8))
        painter.drawLine(QPointF(5.2, 12), QPointF(18.8, 12))
    elif name == "check":
        path = QPainterPath()
        path.moveTo(5.0, 12.5)
        path.lineTo(10.0, 17.2)
        path.lineTo(19.5, 6.8)
        painter.drawPath(path)
    elif name == "close":
        painter.drawLine(QPointF(6.2, 6.2), QPointF(17.8, 17.8))
        painter.drawLine(QPointF(17.8, 6.2), QPointF(6.2, 17.8))
    elif name == "minimize":
        painter.drawLine(QPointF(6.5, 12), QPointF(17.5, 12))
    elif name == "settings":
        painter.drawEllipse(QPointF(12, 12), 3.1, 3.1)
        painter.drawEllipse(QPointF(12, 12), 7.2, 7.2)
        for index in range(8):
            angle = math.radians(index * 45)
            inner = QPointF(12 + 6.8 * math.cos(angle), 12 + 6.8 * math.sin(angle))
            outer = QPointF(12 + 9.4 * math.cos(angle), 12 + 9.4 * math.sin(angle))
            painter.drawLine(inner, outer)
    elif name in ("pin", "pin_filled"):
        path = QPainterPath()
        path.moveTo(8.0, 4.6)
        path.lineTo(16.0, 4.6)
        path.lineTo(14.7, 9.4)
        path.lineTo(17.0, 12.2)
        path.lineTo(7.0, 12.2)
        path.lineTo(9.3, 9.4)
        path.closeSubpath()
        if name == "pin_filled":
            painter.setBrush(_qcolor(color))
        painter.drawPath(path)
        painter.drawLine(QPointF(12.0, 12.4), QPointF(12.0, 20.2))
    elif name == "more":
        painter.setBrush(_qcolor(color))
        painter.setPen(Qt.NoPen)
        for x in (6.2, 12.0, 17.8):
            painter.drawEllipse(QPointF(x, 12), 1.35, 1.35)
    elif name == "chevron_down":
        painter.drawLine(QPointF(6.5, 9.5), QPointF(12.0, 15.0))
        painter.drawLine(QPointF(12.0, 15.0), QPointF(17.5, 9.5))
    elif name == "chevron_up":
        painter.drawLine(QPointF(6.5, 14.5), QPointF(12.0, 9.0))
        painter.drawLine(QPointF(12.0, 9.0), QPointF(17.5, 14.5))
    elif name == "chevron_right":
        painter.drawLine(QPointF(9.5, 6.5), QPointF(15.0, 12.0))
        painter.drawLine(QPointF(15.0, 12.0), QPointF(9.5, 17.5))
    elif name == "chevron_left":
        painter.drawLine(QPointF(14.5, 6.5), QPointF(9.0, 12.0))
        painter.drawLine(QPointF(9.0, 12.0), QPointF(14.5, 17.5))
    elif name == "edit":
        path = QPainterPath()
        path.moveTo(5.0, 19.0)
        path.lineTo(6.0, 14.6)
        path.lineTo(15.1, 5.5)
        path.lineTo(18.5, 8.9)
        path.lineTo(9.4, 18.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(13.1, 7.5), QPointF(16.5, 10.9))
    elif name == "trash":
        painter.drawLine(QPointF(4.8, 7.0), QPointF(19.2, 7.0))
        path = QPainterPath()
        path.moveTo(9.2, 7.0)
        path.lineTo(9.7, 4.4)
        path.lineTo(14.3, 4.4)
        path.lineTo(14.8, 7.0)
        painter.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(6.7, 7.2)
        path2.lineTo(7.6, 19.6)
        path2.lineTo(16.4, 19.6)
        path2.lineTo(17.3, 7.2)
        painter.drawPath(path2)
        painter.drawLine(QPointF(10.4, 10.4), QPointF(10.6, 16.6))
        painter.drawLine(QPointF(13.6, 10.4), QPointF(13.4, 16.6))
    elif name == "search":
        painter.drawEllipse(QPointF(10.7, 10.7), 5.6, 5.6)
        painter.drawLine(QPointF(15.0, 15.0), QPointF(20.0, 20.0))
    elif name == "calendar":
        painter.drawRoundedRect(QRectF(3.8, 5.8, 16.4, 14.4), 2.4, 2.4)
        painter.drawLine(QPointF(3.8, 10.2), QPointF(20.2, 10.2))
        painter.drawLine(QPointF(8.2, 3.4), QPointF(8.2, 7.4))
        painter.drawLine(QPointF(15.8, 3.4), QPointF(15.8, 7.4))
        painter.setBrush(_qcolor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(8.4, 14.2), 0.9, 0.9)
        painter.drawEllipse(QPointF(12.0, 14.2), 0.9, 0.9)
        painter.drawEllipse(QPointF(15.6, 14.2), 0.9, 0.9)
    elif name == "clock":
        painter.drawEllipse(QPointF(12, 12), 7.6, 7.6)
        painter.drawLine(QPointF(12, 7.2), QPointF(12, 12.0))
        painter.drawLine(QPointF(12, 12.0), QPointF(15.4, 14.1))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3.5, 7.0)
        path.lineTo(9.2, 7.0)
        path.lineTo(10.8, 9.6)
        path.lineTo(20.5, 9.6)
        path.lineTo(20.5, 18.8)
        path.lineTo(3.5, 18.8)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(3.5, 12.3), QPointF(20.5, 12.3))
    elif name == "undo":
        path = QPainterPath()
        path.moveTo(8.4, 7.4)
        path.lineTo(3.8, 11.6)
        path.lineTo(8.4, 15.8)
        painter.drawPath(path)
        painter.drawArc(QRectF(4.2, 4.0, 15.6, 15.6), 70 * 16, 250 * 16)
    elif name == "arrow_right":
        painter.drawLine(QPointF(4.8, 12), QPointF(19.0, 12))
        painter.drawLine(QPointF(13.2, 6.2), QPointF(19.0, 12))
        painter.drawLine(QPointF(19.0, 12), QPointF(13.2, 17.8))
    elif name == "eye":
        path = QPainterPath()
        path.moveTo(3.2, 12)
        path.cubicTo(6.4, 6.6, 17.6, 6.6, 20.8, 12)
        path.cubicTo(17.6, 17.4, 6.4, 17.4, 3.2, 12)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(12, 12), 2.6, 2.6)
    elif name == "eye_off":
        path = QPainterPath()
        path.moveTo(3.2, 12)
        path.cubicTo(6.4, 7.4, 17.6, 7.4, 20.8, 12)
        path.cubicTo(17.6, 16.6, 6.4, 16.6, 3.2, 12)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(12, 12), 2.6, 2.6)
        painter.drawLine(QPointF(4.5, 4.5), QPointF(19.5, 19.5))
    elif name == "export":
        painter.drawRoundedRect(QRectF(4.0, 10.0, 16.0, 9.5), 2.0, 2.0)
        painter.drawLine(QPointF(12.0, 3.5), QPointF(12.0, 14.0))
        painter.drawLine(QPointF(7.8, 7.7), QPointF(12.0, 3.5))
        painter.drawLine(QPointF(16.2, 7.7), QPointF(12.0, 3.5))
    elif name == "database":
        painter.drawEllipse(QPointF(12, 6.0), 7.0, 3.0)
        painter.drawLine(QPointF(5.0, 6.0), QPointF(5.0, 17.0))
        painter.drawLine(QPointF(19.0, 6.0), QPointF(19.0, 17.0))
        painter.drawArc(QRectF(5.0, 14.0, 14.0, 6.0), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(5.0, 8.5, 14.0, 6.0), 180 * 16, 180 * 16)
    elif name == "info":
        painter.drawEllipse(QPointF(12, 12), 8.3, 8.3)
        painter.setBrush(_qcolor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(12, 7.6), 1.15, 1.15)
        painter.setPen(QPen(_qcolor(color), 1.9, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(12, 10.8), QPointF(12, 17.0))
    elif name == "refresh":
        painter.drawArc(QRectF(4.6, 4.6, 14.8, 14.8), 40 * 16, 285 * 16)
        painter.drawLine(QPointF(17.8, 4.3), QPointF(18.6, 9.2))
        painter.drawLine(QPointF(18.6, 9.2), QPointF(13.8, 8.5))
    elif name == "sun":
        painter.drawEllipse(QPointF(12, 12), 4.2, 4.2)
        for index in range(8):
            angle = math.radians(index * 45)
            p1 = QPointF(12 + 6.3 * math.cos(angle), 12 + 6.3 * math.sin(angle))
            p2 = QPointF(12 + 8.8 * math.cos(angle), 12 + 8.8 * math.sin(angle))
            painter.drawLine(p1, p2)
    elif name == "menu":
        painter.drawLine(QPointF(5, 7), QPointF(19, 7))
        painter.drawLine(QPointF(5, 12), QPointF(19, 12))
        painter.drawLine(QPointF(5, 17), QPointF(19, 17))
    else:
        painter.drawEllipse(QPointF(12, 12), 6, 6)
    painter.restore()


@lru_cache(maxsize=256)
def icon(name: str, color: str = theme.INK_SOFT, size: int = 20) -> QIcon:
    result = QIcon()
    for logical in {size, max(16, size), max(24, size * 2)}:
        pixmap = QPixmap(logical * 2, logical * 2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.scale(2.0, 2.0)
        _draw(name, painter, color, float(logical))
        painter.end()
        result.addPixmap(pixmap)
    return result


def app_pixmap(size: int = 128, rounded: bool = True) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(_qcolor(theme.ACCENT))
    if rounded:
        painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.27, size * 0.27)
    else:
        painter.drawRect(0, 0, size, size)
    pen = QPen(_qcolor("#F5F1E5"))
    pen.setWidthF(size * 0.075)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(size * 0.26, size * 0.64)
    path.lineTo(size * 0.44, size * 0.46)
    path.lineTo(size * 0.72, size * 0.32)
    painter.drawPath(path)
    painter.setPen(Qt.NoPen)
    painter.setBrush(_qcolor("#D8A657"))
    painter.drawEllipse(QPointF(size * 0.735, size * 0.305), size * 0.058, size * 0.058)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    result = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        result.addPixmap(app_pixmap(size))
    return result


class LogoMark:
    """与图标一致的品牌圆角方块，供界面控件绘制使用。"""

    @staticmethod
    def draw(painter: QPainter, rect: QRectF, accent: str = theme.ACCENT) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_qcolor(accent))
        radius = min(rect.width(), rect.height()) * 0.29
        painter.drawRoundedRect(rect, radius, radius)
        pen = QPen(_qcolor("#F5F1E5"))
        pen.setWidthF(rect.width() * 0.075)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(rect.left() + rect.width() * 0.26, rect.top() + rect.height() * 0.64)
        path.lineTo(rect.left() + rect.width() * 0.44, rect.top() + rect.height() * 0.46)
        path.lineTo(rect.left() + rect.width() * 0.72, rect.top() + rect.height() * 0.32)
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_qcolor("#D8A657"))
        painter.drawEllipse(
            QPointF(rect.left() + rect.width() * 0.735, rect.top() + rect.height() * 0.305),
            rect.width() * 0.058,
            rect.width() * 0.058,
        )
        painter.restore()


def priority_polygon(rect: QRectF, color: str) -> QPolygonF:
    return QPolygonF(rect)
