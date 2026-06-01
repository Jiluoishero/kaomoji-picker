from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from kaomoji_picker.app_logging import log
from kaomoji_picker.app_paths import runtime_file


class KaomojiApp(QApplication):
    def __init__(self, argv, window_factory):
        super().__init__(argv)
        log("KaomojiApp init")
        self.setApplicationName("颜文字输入器")
        self.setApplicationDisplayName("颜文字输入器")
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.setQuitOnLastWindowClosed(False)
        self.app_icon = QIcon(runtime_file(__file__, "icon/icon.png"))
        self.setWindowIcon(self.app_icon)
        self.window = window_factory()
        self.window.setWindowIcon(self.app_icon)
        self.window.register_hotkey(self.window.config.get("hotkey", "ctrl+q"))
        log("KaomojiApp ready")
        self.tray = self._create_tray()
        self.aboutToQuit.connect(self.window.unregister_hotkey)
        self.aboutToQuit.connect(self.window._uninstall_keyboard_hook)

    def _create_tray(self):
        tray = QSystemTrayIcon(self.app_icon, self)
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
