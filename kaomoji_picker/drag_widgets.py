from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QTabBar, QWidget


class SortableTabBar(QTabBar):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setAcceptDrops(True)
        self.setDrawBase(False)
        self.setElideMode(Qt.ElideNone)
        self.drop_target_index = -1

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.drop_target_index = index
                self.update()
                groups = self.window.data.get_groups()
                if index < len(groups):
                    event.acceptProposedAction()
            else:
                self.drop_target_index = -1
                self.update()
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.drop_target_index = -1
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            index = self.tabAt(event.position().toPoint())
            if index >= 0 and self.window._drop_symbol_on_group(event.mimeData(), index):
                self.drop_target_index = -1
                self.update()
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def paintEvent(self, event):
        scale = self.devicePixelRatioF()
        content = QPixmap(int(self.width() * scale), int(self.height() * scale))
        content.setDevicePixelRatio(scale)
        content.fill(Qt.transparent)
        content_painter = QPainter(content)
        content_painter.setRenderHint(QPainter.Antialiasing, True)

        self._paint_tabs(content_painter)
        content_painter.end()
        self._apply_overflow_mask(content)

        painter = QPainter(self)
        painter.drawPixmap(0, 0, content)

    def _paint_tabs(self, painter):
        theme = self.window.config.get("theme", "light") if self.window else "light"
        indicator_color = QColor("#d9b368") if theme == "dark" else QColor("#C67A25")
        feedback_brush = QColor(217, 179, 104, 30) if theme == "dark" else QColor(198, 122, 37, 30)

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            if not option.rect.isValid() or option.rect.right() < 0 or option.rect.left() > self.width():
                continue
            self.style().drawControl(QStyle.CE_TabBarTab, option, painter, self)

        selected_index = self.currentIndex()
        if selected_index >= 0:
            rect = self.tabRect(selected_index)
            if rect.isValid():
                painter.setPen(Qt.NoPen)
                painter.setBrush(indicator_color)

                line_h = 3.5
                line_y = rect.bottom() - 4.5
                start_x = rect.left() + 12
                end_x = rect.right() - 16
                if end_x > start_x:
                    painter.drawRoundedRect(QRectF(start_x, line_y, end_x - start_x, line_h), 1.75, 1.75)

                dot_x = rect.right() - 11
                painter.drawEllipse(QRectF(dot_x, line_y, line_h, line_h))

        if self.drop_target_index >= 0:
            rect = self.tabRect(self.drop_target_index)
            if rect.isValid():
                painter.setPen(Qt.NoPen)
                painter.setBrush(feedback_brush)
                painter.drawRoundedRect(rect.adjusted(1, 2, -1, -2), 9, 9)
                painter.setPen(indicator_color)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(1, 2, -1, -2), 9, 9)

    def _apply_overflow_mask(self, content):
        if self.count() <= 0 or self.width() <= 0:
            return

        tab_rects = [self.tabRect(index) for index in range(self.count())]
        has_left_overflow = any(rect.left() < 0 for rect in tab_rects)
        has_right_overflow = any(rect.right() > self.width() - 1 for rect in tab_rects)
        if not has_left_overflow and not has_right_overflow:
            return

        fade_width = min(72, max(42, self.width() // 4))
        transparent = QColor(0, 0, 0, 0)
        opaque = QColor(0, 0, 0, 255)

        painter = QPainter(content)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.setPen(Qt.NoPen)
        if has_left_overflow:
            gradient = QLinearGradient(0, 0, fade_width, 0)
            gradient.setColorAt(0.0, transparent)
            gradient.setColorAt(1.0, opaque)
            painter.fillRect(0, 0, fade_width, self.height(), gradient)
        if has_right_overflow:
            fade_start = self.width() - fade_width
            gradient = QLinearGradient(fade_start, 0, self.width(), 0)
            gradient.setColorAt(0.0, opaque)
            gradient.setColorAt(1.0, transparent)
            painter.fillRect(fade_start, 0, fade_width, self.height(), gradient)
        painter.end()


class SymbolContainer(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setAcceptDrops(True)
        self.insertion_index = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            self.insertion_index = self.window._symbol_insert_index_at(event.position().toPoint())
            self.update()
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.insertion_index = None
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-kaomoji-symbol"):
            if self.window._drop_symbol_at(event.mimeData(), event.position().toPoint()):
                self.insertion_index = None
                self.update()
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.insertion_index is None:
            return
        marker = self.window._symbol_insert_marker_rect(self.insertion_index)
        if marker is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#b8b0ff"))
        painter.drawRoundedRect(marker, 2, 2)
