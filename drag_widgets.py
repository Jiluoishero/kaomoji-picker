from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QTabBar, QWidget


class SortableTabBar(QTabBar):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setAcceptDrops(True)
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
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        theme = self.window.config.get("theme", "light") if self.window else "light"
        indicator_color = QColor("#d9b368") if theme == "dark" else QColor("#C67A25")
        feedback_brush = QColor(217, 179, 104, 30) if theme == "dark" else QColor(198, 122, 37, 30)

        # Draw the beautiful indicator with a dot break for the selected tab
        selected_index = self.currentIndex()
        if selected_index >= 0:
            rect = self.tabRect(selected_index)
            painter.setPen(Qt.NoPen)
            painter.setBrush(indicator_color)

            # Indicator geometry
            line_h = 3.5
            line_y = rect.bottom() - 4.5
            start_x = rect.left() + 12
            end_x = rect.right() - 16
            if end_x > start_x:
                painter.drawRoundedRect(QRectF(start_x, line_y, end_x - start_x, line_h), 1.75, 1.75)

            # Detached playful dot break
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
