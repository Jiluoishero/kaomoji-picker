import pyperclip
import time
import ctypes
import win32gui
import win32con
import win32api
import win32process


class ClipboardUtil:
    def __init__(self):
        self._saved_text = None

    def save_clipboard(self):
        try:
            self._saved_text = pyperclip.paste()
        except Exception:
            self._saved_text = None

    def write_symbol(self, symbol):
        pyperclip.copy(symbol)

    def restore_clipboard(self):
        if self._saved_text is not None:
            try:
                pyperclip.copy(self._saved_text)
            except Exception:
                pass
            self._saved_text = None

    @staticmethod
    def set_foreground_window(hwnd):
        try:
            current_thread = win32api.GetCurrentThreadId()
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

            if current_thread != target_thread:
                win32process.AttachThreadInput(target_thread, current_thread, True)

            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)

            if current_thread != target_thread:
                win32process.AttachThreadInput(target_thread, current_thread, False)
        except Exception as e:
            print(f"SetForegroundWindow failed: {e}")

    @staticmethod
    def simulate_paste():
        VK_CONTROL = 0x11
        VK_V = 0x56
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def paste_symbol(self, symbol, target_hwnd):
        self.save_clipboard()
        self.write_symbol(symbol)
        self.set_foreground_window(target_hwnd)
        time.sleep(0.05)
        self.simulate_paste()
        time.sleep(0.1)
        self.restore_clipboard()

    def paste_symbol_direct(self, symbol):
        """Paste when the target window already has focus (NOACTIVATE mode)."""
        self.save_clipboard()
        self.write_symbol(symbol)
        time.sleep(0.05)
        self.simulate_paste()
        time.sleep(0.1)
        self.restore_clipboard()
