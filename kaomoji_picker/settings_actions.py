from kaomoji_picker.app_logging import log
from kaomoji_picker.autostart_manager import is_auto_start_enabled, set_auto_start_enabled
from kaomoji_picker.hotkey_parser import parse_hotkey


def update_hotkey(window, hotkey=None):
    hotkey = (hotkey or window.hotkey_edit.text()).strip()
    if not hotkey:
        return
    try:
        parse_hotkey(hotkey)
    except ValueError as exc:
        log(str(exc))
        return
    if window.register_hotkey(hotkey):
        window.config.set("hotkey", hotkey)


def set_auto_start(window, enabled, script_path):
    try:
        set_auto_start_enabled(enabled, script_path)
        window.config.set("auto_start", bool(enabled))
    except Exception as exc:
        log(f"Auto-start toggle failed: {exc}")
        window.autostart_check.blockSignals(True)
        window.autostart_check.setChecked(is_auto_start(window, script_path))
        window.autostart_check.blockSignals(False)
        sync_autostart_state_label(window, window.autostart_check.isChecked())


def sync_autostart_state_label(window, enabled):
    if hasattr(window, "autostart_state"):
        window.autostart_state.setText("已开启" if enabled else "已关闭")


def is_auto_start(window, script_path):
    try:
        return is_auto_start_enabled(script_path)
    except OSError as exc:
        log(f"Auto-start read failed: {exc}")
        return bool(window.config.get("auto_start", False))
