import ctypes
import threading
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

from app_logging import log
from hotkey_parser import parse_hotkey


WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
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
    """Legacy message-only hotkey loop kept as a fallback reference.

    The active app path registers the hotkey against the picker window hwnd in
    main.py. This older implementation is intentionally kept out of main.py so
    the current hotkey path stays clear without losing the prior workaround.
    """

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
