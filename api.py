import threading
from data_manager import DataManager
from config_manager import ConfigManager
from clipboard_util import ClipboardUtil


class Api:
    def __init__(self, app):
        self._app = app
        self._data = DataManager()
        self._config = ConfigManager()
        self._clipboard = ClipboardUtil()

    def get_groups(self):
        return self._data.get_groups()

    def add_items(self, group_name, items_text):
        symbols = [line.strip() for line in items_text.split('\n') if line.strip()]
        return self._data.add_items(group_name, symbols)

    def delete_item(self, group_name, symbol):
        return self._data.delete_item(group_name, symbol)

    def add_group(self, name):
        return self._data.add_group(name)

    def delete_group(self, name):
        return self._data.delete_group(name)

    def rename_group(self, old_name, new_name):
        return self._data.rename_group(old_name, new_name)

    def reorder_groups(self, group_names):
        return self._data.reorder_groups(group_names)

    def paste_symbol(self, symbol):
        if self._app.prev_window_handle:
            self._clipboard.paste_symbol(symbol, self._app.prev_window_handle)
        if self._app.mode == 'single':
            threading.Thread(target=self._app.hide_panel, daemon=True).start()

    def get_mode(self):
        return self._app.mode

    def close_panel(self):
        threading.Thread(target=self._app.hide_panel, daemon=True).start()

    def get_config(self):
        return self._config.get_all()

    def set_config(self, key, value):
        self._config.set(key, value)
        if key == 'hotkey':
            self._app.update_hotkey(value)

    def set_hotkey(self, hotkey):
        self._config.set('hotkey', hotkey)
        self._app.update_hotkey(hotkey)

    def set_auto_start(self, enabled):
        self._config.set('auto_start', enabled)
        self._app.set_auto_start(enabled)
