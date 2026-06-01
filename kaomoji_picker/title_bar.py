import re

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

from kaomoji_picker.app_paths import runtime_file


def _icon_path(filename):
    return runtime_file(__file__, f"icon/{filename}")


def _colored_svg_renderer(filename, color):
    with open(_icon_path(filename), "r", encoding="utf-8") as f:
        svg = f.read()
    svg = re.sub(r'\sfilter="url\([^"]+\)"', "", svg)
    svg = re.sub(r"<defs>.*?</defs>", "", svg, flags=re.S)
    svg = svg.replace('fill="white"', f'fill="{color}"')
    return QSvgRenderer(QByteArray(svg.encode("utf-8")))


class SvgIconButton(QToolButton):
    icon_size = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("")
        self._icon_name = None
        self._color = "#5A4E6B"
        self._renderer = None
        self._icon_cache = None
        self._icon_cache_key = None

    def set_svg_icon(self, icon_name, color):
        self._icon_name = icon_name
        self._color = color
        self._renderer = _colored_svg_renderer(icon_name, color)
        self._icon_cache = None
        self._icon_cache_key = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._renderer:
            return
        painter = QPainter(self)
        size = min(self.icon_size, self.width(), self.height())
        x = (self.width() - size) / 2
        y = (self.height() - size) / 2
        pixmap = self._rendered_icon_pixmap(size)
        painter.drawPixmap(QRectF(x, y, size, size), pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.end()

    def _rendered_icon_pixmap(self, size):
        dpr = self.devicePixelRatioF()
        cache_key = (self._icon_name, self._color, size, dpr)
        if self._icon_cache is not None and self._icon_cache_key == cache_key:
            return self._icon_cache

        pixel_size = max(1, int(round(size * dpr)))
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        self._icon_cache = pixmap
        self._icon_cache_key = cache_key
        return pixmap


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


class ThemeToggleButton(SvgIconButton):
    def __init__(self, parent=None):
        super().__init__(parent)

    def set_theme(self, theme):
        color = "#e4e0d0" if theme == "dark" else "#5A4E6B"
        icon_name = "LightMode2-SVG.svg" if theme == "dark" else "DarkMode2-SVG.svg"
        self.set_svg_icon(icon_name, color)


class SettingsButton(SvgIconButton):
    def __init__(self, parent=None):
        super().__init__(parent)

    def set_color(self, color):
        self.set_svg_icon("Settings2-SVG.svg", color)


class CloseButton(SvgIconButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = "#5A4E6B"

    def set_color(self, color):
        self.set_svg_icon("Cross-SVG.svg", color)

    def enterEvent(self, event):
        self.set_svg_icon("Cross-SVG.svg", "#ffffff")
        super().enterEvent(event)

    def leaveEvent(self, event):
        theme = self.parentWidget().window.config.get("theme", "light") if self.parentWidget() else "light"
        self.set_color("#e4e0d0" if theme == "dark" else "#5A4E6B")
        super().leaveEvent(event)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_start = None
        self.window_start = None
        self.setObjectName("titlebar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 14, 0)
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

        self.close_button = CloseButton()
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
        self.close_button.set_color(c)

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
