import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process
from PySide6.QtCore import QEasingCurve, QEvent, QMimeData, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH
from app_shell import KaomojiApp
from app_logging import log
from autostart_manager import is_auto_start_enabled, set_auto_start_enabled
from clipboard_util import ClipboardUtil
from data_actions import DataActionController
from config_manager import ConfigManager
from data_manager import DataManager
from flow_layout import FlowLayout
from font_resolver import FontResolver
from hotkey_parser import parse_hotkey
from main_view import build_main_view
from resize_geometry import resize_handle_geometries, resized_window_geometry
from resize_handle import ResizeHandle
from rounded_widgets import RoundedFrame
from settings_view import build_settings_view
from symbol_button import SymbolButton
from style_sheets import apply_window_styles
from title_bar import TitleBar
from ui_helpers import draw_rounded_fill_box, in_dark_dialog, window_theme
from win32_constants import (
    DWMWA_WINDOW_CORNER_PREFERENCE,
    DWMWCP_DONOTROUND,
    GA_ROOT,
    GWL_EXSTYLE,
    HOTKEY_ID,
    MA_NOACTIVATE,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_SHOWWINDOW,
    SW_SHOWNOACTIVATE,
    VK_MODIFIERS,
    VK_TOP_ROW_DIGITS,
    WH_KEYBOARD_LL,
    WM_HOTKEY,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_MOUSEACTIVATE,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    WS_EX_APPWINDOW,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
)
from win32_types import KBDLLHOOKSTRUCT, LowLevelKeyboardProc


class KaomojiWindow(QWidget):
    digit_shortcut_pressed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("颜文字输入器")
        self.config = ConfigManager()
        self.data = DataManager()
        self.data_actions = DataActionController(self)
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
        self.font_resolver = FontResolver()
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
        # The picker normally must not activate, otherwise clicks steal focus from
        # the target input window and Ctrl+V can paste into the picker instead.
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
        # Settings and edit dialogs need real focus; symbol picking does not.
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
        build_main_view(self)

    def _build_settings_view(self):
        build_settings_view(self)

    def _apply_styles(self):
        apply_window_styles(self)

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
        geometries = resize_handle_geometries(self.width(), self.height())
        for direction, handle in self.resize_handles.items():
            handle.setGeometry(geometries[direction])
            handle.raise_()

    def resize_from_handle(self, direction, start_geometry, delta):
        self.setGeometry(resized_window_geometry(direction, start_geometry, delta))

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
        # Let Qt create/show the native window before reapplying Win32 styles.
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
            self.data_actions.move_symbol(symbol, move_actions[action])
        elif action == delete_action:
            self.data_actions.delete_symbol(symbol)

    def _show_group_context_menu(self, pos):
        index = self.tabs.tabAt(pos)
        groups = self.data.get_groups()
        if index < 0 or index >= len(groups):
            menu = QMenu(self)
            menu.setSeparatorsCollapsible(False)
            add_group_action = menu.addAction("添加新分组")
            if menu.exec(self.tabs.mapToGlobal(pos)) == add_group_action:
                self.data_actions.add_group()
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
            self.data_actions.rename_group(group_name)
        elif action == delete_group_action:
            self.data_actions.confirm_delete_group(group_name)
        elif action == add_group_action:
            self.data_actions.add_group()

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
            button = SymbolButton(symbol, self.font_resolver.font_for_char, self, self.current_group_index, item_index)
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
            set_auto_start_enabled(enabled, __file__)
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

    def _is_auto_start_enabled(self):
        try:
            return is_auto_start_enabled(__file__)
        except OSError as exc:
            log(f"Auto-start read failed: {exc}")
            return bool(self.config.get("auto_start", False))

    def _save_window_size(self):
        self.config.set("window_width", self.base_window_size.width())
        self.config.set("window_height", self.base_window_size.height())

    def closeEvent(self, event):
        self.unregister_hotkey()
        self._uninstall_keyboard_hook()
        self._save_window_size()
        super().closeEvent(event)


if __name__ == "__main__":
    app = KaomojiApp(sys.argv, KaomojiWindow)
    sys.exit(app.exec())

