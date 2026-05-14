from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QCheckBox, QFrame, QLineEdit, QPushButton, QTextEdit

from ui_helpers import draw_rounded_fill_box, in_dark_dialog, window_theme


class RoundedFrame(QFrame):
    def __init__(self, role, window=None):
        super().__init__()
        self.role = role
        self.window = window
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

    def _colors(self):
        theme = self.window.config.get("theme", "light") if self.window else window_theme(self)
        if self.role == "panel":
            if theme == "dark":
                gradient = QLinearGradient(0, 0, self.width(), self.height())
                gradient.setColorAt(0, QColor(14, 16, 36, 252))
                gradient.setColorAt(0.5, QColor(20, 18, 46, 252))
                gradient.setColorAt(1, QColor(13, 12, 28, 252))
                return gradient, QColor(217, 179, 104, 64), 30.0, 1.0
            return QColor(250, 246, 252, 252), QColor(195, 180, 210, 60), 30.0, 1.0
        if self.role == "sortBar":
            if theme == "dark":
                return QColor(22, 24, 46, 235), QColor(217, 179, 104, 64), 12.0, 1.0
            return QColor(245, 240, 248, 245), QColor(195, 180, 210, 50), 12.0, 1.0
        if self.role == "addBox":
            if theme == "dark":
                return QColor(22, 24, 46, 235), QColor(217, 179, 104, 51), 12.0, 1.0
            return QColor(245, 240, 248, 245), QColor(195, 180, 210, 45), 12.0, 1.0
        return QColor(0, 0, 0, 0), QColor(0, 0, 0, 0), 0.0, 0.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        background, border, radius, border_width = self._colors()
        if self.role == "panel":
            self._paint_panel(painter, background, border, radius, border_width)
            return
        draw_rounded_fill_box(painter, self.rect(), radius, background, border, border_width)

    def _paint_panel(self, painter, background, border, radius, border_width):
        outer_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        inner_rect = outer_rect.adjusted(border_width, border_width, -border_width, -border_width)
        inner_radius = max(0.0, radius - border_width)

        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer_rect, radius, radius)
        painter.fillPath(outer_path, border)

        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner_rect, inner_radius, inner_radius)
        painter.fillPath(inner_path, background)

        painter.save()
        painter.setClipPath(inner_path)
        title_h = 40.0
        theme = self.window.config.get("theme", "light") if self.window else window_theme(self)
        title_gradient = QLinearGradient(0, 0, 0, title_h)
        if theme == "dark":
            title_gradient.setColorAt(0, QColor(255, 255, 255, 15))
            title_gradient.setColorAt(1, QColor(255, 255, 255, 3))
            divider = QColor(217, 179, 104, 31)
        else:
            title_gradient.setColorAt(0, QColor(255, 255, 255, 140))
            title_gradient.setColorAt(1, QColor(255, 255, 255, 40))
            divider = QColor(195, 180, 210, 35)
        painter.fillRect(QRectF(0, 0, self.width(), title_h), title_gradient)
        painter.fillRect(QRectF(0, title_h - 1, self.width(), 1), divider)
        painter.restore()


class RoundedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def _colors(self):
        object_name = self.objectName()
        pressed = self.isDown()
        hovered = self.underMouse()
        theme = window_theme(self)
        if in_dark_dialog(self):
            if object_name == "dangerButton":
                return QColor(240, 72, 72, 46), QColor(240, 72, 72, 107), 7.0, 1.0
            if object_name == "primaryButton":
                return QColor(124, 111, 239, 61 if not hovered else 82), QColor(124, 111, 239, 112), 7.0, 1.0
            if hovered or pressed:
                return QColor(255, 255, 255, 28 if pressed else 19), QColor(255, 255, 255, 20), 7.0, 1.0
            return QColor(0, 0, 0, 0), QColor(0, 0, 0, 0), 7.0, 1.0
        if object_name == "dangerButton":
            return QColor(240, 72, 72, 46), QColor(240, 72, 72, 107), 7.0, 1.0
        if object_name == "primaryButton":
            if theme == "dark":
                bg = QColor(217, 179, 104, 89 if hovered else 56)
                border = QColor(217, 179, 104, 179 if hovered else 128)
            else:
                bg = QColor(198, 122, 37, 50 if hovered else 25)
                border = QColor(198, 122, 37, 150 if hovered else 90)
            if pressed:
                bg = bg.darker(110)
            return bg, border, 9.0, 1.0
        if hovered or pressed:
            if theme == "dark":
                bg = QColor(217, 179, 104, 64 if pressed else 31)
                border = QColor(217, 179, 104, 51)
            else:
                bg = QColor(198, 122, 37, 35 if pressed else 15)
                border = QColor(195, 180, 210, 50)
            return bg, border, 9.0, 1.0
        return QColor(0, 0, 0, 0), QColor(0, 0, 0, 0), 9.0, 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        background, border, radius, border_width = self._colors()
        if background.alpha() or border.alpha():
            draw_rounded_fill_box(painter, self.rect(), radius, background, border, border_width)
        painter.end()
        super().paintEvent(event)


class RoundedLineEdit(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setTextMargins(8, 0, 8, 0)

    def _colors(self):
        if in_dark_dialog(self):
            return QColor(18, 19, 31, 245), QColor(124, 111, 239, 163)
        theme = window_theme(self)
        focused = self.hasFocus()
        if theme == "dark":
            background = QColor(16, 18, 34, 245) if focused else QColor(12, 14, 28, 235)
            border = QColor("#d9b368") if focused else QColor(217, 179, 104, 64)
        else:
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 246, 252, 245)
            border = QColor("#C67A25") if focused else QColor(195, 180, 210, 80)
        return background, border

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        background, border = self._colors()
        draw_rounded_fill_box(painter, self.rect(), 10.0, background, border, 1.0)
        painter.end()
        super().paintEvent(event)


class RoundedTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setViewportMargins(8, 8, 8, 8)
        self.viewport().setAutoFillBackground(False)

    def _colors(self):
        theme = window_theme(self)
        focused = self.hasFocus()
        if theme == "dark":
            background = QColor(16, 18, 34, 245) if focused else QColor(12, 14, 28, 235)
            border = QColor("#d9b368") if focused else QColor(217, 179, 104, 64)
        else:
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 246, 252, 245)
            border = QColor("#C67A25") if focused else QColor(195, 180, 210, 80)
        return background, border

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        background, border = self._colors()
        draw_rounded_fill_box(painter, self.rect(), 10.0, background, border, 1.0)
        painter.end()
        super().paintEvent(event)


class RoundedSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.toggled.connect(self.update)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        theme = window_theme(self)
        checked = self.isChecked()
        hovered = self.underMouse()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if theme == "dark":
            background = QColor("#d9b368") if checked else (QColor(22, 24, 46, 245) if hovered else QColor(12, 14, 28, 245))
            border = QColor("#d9b368") if checked or hovered else QColor(217, 179, 104, 77)
            knob = QColor(18, 19, 31, 245) if checked else QColor(217, 179, 104, 180)
        else:
            background = QColor("#C67A25") if checked else (QColor(255, 255, 255, 255) if hovered else QColor(250, 246, 252, 245))
            border = QColor("#C67A25") if checked or hovered else QColor(195, 180, 210, 80)
            knob = QColor(255, 255, 255, 245) if checked else QColor(195, 180, 210, 180)

        draw_rounded_fill_box(painter, QRectF(2, 1, 42, 24), 12.0, background, border, 1.0)
        knob_x = 24 if checked else 6
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(knob_x, 5, 16, 16))
