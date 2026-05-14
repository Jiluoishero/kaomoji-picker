from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app_logging import log


class KaomojiApp(QApplication):
    def __init__(self, argv, window_factory):
        super().__init__(argv)
        log("KaomojiApp init")
        self.setApplicationName("颜文字输入器")
        self.setApplicationDisplayName("颜文字输入器")
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.setQuitOnLastWindowClosed(False)
        self.window = window_factory()
        self.window.register_hotkey(self.window.config.get("hotkey", "ctrl+q"))
        log("KaomojiApp ready")
        self.tray = self._create_tray()
        self.aboutToQuit.connect(self.window.unregister_hotkey)
        self.aboutToQuit.connect(self.window._uninstall_keyboard_hook)

    def _create_tray(self):
        tray = QSystemTrayIcon(self._tray_icon(), self)
        tray.setToolTip("Kaomoji Picker")
        menu = QMenu()
        show_action = QAction("显示面板", self)
        show_action.triggered.connect(self.window.show_panel)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: self.window.show_panel() if reason == QSystemTrayIcon.Trigger else None)
        tray.show()
        return tray

    def _tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#7c6fef"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(18, 22, 8, 8)
        painter.drawEllipse(38, 22, 8, 8)
        painter.setPen(QColor("white"))
        painter.drawArc(23, 30, 18, 14, 0, -180 * 16)
        painter.end()
        return QIcon(pixmap)
