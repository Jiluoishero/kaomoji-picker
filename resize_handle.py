from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


class ResizeHandle(QWidget):
    def __init__(self, window, direction, cursor):
        super().__init__(window)
        self.window = window
        self.direction = direction
        self.start_pos = None
        self.start_geometry = None
        self.setCursor(cursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.window._begin_manual_resize()
        self.start_pos = event.globalPosition().toPoint()
        self.start_geometry = self.window.geometry()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.start_pos is None or not event.buttons() & Qt.LeftButton:
            return
        self.window.resize_from_handle(
            self.direction,
            self.start_geometry,
            event.globalPosition().toPoint() - self.start_pos,
        )
        event.accept()

    def mouseReleaseEvent(self, event):
        self.start_pos = None
        self.start_geometry = None
        self.window._finish_manual_resize()
        event.accept()
