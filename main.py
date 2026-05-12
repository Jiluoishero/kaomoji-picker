import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from clipboard_util import ClipboardUtil
from config_manager import ConfigManager
from data_manager import DataManager


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "debug.log")


def log(message):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


MIN_WINDOW_WIDTH = 360
MIN_WINDOW_HEIGHT = 320
DEFAULT_WINDOW_WIDTH = 420
DEFAULT_WINDOW_HEIGHT = 480

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_MOUSEACTIVATE = 0x0021
MA_NOACTIVATE = 3
PM_REMOVE = 0x0001
GWL_EXSTYLE = -20
GA_ROOT = 2
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
SW_SHOWNOACTIVATE = 4
SWP_NOMOVE = 0x0001
SWP_NOSIZE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", wintypes.POINT),
    ]


class HotkeyBridge(QObject):
    pressed = Signal()


class HotkeyThread:
    def __init__(self, bridge):
        self.bridge = bridge
        self.thread = None
        self.thread_id = None
        self.stop_event = threading.Event()

    def start(self, hotkey):
        self.stop()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(hotkey,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.6)
        self.thread = None
        self.thread_id = None

    def _run(self, hotkey):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        try:
            modifiers, key = parse_hotkey(hotkey)
        except ValueError as exc:
            print(exc)
            return

        if not ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, modifiers, key):
            err = ctypes.get_last_error()
            log(f"Failed to register hotkey '{hotkey}' (Win32 error {err})")
            return
        log(f"Registered hotkey '{hotkey}' modifiers={modifiers} key={key}")

        msg = MSG()
        try:
            while not self.stop_event.is_set():
                while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        log("Hotkey pressed")
                        self.bridge.pressed.emit()
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.01)
        finally:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            log(f"Unregistered hotkey '{hotkey}'")


def parse_hotkey(hotkey):
    modifiers = MOD_NOREPEAT
    key = None
    aliases = {
        "`": 0xC0,
        "grave": 0xC0,
        "space": win32con.VK_SPACE,
        "tab": win32con.VK_TAB,
        "enter": win32con.VK_RETURN,
        "return": win32con.VK_RETURN,
        "esc": win32con.VK_ESCAPE,
        "escape": win32con.VK_ESCAPE,
        "backspace": win32con.VK_BACK,
        "delete": win32con.VK_DELETE,
    }

    for part in [p.strip().lower() for p in hotkey.split("+") if p.strip()]:
        if part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part in ("win", "meta", "cmd"):
            modifiers |= MOD_WIN
        elif part in aliases:
            key = aliases[part]
        elif len(part) == 1 and part.isalpha():
            key = ord(part.upper())
        elif len(part) == 1 and part.isdigit():
            key = ord(part)
        elif part.startswith("f") and part[1:].isdigit():
            number = int(part[1:])
            if 1 <= number <= 24:
                key = win32con.VK_F1 + number - 1

    if key is None:
        raise ValueError(f"Unsupported hotkey: {hotkey}")
    return modifiers, key


class FlowLayout(QVBoxLayout):
    """Simple wrapped button layout built from rows, rebuilt on demand."""

    def __init__(self):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)
        self.rows = []

    def clear(self):
        while self.count():
            item = self.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.rows = []

    def add_wrapped(self, widgets, max_width):
        self.clear()
        row = None
        row_width = 0
        limit = max(240, max_width - 28)

        for widget in widgets:
            hint = widget.sizeHint().width() + 8
            if row is None or row_width + hint > limit:
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(6)
                row.addStretch(1)
                self.addWidget(row_widget)
                self.rows.append(row)
                row_width = 0
            row.insertWidget(row.count() - 1, widget)
            row_width += hint
        self.addStretch(1)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_start = None
        self.window_start = None
        self.setObjectName("titlebar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.mode_dot = QLabel()
        self.mode_dot.setObjectName("modeDot")
        self.mode_text = QLabel("单次")
        self.mode_text.setObjectName("modeText")
        layout.addWidget(self.mode_dot)
        layout.addWidget(self.mode_text)
        layout.addStretch(1)

        self.add_button = QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("添加符号")
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("设置")
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("关闭")
        self.close_button.setObjectName("closeButton")

        for button in (self.add_button, self.settings_button, self.close_button):
            button.setFixedSize(30, 30)
            layout.addWidget(button)

    def set_mode(self, mode):
        self.mode_text.setText("固定" if mode == "pinned" else "单次")
        self.mode_dot.setProperty("pinned", mode == "pinned")
        self.mode_dot.style().unpolish(self.mode_dot)
        self.mode_dot.style().polish(self.mode_dot)

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
        self.window._save_window_size()
        event.accept()


class KaomojiWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("颜文字输入器")
        self.config = ConfigManager()
        self.data = DataManager()
        self.clipboard = ClipboardUtil()
        self.current_group_index = 0
        self.mode = "single"
        self.last_hotkey_time = 0
        self.prev_window_handle = None
        self.allow_activation = False
        self.edit_mode = False
        self.add_mode = False
        self.outside_timer = QTimer(self)
        self.outside_timer.timeout.connect(self._check_outside_click)
        self._outside_mouse_was_down = False
        self.show_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.show_animation.setDuration(120)
        self.show_animation.setEasingCurve(QEasingCurve.OutCubic)

        flags = (
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self._resize_from_config()
        self._build_ui()
        self._apply_styles()
        self._apply_window_activation_policy()
        self._apply_dwm_window_style()

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    log("WM_HOTKEY")
                    self.handle_hotkey()
                    return True, 0
                if not self.allow_activation and msg.message == WM_MOUSEACTIVATE:
                    return True, MA_NOACTIVATE
            except Exception as exc:
                log(f"nativeEvent failed: {exc}")
        return super().nativeEvent(event_type, message)

    def _hwnd(self):
        hwnd = int(self.winId())
        if sys.platform == "win32" and hwnd:
            try:
                root = win32gui.GetAncestor(hwnd, GA_ROOT)
                if root:
                    return root
            except Exception:
                pass
        return hwnd

    def _visible_panel_hwnd(self):
        pid = os.getpid()
        candidates = []
        expected_w = self.width()
        expected_h = self.height()
        expected_x = self.x()
        expected_y = self.y()

        def enum(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid != pid:
                    return
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top
                if abs(width - expected_w) > 80 or abs(height - expected_h) > 80:
                    return
                distance = abs(left - expected_x) + abs(top - expected_y)
                candidates.append((distance, hwnd))
            except Exception:
                pass

        win32gui.EnumWindows(enum, None)
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]
        return self._hwnd()

    def _apply_window_activation_policy(self):
        if sys.platform != "win32":
            return
        hwnd = self._visible_panel_hwnd() if self.isVisible() else self._hwnd()
        ex_style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_TOOLWINDOW
        ex_style &= ~WS_EX_APPWINDOW
        if self.allow_activation:
            ex_style &= ~WS_EX_NOACTIVATE
        else:
            ex_style |= WS_EX_NOACTIVATE
        win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)

    def _apply_dwm_window_style(self):
        if sys.platform != "win32":
            return
        hwnd = self._visible_panel_hwnd() if self.isVisible() else self._hwnd()
        try:
            corner = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner),
                ctypes.sizeof(corner),
            )
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(dark),
                ctypes.sizeof(dark),
            )
        except Exception as exc:
            log(f"DWM style failed: {exc}")

    def _set_allow_activation(self, enabled):
        self.allow_activation = bool(enabled)
        self._apply_window_activation_policy()

    def register_hotkey(self, hotkey):
        if sys.platform != "win32":
            return
        self.unregister_hotkey()
        try:
            modifiers, key = parse_hotkey(hotkey)
        except ValueError as exc:
            log(str(exc))
            return
        hwnd = self._hwnd()
        if ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID, modifiers, key):
            log(f"Registered window hotkey '{hotkey}' hwnd={hwnd} modifiers={modifiers} key={key}")
        else:
            log(f"Failed to register window hotkey '{hotkey}' error={ctypes.get_last_error()} hwnd={hwnd}")

    def unregister_hotkey(self):
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.user32.UnregisterHotKey(self._hwnd(), HOTKEY_ID)
        except Exception:
            pass

    def _resize_from_config(self):
        width = int(self.config.get("window_width", DEFAULT_WINDOW_WIDTH))
        height = int(self.config.get("window_height", DEFAULT_WINDOW_HEIGHT))
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            max_width = max(MIN_WINDOW_WIDTH, int(area.width() * 0.9))
            max_height = max(MIN_WINDOW_HEIGHT, int(area.height() * 0.9))
        else:
            max_width = 1200
            max_height = 900
        width = min(max(MIN_WINDOW_WIDTH, width), max_width)
        height = min(max(MIN_WINDOW_HEIGHT, height), max_height)
        self.resize(width, height)
        if width != self.config.get("window_width") or height != self.config.get("window_height"):
            self.config.set("window_width", width)
            self.config.set("window_height", height)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        self.panel.setAutoFillBackground(False)
        root.addWidget(self.panel)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.titlebar = TitleBar(self)
        panel_layout.addWidget(self.titlebar)
        self.titlebar.add_button.clicked.connect(self._toggle_add_mode)
        self.titlebar.settings_button.clicked.connect(self._show_settings)
        self.titlebar.close_button.clicked.connect(self.hide_panel)

        self.stack = QStackedWidget()
        panel_layout.addWidget(self.stack, 1)
        self._build_main_view()
        self._build_settings_view()

        self.resize_handles = {}
        handle_specs = {
            "n": Qt.SizeVerCursor,
            "s": Qt.SizeVerCursor,
            "e": Qt.SizeHorCursor,
            "w": Qt.SizeHorCursor,
            "ne": Qt.SizeBDiagCursor,
            "sw": Qt.SizeBDiagCursor,
            "nw": Qt.SizeFDiagCursor,
            "se": Qt.SizeFDiagCursor,
        }
        for direction, cursor in handle_specs.items():
            handle = ResizeHandle(self, direction, cursor)
            handle.raise_()
            self.resize_handles[direction] = handle
        self._position_resize_handles()

    def _build_main_view(self):
        self.main_view = QWidget()
        layout = QVBoxLayout(self.main_view)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._set_current_group)
        self.tabs.tabMoved.connect(self._reorder_groups)
        tab_row.addWidget(self.tabs, 1)
        self.add_group_button = QPushButton("+")
        self.add_group_button.setFixedSize(28, 28)
        self.add_group_button.clicked.connect(self._add_group)
        self.add_group_button.hide()
        tab_row.addWidget(self.add_group_button)
        layout.addLayout(tab_row)

        self.add_box = QFrame()
        self.add_box.setObjectName("addBox")
        add_layout = QVBoxLayout(self.add_box)
        add_layout.setContentsMargins(10, 10, 10, 10)
        self.add_hint = QLabel("每行输入一个符号")
        self.add_text = QTextEdit()
        self.add_text.setFixedHeight(76)
        add_buttons = QHBoxLayout()
        add_buttons.addStretch(1)
        cancel = QPushButton("取消")
        confirm = QPushButton("确认添加")
        cancel.clicked.connect(self._exit_add_mode)
        confirm.clicked.connect(self._confirm_add)
        add_buttons.addWidget(cancel)
        add_buttons.addWidget(confirm)
        add_layout.addWidget(self.add_hint)
        add_layout.addWidget(self.add_text)
        add_layout.addLayout(add_buttons)
        self.add_box.hide()
        layout.addWidget(self.add_box)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.symbol_container = QWidget()
        self.symbol_layout = FlowLayout()
        self.symbol_container.setLayout(self.symbol_layout)
        self.scroll.setWidget(self.symbol_container)
        layout.addWidget(self.scroll, 1)

        self.stack.addWidget(self.main_view)

    def _build_settings_view(self):
        self.settings_view = QWidget()
        layout = QVBoxLayout(self.settings_view)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        back = QPushButton("‹")
        back.setFixedSize(30, 30)
        back.clicked.connect(self._show_main)
        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        header.addWidget(back)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        hotkey_row = self._setting_row("快捷键", "全局唤起面板")
        self.hotkey_edit = QLineEdit(self.config.get("hotkey", "ctrl+`"))
        self.hotkey_edit.setFixedWidth(150)
        self.hotkey_edit.editingFinished.connect(self._update_hotkey)
        hotkey_row.addWidget(self.hotkey_edit)
        layout.addLayout(hotkey_row)

        auto_row = self._setting_row("开机自启", "登录 Windows 后自动运行")
        self.autostart_check = QCheckBox()
        self.autostart_check.setChecked(bool(self.config.get("auto_start", False)))
        self.autostart_check.toggled.connect(self._set_auto_start)
        auto_row.addWidget(self.autostart_check)
        layout.addLayout(auto_row)

        edit_row = self._setting_row("编辑模式", "删除符号、管理分组")
        self.edit_check = QCheckBox()
        self.edit_check.toggled.connect(self._set_edit_mode)
        edit_row.addWidget(self.edit_check)
        layout.addLayout(edit_row)

        layout.addStretch(1)
        self.stack.addWidget(self.settings_view)

    def _setting_row(self, label, desc):
        row = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel(label)
        title.setObjectName("settingLabel")
        subtitle = QLabel(desc)
        subtitle.setObjectName("settingDesc")
        text.addWidget(title)
        text.addWidget(subtitle)
        row.addLayout(text)
        row.addStretch(1)
        return row

    def _apply_styles(self):
        self.setStyleSheet(
            """
            #panel {
                background: rgba(21, 22, 33, 246);
                border: 1px solid #282a42;
                border-radius: 14px;
            }
            #titlebar {
                background: rgba(255, 255, 255, 0.035);
                border-bottom: 1px solid #282a42;
            }
            #modeDot {
                min-width: 7px; max-width: 7px;
                min-height: 7px; max-height: 7px;
                border-radius: 4px;
                background: #7c6fef;
            }
            #modeDot[pinned="true"] { background: #34d399; }
            #modeText, QLabel { color: #cdd6f4; font-family: "Microsoft YaHei UI", "Segoe UI"; }
            #modeText { color: #a6adc8; font-size: 12px; }
            QToolButton, QPushButton {
                background: transparent;
                color: #cdd6f4;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QToolButton:hover, QPushButton:hover { background: #222440; }
            QToolButton#closeButton:hover { background: #f04848; color: white; }
            QTabBar::tab {
                color: #a6adc8;
                background: transparent;
                padding: 6px 14px;
                border-radius: 7px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #9f95f7;
                background: rgba(124, 111, 239, 0.16);
            }
            QScrollArea, QWidget { background: transparent; }
            QPushButton[symbol="true"] {
                background: rgba(34, 36, 64, 220);
                border: 1px solid transparent;
                border-radius: 9px;
                padding: 7px 14px;
                color: #e4e8f4;
                font-size: 14px;
            }
            QPushButton[symbol="true"]:hover {
                background: rgba(42, 45, 80, 235);
                border-color: #363858;
            }
            #addBox {
                background: #1a1c2e;
                border: 1px solid #282a42;
                border-radius: 10px;
            }
            QTextEdit, QLineEdit {
                color: #e4e8f4;
                background: #0f1019;
                border: 1px solid #363858;
                border-radius: 8px;
                padding: 7px;
            }
            #settingsTitle { font-size: 15px; font-weight: 600; }
            #settingLabel { font-size: 13px; font-weight: 600; }
            #settingDesc { font-size: 11px; color: #8a8faa; }
            """
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_handles()
        QTimer.singleShot(0, self._render_symbols)

    def _position_resize_handles(self):
        if not hasattr(self, "resize_handles"):
            return
        edge = 8
        corner = 16
        w = self.width()
        h = self.height()
        self.resize_handles["n"].setGeometry(corner, 0, max(0, w - corner * 2), edge)
        self.resize_handles["s"].setGeometry(corner, h - edge, max(0, w - corner * 2), edge)
        self.resize_handles["e"].setGeometry(w - edge, corner, edge, max(0, h - corner * 2))
        self.resize_handles["w"].setGeometry(0, corner, edge, max(0, h - corner * 2))
        self.resize_handles["ne"].setGeometry(w - corner, 0, corner, corner)
        self.resize_handles["se"].setGeometry(w - corner, h - corner, corner, corner)
        self.resize_handles["sw"].setGeometry(0, h - corner, corner, corner)
        self.resize_handles["nw"].setGeometry(0, 0, corner, corner)
        for handle in self.resize_handles.values():
            handle.raise_()

    def resize_from_handle(self, direction, start_geometry, delta):
        x = start_geometry.x()
        y = start_geometry.y()
        width = start_geometry.width()
        height = start_geometry.height()
        dx = delta.x()
        dy = delta.y()

        if "e" in direction:
            width += dx
        if "s" in direction:
            height += dy
        if "w" in direction:
            x += dx
            width -= dx
            if width < MIN_WINDOW_WIDTH:
                x -= MIN_WINDOW_WIDTH - width
                width = MIN_WINDOW_WIDTH
        if "n" in direction:
            y += dy
            height -= dy
            if height < MIN_WINDOW_HEIGHT:
                y -= MIN_WINDOW_HEIGHT - height
                height = MIN_WINDOW_HEIGHT

        width = max(MIN_WINDOW_WIDTH, width)
        height = max(MIN_WINDOW_HEIGHT, height)
        self.setGeometry(x, y, width, height)

    def show_panel(self):
        log("show_panel")
        try:
            self.prev_window_handle = win32gui.GetForegroundWindow()
        except Exception:
            self.prev_window_handle = None

        self._reload_tabs()
        self.titlebar.set_mode(self.mode)
        self.stack.setCurrentWidget(self.main_view)
        self._set_allow_activation(False)

        cursor = QCursor.pos()
        geo = self._work_area_for_point(cursor)
        x = min(max(cursor.x(), geo.left() + 10), geo.right() - self.width() - 10)
        y = min(max(cursor.y(), geo.top() + 10), geo.bottom() - self.height() - 10)
        self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()
        QApplication.processEvents()
        self._apply_window_activation_policy()
        self._apply_dwm_window_style()
        if sys.platform == "win32":
            hwnd = self._visible_panel_hwnd()
            win32gui.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        else:
            self.raise_()
        self.show_animation.stop()
        self.show_animation.setStartValue(0.0)
        self.show_animation.setEndValue(0.97)
        self.show_animation.start()
        self.outside_timer.start(80)
        log(f"panel visible={self.isVisible()} hwnd={self._visible_panel_hwnd()}")

    def hide_panel(self):
        self._save_window_size()
        self.outside_timer.stop()
        self.hide()

    def _work_area_for_point(self, point):
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def _check_outside_click(self):
        if not self.isVisible() or self.mode != "single":
            return
        down = bool(win32api.GetAsyncKeyState(0x01) & 0x8000)
        if down and not self._outside_mouse_was_down:
            pos = QCursor.pos()
            if not self.geometry().contains(pos):
                self.hide_panel()
        self._outside_mouse_was_down = down

    def handle_hotkey(self):
        log(f"handle_hotkey visible={self.isVisible()} mode={self.mode}")
        now = time.time()
        interval = int(self.config.get("double_click_interval", 300)) / 1000.0
        if self.isVisible():
            if self.mode == "single" and now - self.last_hotkey_time < interval:
                self.mode = "pinned"
                self.titlebar.set_mode(self.mode)
            else:
                self.hide_panel()
            self.last_hotkey_time = now
            return

        self.mode = "pinned" if now - self.last_hotkey_time < interval else "single"
        self.last_hotkey_time = now
        self.show_panel()

    def _reload_tabs(self):
        groups = self.data.get_groups()
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for group in groups:
            self.tabs.addTab(group["name"])
        if groups:
            self.current_group_index = min(self.current_group_index, len(groups) - 1)
            self.tabs.setCurrentIndex(self.current_group_index)
        self.tabs.blockSignals(False)
        self._render_symbols()

    def _set_current_group(self, index):
        if index >= 0:
            self.current_group_index = index
            self._render_symbols()

    def _render_symbols(self):
        groups = self.data.get_groups()
        if not groups:
            self.symbol_layout.clear()
            self.symbol_layout.addWidget(QLabel("还没有分组"))
            return
        group = groups[self.current_group_index]
        widgets = []
        for item in group.get("items", []):
            button = QPushButton(f" {item['symbol']} ")
            button.setProperty("symbol", True)
            button.setCursor(Qt.PointingHandCursor)
            if self.edit_mode:
                button.setText(f"{item['symbol']}  ×")
                button.clicked.connect(lambda _, s=item["symbol"]: self._delete_symbol(s))
            else:
                button.clicked.connect(lambda _, s=item["symbol"]: self._paste_symbol(s))
            widgets.append(button)
        self.symbol_layout.add_wrapped(widgets, self.scroll.viewport().width())

    def _paste_symbol(self, symbol):
        if self.prev_window_handle:
            self.clipboard.paste_symbol(symbol, self.prev_window_handle)
        else:
            self.clipboard.paste_symbol_direct(symbol)
        if self.mode == "single":
            QTimer.singleShot(80, self.hide_panel)

    def _toggle_add_mode(self):
        if self.add_box.isVisible():
            self._exit_add_mode()
            return
        self._set_allow_activation(True)
        self.add_box.show()
        self.add_text.clear()
        self.activateWindow()
        self.add_text.setFocus()

    def _exit_add_mode(self):
        self.add_box.hide()
        self._set_allow_activation(False)

    def _confirm_add(self):
        groups = self.data.get_groups()
        if not groups:
            return
        text = self.add_text.toPlainText()
        symbols = [line.strip() for line in text.splitlines() if line.strip()]
        if symbols:
            self.data.add_items(groups[self.current_group_index]["name"], symbols)
        self._exit_add_mode()
        self._render_symbols()

    def _show_settings(self):
        self._set_allow_activation(True)
        self.stack.setCurrentWidget(self.settings_view)
        self.edit_check.setChecked(self.edit_mode)
        self.activateWindow()

    def _show_main(self):
        self._set_allow_activation(False)
        self.stack.setCurrentWidget(self.main_view)

    def _update_hotkey(self):
        hotkey = self.hotkey_edit.text().strip()
        if hotkey:
            self.config.set("hotkey", hotkey)
            self.register_hotkey(hotkey)

    def _set_auto_start(self, enabled):
        self.config.set("auto_start", bool(enabled))
        try:
            import win32com.client
            startup_path = os.path.join(
                os.getenv("APPDATA"),
                "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
                "KaomojiPicker.lnk",
            )
            if enabled:
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(startup_path)
                shortcut.Targetpath = sys.executable
                shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
                shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
                shortcut.save()
            elif os.path.exists(startup_path):
                os.remove(startup_path)
        except Exception as exc:
            print(f"Auto-start toggle failed: {exc}")

    def _set_edit_mode(self, enabled):
        self.edit_mode = bool(enabled)
        self.add_group_button.setVisible(self.edit_mode)
        self._render_symbols()

    def _delete_symbol(self, symbol):
        groups = self.data.get_groups()
        if groups:
            self.data.delete_item(groups[self.current_group_index]["name"], symbol)
            self._render_symbols()

    def _add_group(self):
        name, ok = SimpleInputDialog.get_text(self, "新分组", "输入分组名称")
        if ok and name.strip():
            self.data.add_group(name.strip())
            self._reload_tabs()

    def _reorder_groups(self, from_index, to_index):
        groups = self.data.get_groups()
        names = [g["name"] for g in groups]
        moved = names.pop(from_index)
        names.insert(to_index, moved)
        self.data.reorder_groups(names)
        self.current_group_index = to_index

    def _save_window_size(self):
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())

    def closeEvent(self, event):
        self.unregister_hotkey()
        self._save_window_size()
        super().closeEvent(event)


class SimpleInputDialog(QMessageBox):
    @staticmethod
    def get_text(parent, title, label):
        parent._set_allow_activation(True)
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(label)
        edit = QLineEdit(box)
        box.layout().addWidget(edit, 1, 1)
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        result = box.exec()
        parent._set_allow_activation(False)
        return edit.text(), result == QMessageBox.Ok


class KaomojiApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        log("KaomojiApp init")
        self.setApplicationName("颜文字输入器")
        self.setApplicationDisplayName("颜文字输入器")
        self.setQuitOnLastWindowClosed(False)
        self.window = KaomojiWindow()
        self.window.register_hotkey(self.window.config.get("hotkey", "ctrl+`"))
        log("KaomojiApp ready")
        self.tray = self._create_tray()
        self.aboutToQuit.connect(self.window.unregister_hotkey)

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


if __name__ == "__main__":
    app = KaomojiApp(sys.argv)
    sys.exit(app.exec())
