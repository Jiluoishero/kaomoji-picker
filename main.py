import ctypes
import json
import os
import sys
import threading
import time
import unicodedata
import winreg
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process
from PySide6.QtCore import QEasingCurve, QEvent, QMimeData, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QColor, QCursor, QDrag, QFont, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRawFont, QTextCharFormat, QTextLayout
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
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEACTIVATE = 0x0021
MA_NOACTIVATE = 3
PM_REMOVE = 0x0001
WH_KEYBOARD_LL = 13
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
DWMWCP_DONOTROUND = 1
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "KaomojiPicker"
VK_TOP_ROW_DIGITS = tuple(range(0x31, 0x3A))
VK_MODIFIERS = (
    win32con.VK_CONTROL,
    win32con.VK_LCONTROL,
    win32con.VK_RCONTROL,
    win32con.VK_MENU,
    win32con.VK_LMENU,
    win32con.VK_RMENU,
    win32con.VK_SHIFT,
    win32con.VK_LSHIFT,
    win32con.VK_RSHIFT,
    win32con.VK_LWIN,
    win32con.VK_RWIN,
)


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", wintypes.POINT),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class HotkeyBridge(QObject):
    pressed = Signal()


class HotkeyEdit(QLineEdit):
    hotkeyChanged = Signal(str)

    def __init__(self, hotkey):
        super().__init__(hotkey)
        self.setReadOnly(True)
        self.setPlaceholderText("按下快捷键")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setTextMargins(8, 0, 8, 0)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_unknown):
            return
        if key in (Qt.Key_Backspace, Qt.Key_Delete):
            self.clear()
            event.accept()
            return

        hotkey = self._event_to_hotkey(event)
        if hotkey:
            self.setText(hotkey)
            self.hotkeyChanged.emit(hotkey)
        event.accept()

    def mousePressEvent(self, event):
        self.selectAll()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        theme = window_theme(self)
        focused = self.hasFocus()
        if theme == "dark":
            background = QColor(16, 18, 34, 245) if focused else QColor(12, 14, 28, 235)
            border = QColor("#d9b368") if focused else QColor(217, 179, 104, 64)
        else:
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 248, 242, 245)
            border = QColor("#a66236") if focused else QColor(103, 96, 78, 51)
        draw_rounded_fill_box(painter, self.rect(), 10.0, background, border, 1.0)
        painter.end()
        super().paintEvent(event)

    def _event_to_hotkey(self, event):
        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.MetaModifier:
            parts.append("win")

        key_text = self._key_name(event.key())
        if not key_text:
            sequence = QKeySequence(event.key())
            key_text = sequence.toString(QKeySequence.PortableText).lower()
        if not key_text:
            return None
        parts.append(key_text)
        return "+".join(parts)

    def _key_name(self, key):
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(ord("a") + key - Qt.Key_A)
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(ord("0") + key - Qt.Key_0)
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            return f"f{key - Qt.Key_F1 + 1}"
        special = {
            Qt.Key_QuoteLeft: "`",
            Qt.Key_Space: "space",
            Qt.Key_Tab: "tab",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc",
        }
        return special.get(key)


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


class PinIcon(QWidget):
    """A tiny monochrome pushpin icon drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._color = QColor("#8b5730")

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


class ThemeToggleButton(QToolButton):
    """Draws a monochrome crescent moon (light) or sun (dark) icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = False
        self._color = QColor("#8b5730")
        self.setText("")

    def set_theme(self, theme):
        self._is_dark = (theme == "dark")
        self._color = QColor("#e4e0d0" if self._is_dark else "#8b5730")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2

        if self._is_dark:
            # Sun: central disc + 8 rays
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
            p.drawEllipse(QPointF(cx, cy), 4.5, 4.5)
            pen = QPen(self._color, 1.8)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            for i in range(8):
                angle = i * math.pi / 4
                r1, r2 = 7, 10
                p.drawLine(
                    QPointF(cx + r1 * math.cos(angle), cy + r1 * math.sin(angle)),
                    QPointF(cx + r2 * math.cos(angle), cy + r2 * math.sin(angle)),
                )
        else:
            # Crescent moon via path subtraction
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
            full = QPainterPath()
            full.addEllipse(QRectF(cx - 7, cy - 7, 14, 14))
            cut = QPainterPath()
            cut.addEllipse(QRectF(cx - 2, cy - 9, 14, 14))
            p.drawPath(full.subtracted(cut))

        p.end()


class SettingsButton(QToolButton):
    """Draws a monochrome minimal gear icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#8b5730")
        self.setText("")

    def set_color(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)

        cx, cy = self.width() / 2, self.height() / 2
        teeth = 8
        outer_r = 10.5
        inner_r = 7.8
        hole_r = 3.8

        # Gear outline via alternating radii polygon
        path = QPainterPath()
        n = teeth * 4
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            r = outer_r if (i % 4 < 2) else inner_r
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()

        # Center hole
        hole = QPainterPath()
        hole.addEllipse(QPointF(cx, cy), hole_r, hole_r)
        p.drawPath(path.subtracted(hole))
        p.end()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_start = None
        self.window_start = None
        self.setObjectName("titlebar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
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

        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setFont(QFont("Microsoft YaHei UI", 15))
        self.close_button.setToolTip("关闭")
        self.close_button.setObjectName("closeButton")

        for button in (self.theme_button, self.settings_button, self.close_button):
            button.setFixedSize(32, 32)
            layout.addWidget(button)

        self._apply_icon_colors(theme)

    def _apply_icon_colors(self, theme):
        c = "#e4e0d0" if theme == "dark" else "#8b5730"
        self.pin_icon.set_color(c)
        self.settings_button.set_color(c)
        self.theme_button.set_theme(theme)

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


def draw_rounded_fill_box(painter, rect, radius, background, border, border_width=1.0):
    outer_rect = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    inner_rect = outer_rect.adjusted(border_width, border_width, -border_width, -border_width)

    outer_path = QPainterPath()
    outer_path.addRoundedRect(outer_rect, radius, radius)
    painter.fillPath(outer_path, border)

    inner_path = QPainterPath()
    inner_radius = max(0.0, radius - border_width)
    inner_path.addRoundedRect(inner_rect, inner_radius, inner_radius)
    painter.fillPath(inner_path, background)


def window_theme(widget):
    current = widget
    while current is not None:
        config = getattr(current, "config", None)
        if config is not None:
            return config.get("theme", "light")
        current = current.parentWidget()
    return "light"


def in_dark_dialog(widget):
    current = widget
    while current is not None:
        if current.objectName() == "darkDialog":
            return True
        current = current.parentWidget()
    return False


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
            return QColor(232, 228, 216, 250), QColor(103, 96, 78, 38), 30.0, 1.0
        if self.role == "sortBar":
            if theme == "dark":
                return QColor(22, 24, 46, 235), QColor(217, 179, 104, 64), 12.0, 1.0
            return QColor(240, 236, 224, 235), QColor(103, 96, 78, 38), 12.0, 1.0
        if self.role == "addBox":
            if theme == "dark":
                return QColor(22, 24, 46, 235), QColor(217, 179, 104, 51), 12.0, 1.0
            return QColor(240, 236, 224, 235), QColor(103, 96, 78, 31), 12.0, 1.0
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
            title_gradient.setColorAt(0, QColor(255, 255, 255, 102))
            title_gradient.setColorAt(1, QColor(255, 255, 255, 26))
            divider = QColor(103, 96, 78, 20)
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
                bg = QColor(166, 98, 54, 56 if hovered else 31)
                border = QColor(166, 98, 54, 140 if hovered else 89)
            if pressed:
                bg = bg.darker(110)
            return bg, border, 9.0, 1.0
        if hovered or pressed:
            if theme == "dark":
                bg = QColor(217, 179, 104, 64 if pressed else 31)
                border = QColor(217, 179, 104, 51)
            else:
                bg = QColor(166, 98, 54, 38 if pressed else 20)
                border = QColor(103, 96, 78, 31)
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
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 248, 242, 245)
            border = QColor("#a66236") if focused else QColor(103, 96, 78, 51)
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
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 248, 242, 245)
            border = QColor("#a66236") if focused else QColor(103, 96, 78, 51)
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
            background = QColor("#a66236") if checked else (QColor(255, 255, 255, 255) if hovered else QColor(250, 248, 242, 245))
            border = QColor("#a66236") if checked or hovered else QColor(103, 96, 78, 64)
            knob = QColor(255, 255, 255, 245) if checked else QColor(103, 96, 78, 150)

        draw_rounded_fill_box(painter, QRectF(2, 1, 42, 24), 12.0, background, border, 1.0)
        knob_x = 24 if checked else 6
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(knob_x, 5, 16, 16))


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
        indicator_color = QColor("#d9b368") if theme == "dark" else QColor("#a66236")
        feedback_brush = QColor(217, 179, 104, 30) if theme == "dark" else QColor(166, 98, 54, 30)

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
            text_color = QColor("#8a552e") if is_pressed else (QColor("#a66236") if is_hovered else QColor("#67604e"))
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
                background = QColor(166, 98, 54, 31)
                border = QColor("#a66236")
                border_width = 2.0
            elif is_hovered:
                background = QColor(255, 255, 255, 255)
                border = QColor(166, 98, 54, 102)
                border_width = 2.0
            else:
                background = QColor(250, 248, 242, 230)
                border = QColor(103, 96, 78, 15)
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


class KaomojiWindow(QWidget):
    digit_shortcut_pressed = Signal(int)

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
        self.content_scale = float(self.config.get("content_scale", 1.0))
        self.content_scale = min(1.5, max(0.75, self.content_scale))
        self._keyboard_hook = None
        self._keyboard_hook_proc = None
        self._captured_digit_keys = set()
        self.digit_shortcut_pressed.connect(self._switch_group_by_number)
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
            "闇為箿鏂囨シ",
            "Gadugi",
            "Cambria Math",
        ]
        self._font_support_cache = {}
        self.show_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.show_animation.setDuration(120)
        self.show_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.resize_animation = QPropertyAnimation(self, b"geometry", self)
        self.resize_animation.setDuration(180)
        self.resize_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.resize_animation.finished.connect(self._on_resize_animation_finished)
        self.base_window_size = QSize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self._auto_resize_active = False
        self._manual_resize_active = False
        self._resize_render_pending = False
        self._suppress_resize_render = False
        self._layout_generation = 0
        self._last_render_width = -1

        flags = (
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self._resize_from_config()
        self._build_ui()
        self._apply_styles()
        self._apply_window_activation_policy()
        self._apply_dwm_window_style()
        QApplication.instance().installEventFilter(self)
        self._install_keyboard_hook()

    def _scaled(self, value):
        return max(1, int(round(value * self.content_scale)))

    def _scale_qss(self, qss):
        for size in (11, 12, 13, 14, 15, 16, 18):
            qss = qss.replace(f"font-size: {size}px;", f"font-size: {self._scaled(size)}px;")
        return qss

    def _install_keyboard_hook(self):
        if sys.platform != "win32" or self._keyboard_hook:
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LowLevelKeyboardProc, ctypes.c_void_p, wintypes.DWORD]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

        def keyboard_proc(n_code, w_param, l_param):
            if n_code == 0 and w_param in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if data.vkCode in VK_TOP_ROW_DIGITS:
                    if w_param in (WM_KEYUP, WM_SYSKEYUP):
                        if data.vkCode in self._captured_digit_keys:
                            self._captured_digit_keys.discard(data.vkCode)
                            return 1
                    elif self._should_capture_digit_shortcut():
                        if data.vkCode not in self._captured_digit_keys:
                            self._captured_digit_keys.add(data.vkCode)
                            self.digit_shortcut_pressed.emit(data.vkCode - 0x30)
                        return 1
            return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

        self._keyboard_hook_proc = LowLevelKeyboardProc(keyboard_proc)
        module = kernel32.GetModuleHandleW(None)
        self._keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._keyboard_hook_proc,
            module,
            0,
        )
        if not self._keyboard_hook:
            self._keyboard_hook_proc = None
            log(f"Failed to install digit keyboard hook error={ctypes.get_last_error()}")

    def _uninstall_keyboard_hook(self):
        if sys.platform != "win32" or not self._keyboard_hook:
            return
        try:
            ctypes.windll.user32.UnhookWindowsHookEx(self._keyboard_hook)
        except Exception as exc:
            log(f"Failed to uninstall digit keyboard hook: {exc}")
        self._keyboard_hook = None
        self._keyboard_hook_proc = None
        self._captured_digit_keys.clear()

    def _should_capture_digit_shortcut(self):
        if self.allow_activation or self.stack.currentWidget() != self.main_view:
            return False
        if not self.isVisible() or not self.geometry().contains(QCursor.pos()):
            return False
        return not any(win32api.GetAsyncKeyState(vk) & 0x8000 for vk in VK_MODIFIERS)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and self.isVisible() and self.geometry().contains(QCursor.pos()):
            self._handle_window_wheel(event)
            return True
        return super().eventFilter(obj, event)

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
            # Keep DWM from adding a second rounding layer.
            corner = ctypes.c_int(DWMWCP_DONOTROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner),
                ctypes.sizeof(corner),
            )
        except Exception as exc:
            log(f"DWM style failed: {exc}")

    def _set_allow_activation(self, enabled):
        self.allow_activation = bool(enabled)
        self._apply_window_activation_policy()


    def register_hotkey(self, hotkey):
        if sys.platform != "win32":
            return False
        self.unregister_hotkey()
        try:
            modifiers, key = parse_hotkey(hotkey)
        except ValueError as exc:
            log(str(exc))
            return False
        hwnd = self._hwnd()
        if ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID, modifiers, key):
            log(f"Registered window hotkey '{hotkey}' hwnd={hwnd} modifiers={modifiers} key={key}")
            return True
        else:
            log(f"Failed to register window hotkey '{hotkey}' error={ctypes.get_last_error()} hwnd={hwnd}")
            return False

    def unregister_hotkey(self):
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.user32.UnregisterHotKey(self._hwnd(), HOTKEY_ID)
        except Exception:
            pass

    def toggle_theme(self):
        current = self.config.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self.config.set("theme", new_theme)
        self._apply_styles()
        self._apply_dwm_window_style()
        if hasattr(self, "titlebar"):
            self.titlebar._apply_icon_colors(new_theme)
        if hasattr(self, "tabs"):
            self.tabs.update()
        self._render_symbols()

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
        self.base_window_size = QSize(width, height)
        if width != self.config.get("window_width") or height != self.config.get("window_height"):
            self.config.set("window_width", width)
            self.config.set("window_height", height)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.panel = RoundedFrame("panel", self)
        self.panel.setObjectName("panel")
        self.panel.setAutoFillBackground(False)
        root.addWidget(self.panel)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.titlebar = TitleBar(self)
        panel_layout.addWidget(self.titlebar)
        self.titlebar.theme_button.clicked.connect(self.toggle_theme)
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
        self.tabs = SortableTabBar(self)
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._set_current_group)
        self.tabs.tabMoved.connect(self._reorder_groups)
        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._show_group_context_menu)
        tab_row.addWidget(self.tabs, 1)
        layout.addLayout(tab_row)

        self.add_box = RoundedFrame("addBox", self)
        self.add_box.setObjectName("addBox")
        add_layout = QVBoxLayout(self.add_box)
        add_layout.setContentsMargins(10, 10, 10, 10)
        self.add_hint = QLabel("每行输入一个符号")
        self.add_text = RoundedTextEdit()
        self.add_text.setFixedHeight(76)
        add_buttons = QHBoxLayout()
        add_buttons.addStretch(1)
        cancel = RoundedButton("取消")
        confirm = RoundedButton("确认添加")
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
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.symbol_container = SymbolContainer(self)
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
        back = RoundedButton("‹")
        back.setFixedSize(30, 30)
        back.clicked.connect(self._show_main)
        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        header.addWidget(back)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        hotkey_row = self._setting_row("快捷键", "全局唤起面板")
        self.hotkey_edit = HotkeyEdit(self.config.get("hotkey", "ctrl+q"))
        self.hotkey_edit.setFixedWidth(150)
        self.hotkey_edit.hotkeyChanged.connect(self._update_hotkey)
        hotkey_row.addWidget(self.hotkey_edit)
        layout.addLayout(hotkey_row)

        auto_row = self._setting_row("开机自启", "登录 Windows 后自动运行")
        self.autostart_check = RoundedSwitch()
        self.autostart_check.setChecked(self._is_auto_start_enabled())
        self.autostart_check.toggled.connect(self._set_auto_start)
        self.autostart_state = QLabel()
        self.autostart_state.setObjectName("settingDesc")
        self._sync_autostart_state_label(self.autostart_check.isChecked())
        self.autostart_check.toggled.connect(self._sync_autostart_state_label)
        auto_row.addWidget(self.autostart_state)
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
        theme = self.config.get("theme", "light")
        if theme == "dark":
            qss = """
            #panel {
                background: transparent;
                border: none;
            }
            #titlebar {
                background: transparent;
                border: none;
            }
            #pinIcon { color: #e4e0d0; font-size: 14px; }
            * { font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif; }
            QLabel { color: #fff5d6; }
            QToolButton {
                background: transparent;
                color: #fff5d6;
                border: 1px solid transparent;
                border-radius: 9px;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton {
                background: transparent;
                color: #fff5d6;
                border: none;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QToolButton:hover {
                background: rgba(217, 179, 104, 0.12);
                border-color: transparent;
                color: #d9b368;
            }
            QPushButton:hover {
                background: transparent;
                border: none;
                color: #d9b368;
            }
            QToolButton:pressed {
                background: rgba(217, 179, 104, 0.25);
            }
            QPushButton:pressed {
                background: transparent;
                border: none;
            }
            #titlebar QToolButton {
                padding: 0px;
                font-family: "Segoe UI Symbol", "Microsoft YaHei UI", sans-serif;
                font-size: 15px;
            }
            QToolButton#titleIconButton {
                font-size: 16px;
            }
            QToolButton#closeButton {
                padding: 0px;
                font-size: 18px;
            }
            QToolButton#closeButton:hover { background: #f04848; color: white; border-color: transparent; }
            QTabBar::tab {
                color: #a6adc8;
                background: transparent;
                padding: 8px 16px 12px 16px;
                border-radius: 9px;
                margin-right: 4px;
                border: 1px solid transparent;
                font-size: 14px;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                color: #ffdda1;
                background: rgba(217, 179, 104, 0.08);
            }
            QTabBar::tab:selected {
                color: #d9b368;
                background: transparent;
            }
            QScrollArea, QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 1px 4px 1px;
            }
            QScrollBar::handle:vertical {
                background: rgba(217, 179, 104, 0.22);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(217, 179, 104, 0.45);
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
                color: #fff5d6;
                background-color: rgba(20, 22, 44, 252);
                border: 1px solid rgba(217, 179, 104, 0.35);
                border-radius: 12px;
                padding: 6px;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
                font-weight: 600;
            }
            QMenu::item {
                color: #fff5d6;
                background: transparent;
                padding: 8px 26px 8px 12px;
                border-radius: 8px;
                min-width: 150px;
            }
            QMenu::item:selected {
                color: #d9b368;
                background: rgba(217, 179, 104, 0.15);
            }
            QMenu::item:disabled {
                color: rgba(166, 173, 200, 0.42);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(217, 179, 104, 0.15);
                margin: 5px 8px;
            }
            #symbolButton {
                background: transparent;
                border: none;
            }
            #symbolButton:hover {
                background: transparent;
                border: none;
            }
            #symbolButton[pressed="true"] {
                background: transparent;
                border: none;
            }
            #sortBar {
                background: transparent;
                border: none;
            }
            QPushButton#primaryButton {
                background: transparent;
                border: none;
                color: #d9b368;
            }
            QPushButton#primaryButton:hover {
                background: transparent;
                border: none;
            }
            #addBox {
                background: transparent;
                border: none;
            }
            QTextEdit, QLineEdit {
                color: #fff5d6;
                background: transparent;
                border: none;
                padding: 0px;
                font-size: 13px;
            }
            QTextEdit:focus, QLineEdit:focus {
                background: transparent;
                border: none;
            }
            QCheckBox {
                min-width: 46px;
                min-height: 26px;
                spacing: 0px;
            }
            QCheckBox::indicator {
                width: 0px;
                height: 0px;
            }
            QCheckBox::indicator:hover {
                background: transparent;
                border: none;
            }
            QCheckBox::indicator:checked {
                background: transparent;
                border: none;
            }
            #settingsTitle { font-size: 16px; font-weight: 600; color: #d9b368; }
            #settingLabel { font-size: 14px; font-weight: 600; color: #fff5d6; }
            #settingDesc { font-size: 12px; color: #a6adc8; }
            """
        else:
            qss = """
            #panel {
                background: transparent;
                border: none;
            }
            #titlebar {
                background: transparent;
                border: none;
            }
            #pinIcon { color: #8b5730; font-size: 14px; }
            * { font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif; }
            QLabel { color: #67604e; }
            QToolButton {
                background: transparent;
                color: #67604e;
                border: 1px solid transparent;
                border-radius: 9px;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton {
                background: transparent;
                color: #67604e;
                border: none;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QToolButton:hover {
                background: rgba(103, 96, 78, 0.08);
                border-color: transparent;
                color: #a66236;
            }
            QPushButton:hover {
                background: transparent;
                border: none;
                color: #a66236;
            }
            QToolButton:pressed {
                background: rgba(166, 98, 54, 0.15);
            }
            QPushButton:pressed {
                background: transparent;
                border: none;
            }
            #titlebar QToolButton {
                padding: 0px;
                font-family: "Segoe UI Symbol", "Microsoft YaHei UI", sans-serif;
                font-size: 15px;
            }
            QToolButton#titleIconButton {
                font-size: 16px;
            }
            QToolButton#closeButton {
                padding: 0px;
                font-size: 18px;
            }
            QToolButton#closeButton:hover { background: #f04848; color: white; border-color: transparent; }
            QTabBar::tab {
                color: #9e9785;
                background: transparent;
                padding: 8px 16px 12px 16px;
                border-radius: 9px;
                margin-right: 4px;
                border: 1px solid transparent;
                font-size: 14px;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                color: #a66236;
                background: rgba(103, 96, 78, 0.05);
            }
            QTabBar::tab:selected {
                color: #8a552e;
                background: transparent;
            }
            QScrollArea, QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 1px 4px 1px;
            }
            QScrollBar::handle:vertical {
                background: rgba(103, 96, 78, 0.18);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(103, 96, 78, 0.35);
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
                color: #67604e;
                background-color: rgba(242, 239, 230, 252);
                border: 1px solid rgba(103, 96, 78, 0.2);
                border-radius: 12px;
                padding: 6px;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
                font-weight: 600;
            }
            QMenu::item {
                color: #67604e;
                background: transparent;
                padding: 8px 26px 8px 12px;
                border-radius: 8px;
                min-width: 150px;
            }
            QMenu::item:selected {
                color: #a66236;
                background: rgba(166, 98, 54, 0.1);
            }
            QMenu::item:disabled {
                color: rgba(103, 96, 78, 0.35);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(103, 96, 78, 0.12);
                margin: 5px 8px;
            }
            #symbolButton {
                background: transparent;
                border: none;
            }
            #symbolButton:hover {
                background: transparent;
                border: none;
            }
            #symbolButton[pressed="true"] {
                background: transparent;
                border: none;
            }
            #sortBar {
                background: transparent;
                border: none;
            }
            QPushButton#primaryButton {
                background: transparent;
                border: none;
                color: #a66236;
            }
            QPushButton#primaryButton:hover {
                background: transparent;
                border: none;
            }
            #addBox {
                background: transparent;
                border: none;
            }
            QTextEdit, QLineEdit {
                color: #67604e;
                background: transparent;
                border: none;
                padding: 0px;
                font-size: 13px;
            }
            QTextEdit:focus, QLineEdit:focus {
                background: transparent;
                border: none;
            }
            QCheckBox {
                min-width: 46px;
                min-height: 26px;
                spacing: 0px;
            }
            QCheckBox::indicator {
                width: 0px;
                height: 0px;
            }
            QCheckBox::indicator:hover {
                background: transparent;
                border: none;
            }
            QCheckBox::indicator:checked {
                background: transparent;
                border: none;
            }
            #settingsTitle { font-size: 16px; font-weight: 600; color: #a66236; }
            #settingLabel { font-size: 14px; font-weight: 600; color: #67604e; }
            #settingDesc { font-size: 12px; color: #8f8773; }
            """
        self.setStyleSheet(self._scale_qss(qss))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_handles()
        if self._manual_resize_active or self._suppress_resize_render:
            return
        width_changed = self.scroll.viewport().width() != self._last_render_width if hasattr(self, "scroll") else False
        if not self._auto_resize_active or width_changed:
            self._schedule_render_symbols()

    def _schedule_render_symbols(self):
        if self._resize_render_pending:
            return
        self._resize_render_pending = True
        generation = self._layout_generation
        QTimer.singleShot(0, lambda generation=generation: self._render_symbols(generation))

    def _on_resize_animation_finished(self):
        self._auto_resize_active = False
        self._schedule_render_symbols()

    def _cancel_auto_resize_work(self):
        self._layout_generation += 1
        self._resize_render_pending = False
        self._auto_resize_active = False
        self.resize_animation.stop()

    def _restore_base_size(self):
        if self.size() == self.base_window_size:
            return
        self._suppress_resize_render = True
        try:
            self.resize(self.base_window_size)
        finally:
            self._suppress_resize_render = False

    def _begin_manual_resize(self):
        self._manual_resize_active = True
        self._auto_resize_active = False
        self._resize_render_pending = False
        self.resize_animation.stop()

    def _finish_manual_resize(self):
        self._manual_resize_active = False
        self._auto_resize_active = False
        self.base_window_size = self.size()
        self._save_window_size()
        self._schedule_render_symbols()

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

        self._cancel_auto_resize_work()
        self._restore_base_size()
        self._reload_tabs(render=False)
        self.titlebar.set_mode(self.mode)
        self.stack.setCurrentWidget(self.main_view)
        self._set_allow_activation(False)

        cursor = QCursor.pos()
        geo = self._work_area_for_point(cursor)
        base_width = self.base_window_size.width()
        base_height = self.base_window_size.height()
        x = min(max(cursor.x(), geo.left() + 10), geo.right() - base_width - 10)
        y = min(max(cursor.y(), geo.top() + 10), geo.bottom() - base_height - 10)
        self._suppress_resize_render = True
        try:
            self.setGeometry(x, y, base_width, base_height)
        finally:
            self._suppress_resize_render = False
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

    def _set_content_scale(self, scale):
        scale = round(min(1.5, max(0.75, scale)), 2)
        if abs(scale - self.content_scale) < 0.001:
            return
        self.content_scale = scale
        self.config.set("content_scale", self.content_scale)
        self._apply_styles()
        self._render_symbols()

    def _handle_window_wheel(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.ControlModifier:
            step = 0.1 if delta > 0 else -0.1
            self._set_content_scale(self.content_scale + step)
            event.accept()
            return
        self._switch_group_by_delta(-1 if delta > 0 else 1)
        event.accept()

    def _switch_group_by_delta(self, delta):
        count = self.tabs.count() if hasattr(self, "tabs") else 0
        if count <= 0:
            return
        index = (self.current_group_index + delta) % count
        self.tabs.setCurrentIndex(index)

    def _switch_group_by_number(self, number):
        index = number - 1
        if hasattr(self, "tabs") and 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def hide_panel(self):
        self._save_window_size()
        self._cancel_auto_resize_work()
        self.outside_timer.stop()
        self.hide()
        self._restore_base_size()

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

    def _render_symbols(self, generation=None):
        if generation is not None and generation != self._layout_generation:
            return
        self._resize_render_pending = False
        groups = self.data.get_groups()
        for child in self.symbol_container.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            child.hide()
            child.setParent(None)
            child.deleteLater()

        viewport_width = max(0, self.scroll.viewport().width())
        self._last_render_width = viewport_width
        self.symbol_container.setFixedWidth(viewport_width)
        available_width = max(120, viewport_width - 2)
        gap = self._scaled(10)
        row_gap = self._scaled(10)
        x = 0
        y = 0
        row_height = 0

        if not groups:
            label = QLabel("还没有分组", self.symbol_container)
            label.setGeometry(0, 0, available_width, 32)
            self.symbol_container.setMinimumHeight(40)
            self._adjust_window_to_content(40)
            return

        group = groups[self.current_group_index]
        for item_index, item in enumerate(group.get("items", [])):
            symbol = item["symbol"]
            button = SymbolButton(symbol, self._font_for_char, self, self.current_group_index, item_index)
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
        self._adjust_window_to_content(content_height)

    def _adjust_window_to_content(self, content_height):
        if self._manual_resize_active:
            return
        if not hasattr(self, "scroll") or self.stack.currentWidget() != self.main_view:
            return
        base_width = max(MIN_WINDOW_WIDTH, self.base_window_size.width())
        base_height = max(MIN_WINDOW_HEIGHT, self.base_window_size.height())
        non_scroll_height = max(0, self.height() - self.scroll.viewport().height())
        needed_height = max(base_height, non_scroll_height + max(1, content_height))

        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            max_height = max(MIN_WINDOW_HEIGHT, area.height() - 20)
        else:
            area = None
            max_height = 900
        target_height = min(needed_height, max_height)
        target_width = max(base_width, self.width())
        if abs(target_height - self.height()) < 2 and target_width == self.width():
            return

        target = QRect(self.x(), self.y(), target_width, int(target_height))
        if area and target.bottom() > area.bottom() - 10:
            target.moveBottom(area.bottom() - 10)
        if area and target.top() < area.top() + 10:
            target.moveTop(area.top() + 10)

        self._auto_resize_active = True
        self.resize_animation.stop()
        self.resize_animation.setStartValue(self.geometry())
        self.resize_animation.setEndValue(target)
        self.resize_animation.start()

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
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "LXGW WenKai", "闇為箿鏂囨シ", "Segoe UI"], cp)
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

    def _symbol_drag_payload(self, mime_data):
        try:
            raw = bytes(mime_data.data("application/x-kaomoji-symbol")).decode("utf-8")
            payload = json.loads(raw)
            return {
                "group_index": int(payload["group_index"]),
                "item_index": int(payload["item_index"]),
                "symbol": str(payload.get("symbol", "")),
            }
        except Exception as exc:
            log(f"Invalid symbol drag payload: {exc}")
            return None

    def _drop_symbol_on_group(self, mime_data, target_group_index):
        payload = self._symbol_drag_payload(mime_data)
        if not payload:
            return False
        if self.data.move_item_by_index(payload["group_index"], payload["item_index"], target_group_index, None):
            self.current_group_index = target_group_index
            QTimer.singleShot(0, self._reload_tabs)
            return True
        return False

    def _drop_symbol_at(self, mime_data, pos):
        payload = self._symbol_drag_payload(mime_data)
        if not payload:
            return False
        target_index = self._symbol_insert_index_at(pos)
        if self.data.move_item_by_index(
            payload["group_index"],
            payload["item_index"],
            self.current_group_index,
            target_index,
        ):
            QTimer.singleShot(0, self._render_symbols)
            return True
        return False

    def _symbol_insert_index_at(self, pos):
        buttons = sorted(
            self.symbol_container.findChildren(SymbolButton, options=Qt.FindDirectChildrenOnly),
            key=lambda button: button.item_index,
        )
        for button in buttons:
            rect = button.geometry()
            if pos.y() < rect.center().y():
                if pos.x() < rect.center().x() or pos.y() < rect.top():
                    return button.item_index
            if rect.top() <= pos.y() <= rect.bottom() and pos.x() < rect.center().x():
                return button.item_index
        return len(buttons)

    def _symbol_insert_marker_rect(self, insert_index):
        buttons = sorted(
            self.symbol_container.findChildren(SymbolButton, options=Qt.FindDirectChildrenOnly),
            key=lambda button: button.item_index,
        )
        if not buttons:
            return QRect(0, 0, 4, 44)

        for button in buttons:
            if insert_index <= button.item_index:
                rect = button.geometry()
                return QRect(max(0, rect.left() - 6), rect.top(), 4, rect.height())

        rect = buttons[-1].geometry()
        x = min(self.symbol_container.width() - 4, rect.right() + 8)
        return QRect(max(0, x), rect.top(), 4, rect.height())

    def _update_hotkey(self, hotkey=None):
        hotkey = (hotkey or self.hotkey_edit.text()).strip()
        if hotkey:
            try:
                parse_hotkey(hotkey)
            except ValueError as exc:
                log(str(exc))
                return
            if self.register_hotkey(hotkey):
                self.config.set("hotkey", hotkey)

    def _set_auto_start(self, enabled):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, self._auto_start_command())
                else:
                    try:
                        winreg.DeleteValue(key, RUN_VALUE_NAME)
                    except FileNotFoundError:
                        pass
            self.config.set("auto_start", bool(enabled))
        except Exception as exc:
            log(f"Auto-start toggle failed: {exc}")
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(self._is_auto_start_enabled())
            self.autostart_check.blockSignals(False)
            self._sync_autostart_state_label(self.autostart_check.isChecked())

    def _sync_autostart_state_label(self, enabled):
        if hasattr(self, "autostart_state"):
            self.autostart_state.setText("已开启" if enabled else "已关闭")

    def _auto_start_command(self):
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        executable = sys.executable
        if os.path.basename(executable).lower() == "python.exe":
            pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
            if os.path.exists(pythonw):
                executable = pythonw
        return f'"{executable}" "{os.path.abspath(__file__)}"'

    def _is_auto_start_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return value == self._auto_start_command()
        except FileNotFoundError:
            return False
        except OSError as exc:
            log(f"Auto-start read failed: {exc}")
            return bool(self.config.get("auto_start", False))

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
        self.data.save()

    def _save_window_size(self):
        self.config.set("window_width", self.base_window_size.width())
        self.config.set("window_height", self.base_window_size.height())

    def closeEvent(self, event):
        self.unregister_hotkey()
        self._uninstall_keyboard_hook()
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
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet(
            """
            QDialog#darkDialog {
                background: transparent;
                border: none;
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
                background: transparent;
                border: none;
                padding: 0px;
                selection-background-color: rgba(124, 111, 239, 0.55);
                font-size: 14px;
            }
            QPushButton {
                min-width: 70px;
                min-height: 30px;
                color: #e4e8f4;
                background: transparent;
                border: none;
                padding: 4px 10px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: transparent;
                border: none;
            }
            QPushButton#primaryButton {
                background: transparent;
                border: none;
            }
            QPushButton#dangerButton {
                background: transparent;
                border: none;
            }
            """
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        draw_rounded_fill_box(
            painter,
            self.rect(),
            12.0,
            QColor(12, 13, 22, 252),
            QColor(124, 111, 239, 87),
            1.0,
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

        self.edit = RoundedLineEdit()
        self.edit.setText(initial_text)
        self.edit.selectAll()
        layout.addWidget(self.edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_button = RoundedButton("确定")
        ok_button.setObjectName("primaryButton")
        cancel_button = RoundedButton("取消")
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
        confirm_button = RoundedButton(confirm_text)
        confirm_button.setObjectName("dangerButton")
        cancel_button = RoundedButton(cancel_text)
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


if __name__ == "__main__":
    app = KaomojiApp(sys.argv)
    sys.exit(app.exec())
