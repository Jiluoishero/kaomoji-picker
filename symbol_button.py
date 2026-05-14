import json
import unicodedata

from PySide6.QtCore import QMimeData, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPainterPath, QTextCharFormat, QTextLayout
from PySide6.QtWidgets import QApplication, QFrame


class SymbolButton(QFrame):
    clicked = Signal()

    def __init__(self, symbol, font_resolver, window=None, group_index=0, item_index=0):
        super().__init__()
        self.symbol = symbol
        self.font_resolver = font_resolver
        self.window = window
        self.group_index = group_index
        self.item_index = item_index
        self.drag_start = None
        self.text_ranges = self._text_ranges(symbol, font_resolver)
        self.setObjectName("symbolButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("pressed", False)
        self.setAttribute(Qt.WA_StyledBackground, False)

        scale = self._scale()
        width = self._measure_width(symbol, font_resolver) + int(38 * scale)
        self.setMinimumWidth(max(int(42 * scale), width))
        self.setMinimumHeight(max(36, int(44 * scale)))

    def sizeHint(self):
        return QSize(self.minimumWidth(), self.minimumHeight())

    def minimumSizeHint(self):
        return self.sizeHint()

    def _base_font(self):
        font = QFont("Microsoft YaHei UI", self._font_size())
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

    def _scale(self):
        return self.window.content_scale if self.window else 1.0

    def _font_size(self):
        return max(8, int(round(12 * self._scale())))

    def _text_ranges(self, text, font_resolver):
        ranges = []
        current_start = 0
        current_length = 0
        current_family = None

        for index, ch in enumerate(text):
            if current_length and unicodedata.category(ch).startswith("M"):
                current_length += 1
                continue

            family = font_resolver(ch)
            if current_length and family == current_family:
                current_length += 1
            else:
                if current_length:
                    ranges.append((current_start, current_length, current_family))
                current_start = index
                current_length = 1
                current_family = family

        if current_length:
            ranges.append((current_start, current_length, current_family))
        return ranges

    def _format_ranges(self):
        formats = []
        is_pressed = self.property("pressed")
        is_hovered = self.underMouse()
        theme = self.window.config.get("theme", "light") if self.window else "light"
        if theme == "dark":
            text_color = QColor("#cca652") if is_pressed else (QColor("#d9b368") if is_hovered else QColor("#e4e8f4"))
        else:
            text_color = QColor("#A86015") if is_pressed else (QColor("#C67A25") if is_hovered else QColor("#5A4E6B"))
        for start, length, family in self.text_ranges:
            fmt = QTextCharFormat()
            font = QFont(family, self._font_size())
            font.setHintingPreference(QFont.PreferNoHinting)
            font.setStyleStrategy(QFont.PreferAntialias)
            fmt.setFont(font)
            fmt.setForeground(text_color)
            fmt_range = QTextLayout.FormatRange()
            fmt_range.start = start
            fmt_range.length = length
            fmt_range.format = fmt
            formats.append(fmt_range)
        return formats

    def _layout_text(self, line_width=10000):
        layout = QTextLayout(self.symbol, self._base_font())
        layout.setCacheEnabled(True)
        layout.setFormats(self._format_ranges())
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(line_width)
        line.setPosition(QPointF(0, 0))
        layout.endLayout()
        return layout, line

    def _measure_width(self, symbol, font_resolver):
        layout, line = self._layout_text()
        return int(line.naturalTextWidth() + 0.99)

    def _button_style(self):
        theme = self.window.config.get("theme", "light") if self.window else "light"
        is_pressed = bool(self.property("pressed"))
        is_hovered = self.underMouse()

        if theme == "dark":
            if is_pressed:
                background = QColor(217, 179, 104, 46)
                border = QColor(217, 179, 104, 204)
                border_width = 2.0
            elif is_hovered:
                background = QColor(42, 40, 78, 240)
                border = QColor(217, 179, 104, 128)
                border_width = 2.0
            else:
                background = QColor(28, 30, 56, 225)
                border = QColor(255, 255, 255, 10)
                border_width = 1.0
        else:
            if is_pressed:
                background = QColor(198, 122, 37, 30)
                border = QColor("#C67A25")
                border_width = 2.0
            elif is_hovered:
                background = QColor(255, 255, 255, 255)
                border = QColor(198, 122, 37, 120)
                border_width = 2.0
            else:
                background = QColor(255, 255, 255, 170)
                border = QColor(195, 180, 210, 45)
                border_width = 1.0

        return background, border, border_width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        background, border, border_width = self._button_style()
        outer_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        inner_rect = outer_rect.adjusted(border_width, border_width, -border_width, -border_width)

        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer_rect, 14, 14)
        painter.fillPath(outer_path, border)

        inner_path = QPainterPath()
        inner_radius = max(0.0, 14.0 - border_width)
        inner_path.addRoundedRect(inner_rect, inner_radius, inner_radius)
        painter.fillPath(inner_path, background)

        layout, line = self._layout_text(max(1, self.width() - int(12 * self._scale())))
        text_width = line.naturalTextWidth()
        text_height = line.height()
        x = max(0, (self.width() - text_width) / 2)
        y = max(0, (self.height() - text_height) / 2)
        if self.property("pressed"):
            y += 1
        layout.draw(painter, QPointF(x, y))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.position().toPoint()
            self.setProperty("pressed", True)
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            self.window
            and self.drag_start is not None
            and event.buttons() & Qt.LeftButton
            and (event.position().toPoint() - self.drag_start).manhattanLength() >= QApplication.startDragDistance()
        ):
            self.setProperty("pressed", False)
            self.update()
            payload = {
                "group_index": self.group_index,
                "item_index": self.item_index,
                "symbol": self.symbol,
            }
            mime = QMimeData()
            mime.setData("application/x-kaomoji-symbol", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.setHotSpot(event.position().toPoint())
            drag.exec(Qt.MoveAction)
            self.drag_start = None
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        was_pressed = self.property("pressed")
        self.setProperty("pressed", False)
        self.update()
        if was_pressed and self.drag_start is not None and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        self.drag_start = None
        event.accept()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()
