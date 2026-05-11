import logging
logging.getLogger('pywebview').setLevel(logging.CRITICAL)

import webview
import keyboard
import threading
import time
import os
import sys
import win32gui
import win32api
import win32con

from api import Api
from tray import TrayManager
from config_manager import ConfigManager

# Win32 constants
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0
GA_ROOT = 2
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02


class KaomojiApp:
    def __init__(self):
        self.config = ConfigManager()
        self.api = Api(self)
        self.window = None
        self.prev_window_handle = None
        self.mode = 'single'
        self.last_hotkey_time = 0
        self.visible = False
        self.tray = None
        self._hotkey_handle = None
        self._hwnd = None
        self._outside_monitor_stop = threading.Event()
        self._outside_monitor_thread = None

    def start(self):
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
        self.window = webview.create_window(
            'Kaomoji Picker',
            os.path.join(web_dir, 'index.html'),
            js_api=self.api,
            width=420,
            height=480,
            frameless=True,
            transparent=True,
            on_top=True,
            resizable=False,
            # Do NOT use hidden=True — WebView2 won't load content
        )
        webview.start(self._on_ready, debug=False)

    def _on_ready(self):
        # Wait for content to fully load
        time.sleep(1.5)

        # Push initial data to frontend via evaluate_js
        import json
        groups_json = json.dumps(self.api.get_groups(), ensure_ascii=False)
        config_json = json.dumps(self.api.get_config(), ensure_ascii=False)
        self.window.evaluate_js(f"window._initData={groups_json};")
        self.window.evaluate_js(f"window._initConfig={config_json};")
        self.window.evaluate_js("if(typeof initFromPython==='function')initFromPython();")

        # Hide window after content is loaded
        self.window.hide()

        # Modify window style
        self._setup_window_style()
        self._setup_hotkey()

        self.tray = TrayManager(self)
        self.tray.run()

    def _setup_window_style(self):
        self._hwnd = win32gui.FindWindow(None, 'Kaomoji Picker')
        if not self._hwnd:
            return
        ex_style = win32gui.GetWindowLong(self._hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_TOOLWINDOW      # No taskbar entry
        ex_style &= ~WS_EX_APPWINDOW
        # NOT using WS_EX_NOACTIVATE — it breaks WebView2 click events
        win32gui.SetWindowLong(self._hwnd, GWL_EXSTYLE, ex_style)

    def _setup_hotkey(self):
        hotkey = self.config.get('hotkey', 'ctrl+`')
        self._register_hotkey(hotkey)

    def _register_hotkey(self, hotkey):
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except Exception:
                pass
        try:
            self._hotkey_handle = keyboard.add_hotkey(hotkey, self._on_hotkey, suppress=True)
        except Exception as e:
            print(f"Failed to register hotkey '{hotkey}': {e}")

    def update_hotkey(self, new_hotkey):
        self._register_hotkey(new_hotkey)

    def _on_hotkey(self):
        current_time = time.time()
        interval = self.config.get('double_click_interval', 300) / 1000.0

        if self.visible:
            if self.mode == 'single' and current_time - self.last_hotkey_time < interval:
                self.mode = 'pinned'
                if self.window:
                    self.window.evaluate_js("updateMode('pinned')")
            else:
                self.hide_panel()
            self.last_hotkey_time = current_time
            return

        if current_time - self.last_hotkey_time < interval:
            self.mode = 'pinned'
        else:
            self.mode = 'single'

        self.last_hotkey_time = current_time
        self.show_panel()

    def _window_contains_point(self, hwnd, x, y):
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return left <= x <= right and top <= y <= bottom
        except Exception:
            return False

    def _is_app_foreground(self, hwnd):
        try:
            foreground = win32gui.GetForegroundWindow()
            if not foreground:
                return False
            root = win32gui.GetAncestor(foreground, GA_ROOT)
            return foreground == hwnd or root == hwnd
        except Exception:
            return False

    def _is_mouse_button_down(self):
        return (
            win32api.GetAsyncKeyState(VK_LBUTTON) & 0x8000
            or win32api.GetAsyncKeyState(VK_RBUTTON) & 0x8000
        )

    def _start_outside_monitor(self):
        self._stop_outside_monitor()
        if (
            self._outside_monitor_thread
            and self._outside_monitor_thread.is_alive()
            and threading.current_thread() is not self._outside_monitor_thread
        ):
            self._outside_monitor_thread.join(timeout=0.2)
        self._outside_monitor_stop.clear()
        self._outside_monitor_thread = threading.Thread(
            target=self._monitor_outside_clicks,
            daemon=True,
        )
        self._outside_monitor_thread.start()

    def _stop_outside_monitor(self):
        self._outside_monitor_stop.set()

    def _monitor_outside_clicks(self):
        time.sleep(0.2)
        activated_once = False

        while not self._outside_monitor_stop.is_set():
            time.sleep(0.08)
            if not self.visible:
                return
            if self.mode != 'single':
                continue

            hwnd = self._hwnd or win32gui.FindWindow(None, 'Kaomoji Picker')
            if not hwnd:
                continue
            self._hwnd = hwnd

            if self._is_app_foreground(hwnd):
                activated_once = True
                continue

            if activated_once:
                self.hide_panel()
                return

            try:
                x, y = win32api.GetCursorPos()
                if self._is_mouse_button_down() and not self._window_contains_point(hwnd, x, y):
                    self.hide_panel()
                    return
            except Exception:
                pass

    def show_panel(self):
        if not self.window:
            return

        try:
            self.prev_window_handle = win32gui.GetForegroundWindow()
        except Exception:
            self.prev_window_handle = None

        try:
            x, y = win32api.GetCursorPos()
        except Exception:
            x, y = 200, 200

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        win_w, win_h = 420, 480
        if x + win_w > screen_w:
            x = screen_w - win_w - 10
        if y + win_h > screen_h:
            y = screen_h - win_h - 10
        x = max(10, x)
        y = max(10, y)

        hwnd = self._hwnd or win32gui.FindWindow(None, 'Kaomoji Picker')
        if hwnd:
            self._hwnd = hwnd
            # Move window to position
            win32gui.MoveWindow(hwnd, x, y, win_w, win_h, True)
            # Show without activating (SW_SHOWNOACTIVATE = 4)
            win32gui.ShowWindow(hwnd, 4)
            # Ensure topmost
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                  SWP_NOACTIVATE | 0x0001 | 0x0002)  # NOMOVE|NOSIZE
        else:
            self.window.move(x, y)
            self.window.show()

        self.visible = True
        if self.mode == 'single':
            self._start_outside_monitor()
        else:
            self._stop_outside_monitor()

        try:
            self.window.evaluate_js(f"updateMode('{self.mode}')")
            self.window.evaluate_js("onPanelShow()")
        except Exception:
            pass

    def hide_panel(self):
        if not self.window or not self.visible:
            return
        self.visible = False
        self._stop_outside_monitor()
        try:
            self.window.evaluate_js("onPanelHide()")
            time.sleep(0.15)
        except Exception:
            pass

        hwnd = self._hwnd or win32gui.FindWindow(None, 'Kaomoji Picker')
        if hwnd:
            win32gui.ShowWindow(hwnd, SW_HIDE)
        else:
            self.window.hide()

    def set_auto_start(self, enabled):
        try:
            import win32com.client
            startup_path = os.path.join(
                os.getenv('APPDATA'),
                'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup',
                'KaomojiPicker.lnk'
            )
            if enabled:
                shell = win32com.client.Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(startup_path)
                shortcut.Targetpath = sys.executable
                shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
                shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
                shortcut.save()
            else:
                if os.path.exists(startup_path):
                    os.remove(startup_path)
        except Exception as e:
            print(f"Auto-start toggle failed: {e}")

    def quit(self):
        if self.window:
            self.window.destroy()
        os._exit(0)


if __name__ == '__main__':
    app = KaomojiApp()
    app.start()
