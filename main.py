import ctypes
import os
import sys
import threading
import time
import unicodedata
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process
from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QPainter, QPixmap, QRawFont, QTextCharFormat, QTextLayout
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QMenu,
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


class FlowLayout(QLayout):
    """A real wrapping layout for variable-width symbol buttons."""

    def __init__(self):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.item_list = []
        self.h_spacing = 10
        self.v_spacing = 10

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def clear(self):
        while self.count():
            item = self.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_wrapped(self, widgets, max_width):
        self.clear()
        for widget in widgets:
            self.addWidget(widget)
        self.invalidate()

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        right_padding = 28
        usable_width = max(1, effective.width() - right_padding)
        x = effective.x()
        y = effective.y()
        line_height = 0
        max_right = effective.x() + usable_width - 1

        for item in self.item_list:
            hint = item.sizeHint()
            item_width = min(hint.width(), usable_width)
            item_height = hint.height()
            next_x = x + item_width + self.h_spacing
            if x > effective.x() and next_x - self.h_spacing > max_right + 1:
                x = effective.x()
                y += line_height + self.v_spacing
                next_x = x + item_width + self.h_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_width, item_height)))

            x = next_x
            line_height = max(line_height, item_height)

        return y + line_height - rect.y() + margins.bottom()


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

        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("设置")
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("关闭")
        self.close_button.setObjectName("closeButton")

        for button in (self.settings_button, self.close_button):
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


class SymbolButton(QFrame):
    clicked = Signal()

    def __init__(self, symbol, font_resolver):
        super().__init__()
        self.symbol = symbol
        self.font_resolver = font_resolver
        self.text_ranges = self._text_ranges(symbol, font_resolver)
        self.setObjectName("symbolButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("pressed", False)
        self.setAttribute(Qt.WA_StyledBackground, True)

        width = self._measure_width(symbol, font_resolver) + 38
        self.setMinimumWidth(max(42, width))
        self.setMinimumHeight(44)

    def sizeHint(self):
        return QSize(self.minimumWidth(), self.minimumHeight())

    def minimumSizeHint(self):
        return self.sizeHint()

    def _base_font(self):
        font = QFont("Microsoft YaHei UI", 12)
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

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
        for start, length, family in self.text_ranges:
            fmt = QTextCharFormat()
            font = QFont(family, 12)
            font.setHintingPreference(QFont.PreferNoHinting)
            font.setStyleStrategy(QFont.PreferAntialias)
            fmt.setFont(font)
            fmt.setForeground(QColor("#e4e8f4"))
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

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        layout, line = self._layout_text(max(1, self.width() - 12))
        text_width = line.naturalTextWidth()
        text_height = line.height()
        x = max(0, (self.width() - text_width) / 2)
        y = max(0, (self.height() - text_height) / 2)
        if self.property("pressed"):
            y += 1
        layout.draw(painter, QPointF(x, y))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setProperty("pressed", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.accept()

    def mouseReleaseEvent(self, event):
        was_pressed = self.property("pressed")
        self.setProperty("pressed", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if was_pressed and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
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
        self.add_mode = False
        self.add_target_group = None
        self.outside_timer = QTimer(self)
        self.outside_timer.timeout.connect(self._check_outside_click)
        self._outside_mouse_was_down = False
        self.font_candidates = [
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Segoe UI",
            "Arial",
            "Segoe UI Symbol",
            "Segoe UI Emoji",
            "LXGW WenKai",
            "霞鹜文楷",
            "Gadugi",
            "Cambria Math",
        ]
        self._font_support_cache = {}
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
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(9)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._set_current_group)
        self.tabs.tabMoved.connect(self._reorder_groups)
        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._show_group_context_menu)
        tab_row.addWidget(self.tabs, 1)
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
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.symbol_container = QWidget()
        self.symbol_container.setMinimumHeight(1)
        self.scroll.setWidget(self.symbol_container)
        layout.addWidget(self.scroll, 1)

        self.stack.addWidget(self.main_view)

    def _build_settings_view(self):
        self.settings_view = QWidget()
        layout = QVBoxLayout(self.settings_view)
        layout.setContentsMargins(16, 14, 16, 16)
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
                background: rgba(18, 19, 31, 250);
                border: 1px solid rgba(124, 111, 239, 0.18);
                border-radius: 14px;
            }
            #titlebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.055),
                    stop:1 rgba(255, 255, 255, 0.010));
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid rgba(124, 111, 239, 0.10);
            }
            #modeDot {
                min-width: 7px; max-width: 7px;
                min-height: 7px; max-height: 7px;
                border-radius: 4px;
                background: #7c6fef;
            }
            #modeDot[pinned="true"] { background: #34d399; }
            * { font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif; }
            #modeText, QLabel { color: #cdd6f4; }
            #modeText { color: #a6adc8; font-size: 12px; font-weight: 600; }
            QToolButton, QPushButton {
                background: transparent;
                color: #cdd6f4;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QToolButton:hover, QPushButton:hover {
                background: rgba(255, 255, 255, 0.075);
                border-color: rgba(255, 255, 255, 0.06);
            }
            QToolButton:pressed, QPushButton:pressed {
                background: rgba(124, 111, 239, 0.20);
            }
            QToolButton#closeButton:hover { background: #f04848; color: white; }
            QTabBar::tab {
                color: #a6adc8;
                background: transparent;
                padding: 7px 15px;
                border-radius: 7px;
                margin-right: 4px;
                border: 1px solid transparent;
            }
            QTabBar::tab:hover {
                color: #e4e8f4;
                background: rgba(255, 255, 255, 0.055);
            }
            QTabBar::tab:selected {
                color: #b8b0ff;
                background: rgba(124, 111, 239, 0.18);
                border-color: rgba(124, 111, 239, 0.20);
            }
            QScrollArea, QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 1px 4px 1px;
            }
            QScrollBar::handle:vertical {
                background: rgba(166, 173, 200, 0.22);
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(166, 173, 200, 0.36);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0px;
                background: transparent;
            }
            QScrollBar:horizontal {
                height: 0px;
                background: transparent;
            }
            QScrollBar::handle:horizontal,
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
            }
            QMenu {
                color: #e4e8f4;
                background-color: rgba(24, 25, 40, 252);
                border: 1px solid rgba(124, 111, 239, 0.28);
                border-radius: 9px;
                padding: 6px;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                color: #e4e8f4;
                background: transparent;
                padding: 8px 26px 8px 12px;
                border-radius: 7px;
                min-width: 150px;
            }
            QMenu::item:selected {
                color: #ffffff;
                background: rgba(124, 111, 239, 0.30);
            }
            QMenu::item:disabled {
                color: rgba(166, 173, 200, 0.42);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(166, 173, 200, 0.18);
                margin: 5px 8px;
            }
            #symbolButton {
                background: rgba(34, 36, 64, 225);
                border: 1px solid rgba(255, 255, 255, 0.035);
                border-radius: 9px;
            }
            #symbolButton:hover {
                background: rgba(42, 45, 80, 235);
                border-color: rgba(124, 111, 239, 0.25);
            }
            #symbolButton[pressed="true"] {
                background: rgba(124, 111, 239, 0.24);
            }
            #addBox {
                background: rgba(26, 28, 46, 235);
                border: 1px solid rgba(124, 111, 239, 0.14);
                border-radius: 10px;
            }
            QTextEdit, QLineEdit {
                color: #e4e8f4;
                background: rgba(15, 16, 25, 235);
                border: 1px solid rgba(166, 173, 200, 0.18);
                border-radius: 8px;
                padding: 7px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border-color: rgba(124, 111, 239, 0.65);
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
        inset = 8
        self.resize_handles["n"].setGeometry(corner, inset, max(0, w - corner * 2), edge)
        self.resize_handles["s"].setGeometry(corner, h - inset - edge, max(0, w - corner * 2), edge)
        self.resize_handles["e"].setGeometry(w - inset - edge, corner, edge, max(0, h - corner * 2))
        self.resize_handles["w"].setGeometry(inset, corner, edge, max(0, h - corner * 2))
        self.resize_handles["ne"].setGeometry(w - inset - corner, inset, corner, corner)
        self.resize_handles["se"].setGeometry(w - inset - corner, h - inset - corner, corner, corner)
        self.resize_handles["sw"].setGeometry(inset, h - inset - corner, corner, corner)
        self.resize_handles["nw"].setGeometry(inset, inset, corner, corner)
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

        self._reload_tabs(render=False)
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
        self._render_symbols()
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
        self.show_animation.setEndValue(0.99)
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

    def _reload_tabs(self, render=True):
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
        if render:
            self._render_symbols()

    def _set_current_group(self, index):
        if index >= 0:
            self.current_group_index = index
            self._render_symbols()

    def _show_symbol_context_menu(self, button, symbol, pos):
        groups = self.data.get_groups()
        current_group = groups[self.current_group_index]["name"] if groups else None
        menu = QMenu(self)
        menu.setSeparatorsCollapsible(False)
        move_menu = menu.addMenu("移动到分组")
        move_actions = {}
        for group in groups:
            group_name = group["name"]
            if group_name == current_group:
                continue
            action = move_menu.addAction(group_name)
            move_actions[action] = group_name
        if not move_actions:
            empty_action = move_menu.addAction("没有其他分组")
            empty_action.setEnabled(False)
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        action = menu.exec(button.mapToGlobal(pos))
        if action in move_actions:
            self._move_symbol(symbol, move_actions[action])
        elif action == delete_action:
            self._delete_symbol(symbol)

    def _show_group_context_menu(self, pos):
        index = self.tabs.tabAt(pos)
        groups = self.data.get_groups()
        if index < 0 or index >= len(groups):
            menu = QMenu(self)
            menu.setSeparatorsCollapsible(False)
            add_group_action = menu.addAction("添加新分组")
            if menu.exec(self.tabs.mapToGlobal(pos)) == add_group_action:
                self._add_group()
            return
        self.current_group_index = index
        self.tabs.setCurrentIndex(index)
        group_name = groups[index]["name"]

        menu = QMenu(self)
        menu.setSeparatorsCollapsible(False)
        add_items_action = menu.addAction("往这个分组添加表情")
        rename_group_action = menu.addAction("重命名")
        delete_group_action = menu.addAction("删除这个分组")
        menu.addSeparator()
        add_group_action = menu.addAction("添加新分组")
        action = menu.exec(self.tabs.mapToGlobal(pos))

        if action == add_items_action:
            self._enter_add_mode(group_name)
        elif action == rename_group_action:
            self._rename_group(group_name)
        elif action == delete_group_action:
            self._confirm_delete_group(group_name)
        elif action == add_group_action:
            self._add_group()

    def _render_symbols(self):
        groups = self.data.get_groups()
        for child in self.symbol_container.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            child.hide()
            child.setParent(None)
            child.deleteLater()

        viewport_width = max(0, self.scroll.viewport().width())
        self.symbol_container.setFixedWidth(viewport_width)
        available_width = max(120, viewport_width - 2)
        gap = 10
        row_gap = 10
        x = 0
        y = 0
        row_height = 0

        if not groups:
            label = QLabel("还没有分组", self.symbol_container)
            label.setGeometry(0, 0, available_width, 32)
            self.symbol_container.setMinimumHeight(40)
            return

        group = groups[self.current_group_index]
        for item in group.get("items", []):
            symbol = item["symbol"]
            button = SymbolButton(symbol, self._font_for_char)
            button.setParent(self.symbol_container)
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, b=button, s=symbol: self._show_symbol_context_menu(b, s, pos)
            )
            button.clicked.connect(lambda s=symbol: self._paste_symbol(s))

            hint = button.sizeHint()
            width = min(hint.width(), available_width)
            height = hint.height()
            if x > 0 and x + width > available_width:
                x = 0
                y += row_height + row_gap
                row_height = 0
            button.setGeometry(x, y, width, height)
            button.show()
            x += width + gap
            row_height = max(row_height, height)

        content_height = y + row_height
        self.symbol_container.setMinimumHeight(max(1, content_height))
        self.symbol_container.resize(viewport_width, max(1, content_height))

    def _font_for_char(self, ch):
        cp = ord(ch)
        if cp in self._font_support_cache:
            return self._font_support_cache[cp]
        preferred = self._preferred_font_for_codepoint(cp)
        if preferred:
            self._font_support_cache[cp] = preferred
            return preferred
        for family in self.font_candidates:
            raw = QRawFont.fromFont(QFont(family, 12))
            if raw.isValid() and raw.supportsCharacter(cp):
                self._font_support_cache[cp] = family
                return family
        self._font_support_cache[cp] = "Microsoft YaHei UI"
        return "Microsoft YaHei UI"

    def _preferred_font_for_codepoint(self, cp):
        # Some Windows fonts report broad fallback coverage through Qt, but still
        # render tofu for uncommon kaomoji blocks. Prefer known-good fonts first.
        if 0x1400 <= cp <= 0x167F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Gadugi", "Segoe UI"], cp)
        if 0xA4D0 <= cp <= 0xA4FF:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "LXGW WenKai", "霞鹜文楷", "Segoe UI"], cp)
        if 0x1D00 <= cp <= 0x1D7F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"], cp)
        if 0x2070 <= cp <= 0x209F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Cambria Math", "Segoe UI"], cp)
        if 0x0600 <= cp <= 0x06FF or 0xFE70 <= cp <= 0xFEFF:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Microsoft Uighur", "Arial"], cp)
        if 0x2600 <= cp <= 0x27BF or 0x1F000 <= cp <= 0x1FAFF:
            return self._first_available_font(["Segoe UI Emoji", "Segoe UI Symbol"], cp)
        return None

    def _first_available_font(self, families, cp):
        for family in families:
            raw = QRawFont.fromFont(QFont(family, 12))
            if raw.isValid() and raw.supportsCharacter(cp):
                return family
        return None

    def _paste_symbol(self, symbol):
        if self.mode == "single":
            self.hide_panel()
        if self.prev_window_handle:
            self.clipboard.paste_symbol(symbol, self.prev_window_handle)
        else:
            self.clipboard.paste_symbol_direct(symbol)

    def _enter_add_mode(self, group_name):
        self.add_target_group = group_name
        self._set_allow_activation(True)
        self.add_hint.setText(f"添加到「{group_name}」：每行输入一个表情")
        self.add_box.show()
        self.add_text.clear()
        self.activateWindow()
        self.add_text.setFocus()

    def _exit_add_mode(self):
        self.add_box.hide()
        self.add_target_group = None
        self._set_allow_activation(False)

    def _confirm_add(self):
        if not self.add_target_group:
            return
        text = self.add_text.toPlainText()
        symbols = [line.strip() for line in text.splitlines() if line.strip()]
        if symbols:
            self.data.add_items(self.add_target_group, symbols)
        self._exit_add_mode()
        self._reload_tabs()
        self._render_symbols()

    def _show_settings(self):
        self._set_allow_activation(True)
        self.stack.setCurrentWidget(self.settings_view)
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

    def _delete_symbol(self, symbol):
        groups = self.data.get_groups()
        if groups:
            self.data.delete_item(groups[self.current_group_index]["name"], symbol)
            self._render_symbols()

    def _move_symbol(self, symbol, target_group_name):
        groups = self.data.get_groups()
        if not groups:
            return
        source_group_name = groups[self.current_group_index]["name"]
        if self.data.move_item(source_group_name, target_group_name, symbol):
            self._render_symbols()

    def _confirm_delete_group(self, group_name):
        ok = ConfirmDialog.ask(
            self,
            "删除分组",
            f"确定删除分组「{group_name}」？\n组内表情会一并删除。",
            confirm_text="删除",
            cancel_text="取消",
        )
        if not ok:
            return
        self.data.delete_group(group_name)
        self.current_group_index = 0
        self._reload_tabs()

    def _add_group(self):
        name, ok = SimpleInputDialog.get_text(self, "新分组", "输入分组名称")
        if ok and name.strip():
            self.data.add_group(name.strip())
            self._reload_tabs()

    def _rename_group(self, group_name):
        name, ok = SimpleInputDialog.get_text(self, "重命名分组", "输入新的分组名称", group_name)
        new_name = name.strip()
        if ok and new_name and new_name != group_name:
            self.data.rename_group(group_name, new_name)
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


class BaseDarkDialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setObjectName("darkDialog")
        self.setStyleSheet(
            """
            QDialog#darkDialog {
                background: rgba(12, 13, 22, 252);
                border: 1px solid rgba(124, 111, 239, 0.34);
                border-radius: 12px;
            }
            QLabel {
                color: #e4e8f4;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 14px;
            }
            QLabel#dialogTitle {
                color: #cdd6f4;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit {
                color: #edf1ff;
                background: rgba(18, 19, 31, 245);
                border: 1px solid rgba(124, 111, 239, 0.64);
                border-radius: 9px;
                padding: 8px;
                selection-background-color: rgba(124, 111, 239, 0.55);
                font-size: 14px;
            }
            QPushButton {
                min-width: 70px;
                min-height: 30px;
                color: #e4e8f4;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.075);
                border-color: rgba(255, 255, 255, 0.08);
            }
            QPushButton#primaryButton {
                background: rgba(124, 111, 239, 0.24);
                border-color: rgba(124, 111, 239, 0.44);
            }
            QPushButton#dangerButton {
                background: rgba(240, 72, 72, 0.18);
                border-color: rgba(240, 72, 72, 0.42);
            }
            """
        )

    def exec_with_activation(self):
        self.parent_window._set_allow_activation(True)
        try:
            self.parent_window.activateWindow()
            return self.exec()
        finally:
            self.parent_window._set_allow_activation(False)


class SimpleInputDialog(BaseDarkDialog):
    def __init__(self, parent, title, label, initial_text=""):
        super().__init__(parent, title)
        self.setFixedWidth(270)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        message = QLabel(label)
        layout.addWidget(message)

        self.edit = QLineEdit()
        self.edit.setText(initial_text)
        self.edit.selectAll()
        layout.addWidget(self.edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_button = QPushButton("确定")
        ok_button.setObjectName("primaryButton")
        cancel_button = QPushButton("取消")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    @staticmethod
    def get_text(parent, title, label, initial_text=""):
        dialog = SimpleInputDialog(parent, title, label, initial_text)
        result = dialog.exec_with_activation()
        return dialog.edit.text(), result == QDialog.Accepted


class ConfirmDialog(BaseDarkDialog):
    def __init__(self, parent, title, message, confirm_text="确定", cancel_text="取消"):
        super().__init__(parent, title)
        self.setFixedWidth(330)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName("dangerButton")
        cancel_button = QPushButton(cancel_text)
        confirm_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    @staticmethod
    def ask(parent, title, message, confirm_text="确定", cancel_text="取消"):
        dialog = ConfirmDialog(parent, title, message, confirm_text, cancel_text)
        return dialog.exec_with_activation() == QDialog.Accepted


class KaomojiApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        log("KaomojiApp init")
        self.setApplicationName("颜文字输入器")
        self.setApplicationDisplayName("颜文字输入器")
        self.setFont(QFont("Microsoft YaHei UI", 9))
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
