import os
import sys
import winreg


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "KaomojiPicker"


def auto_start_command(script_path):
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    executable = sys.executable
    if os.path.basename(executable).lower() == "python.exe":
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            executable = pythonw
    return f'"{executable}" "{os.path.abspath(script_path)}"'


def set_auto_start_enabled(enabled, script_path):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, auto_start_command(script_path))
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def is_auto_start_enabled(script_path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
        return value == auto_start_command(script_path)
    except FileNotFoundError:
        return False
