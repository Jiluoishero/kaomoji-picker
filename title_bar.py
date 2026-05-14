import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget


class PinIcon(QWidget):
    """A tiny monochrome pushpin icon drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._color = QColor("#5A4E6B")

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(3, 2, 10, 10))
        needle = QPolygonF([QPointF(6.5, 11), QPointF(9.5, 11), QPointF(8, 16)])
        p.drawPolygon(needle)
        p.end()


class ThemeToggleButton(QToolButton):
    """Draws a monochrome crescent moon (light) or sun (dark) icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = False
        self._color = QColor("#5A4E6B")
        self.setText("")

    def set_theme(self, theme):
        self._is_dark = (theme == "dark")
        self._color = QColor("#e4e0d0" if self._is_dark else "#5A4E6B")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2

        if self._is_dark:
            # Sun: central disc + 8 rays
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
            p.drawEllipse(QPointF(cx, cy), 4.5, 4.5)
            pen = QPen(self._color, 1.8)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            for i in range(8):
                angle = i * math.pi / 4
                r1, r2 = 7, 10
                p.drawLine(
                    QPointF(cx + r1 * math.cos(angle), cy + r1 * math.sin(angle)),
                    QPointF(cx + r2 * math.cos(angle), cy + r2 * math.sin(angle)),
                )
        else:
            # Crescent moon via path subtraction
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
            full = QPainterPath()
            full.addEllipse(QRectF(cx - 7, cy - 7, 14, 14))
            cut = QPainterPath()
            cut.addEllipse(QRectF(cx - 2, cy - 9, 14, 14))
            p.drawPath(full.subtracted(cut))

        p.end()


class SettingsButton(QToolButton):
    """Draws a monochrome minimal gear icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#5A4E6B")
        self.setText("")

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)

        cx, cy = self.width() / 2, self.height() / 2
        teeth = 8
        outer_r = 10.5
        inner_r = 7.8
        hole_r = 3.8

        # Gear outline via alternating radii polygon
        path = QPainterPath()
        n = teeth * 4
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            r = outer_r if (i % 4 < 2) else inner_r
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()

        # Center hole
        hole = QPainterPath()
        hole.addEllipse(QPointF(cx, cy), hole_r, hole_r)
        p.drawPath(path.subtracted(hole))
        p.end()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_start = None
        self.window_start = None
        self.setObjectName("titlebar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(8)

        self.pin_icon = PinIcon()
        self.pin_icon.hide()
        layout.addWidget(self.pin_icon)
        layout.addStretch(1)

        theme = self.window.config.get("theme", "light") if self.window else "light"

        self.theme_button = ThemeToggleButton()
        self.theme_button.set_theme(theme)
        self.theme_button.setObjectName("titleIconButton")
        self.theme_button.setToolTip("切换深浅色主题")

        self.settings_button = SettingsButton()
        self.settings_button.setObjectName("titleIconButton")
        self.settings_button.setToolTip("设置")

        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setFont(QFont("Microsoft YaHei UI", 15))
        self.close_button.setToolTip("关闭")
        self.close_button.setObjectName("closeButton")

        for button in (self.theme_button, self.settings_button, self.close_button):
            button.setFixedSize(32, 32)
            layout.addWidget(button)

        self._apply_icon_colors(theme)

    def _apply_icon_colors(self, theme):
        c = "#e4e0d0" if theme == "dark" else "#5A4E6B"
        self.pin_icon.set_color(c)
        self.settings_button.set_color(c)
        self.theme_button.set_theme(theme)

    def set_mode(self, mode):
        if mode == "pinned":
            self.pin_icon.show()
        else:
            self.pin_icon.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint()
            self.window_start = self.window.pos()

    def mouseMoveEvent(self, event):
        if self.drag_start is None or not event.buttons() & Qt.LeftButton:
            return
        delta = event.globalPosition().toPoint() - self.drag_start
        self.window.move(self.window_start + delta)

    def mouseReleaseEvent(self, event):
        self.drag_start = None
        self.window_start = None
