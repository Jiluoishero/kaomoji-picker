import threading
from data_manager import DataManager
from config_manager import ConfigManager
from clipboard_util import ClipboardUtil


class Api:
    def __init__(self, app):
        self.app = app
        self.data = DataManager()
        self.config = ConfigManager()
        self.clipboard = ClipboardUtil()

    def get_groups(self):
        return self.data.get_groups()

    def add_items(self, group_name, items_text):
        symbols = [line.strip() for line in items_text.split('\n') if line.strip()]
        return self.data.add_items(group_name, symbols)

    def delete_item(self, group_name, symbol):
        return self.data.delete_item(group_name, symbol)

    def add_group(self, name):
        return self.data.add_group(name)

    def delete_group(self, name):
        return self.data.delete_group(name)

    def rename_group(self, old_name, new_name):
        return self.data.rename_group(old_name, new_name)

    def reorder_groups(self, group_names):
        return self.data.reorder_groups(group_names)

    def paste_symbol(self, symbol):
        if self.app.prev_window_handle:
            self.clipboard.paste_symbol(symbol, self.app.prev_window_handle)
        if self.app.mode == 'single':
            threading.Thread(target=self.app.hide_panel, daemon=True).start()

    def get_mode(self):
        return self.app.mode

    def close_panel(self):
        threading.Thread(target=self.app.hide_panel, daemon=True).start()

    def get_config(self):
        return self.config.get_all()

    def set_config(self, key, value):
        self.config.set(key, value)
        if key == 'hotkey':
            self.app.update_hotkey(value)

    def set_hotkey(self, hotkey):
        self.config.set('hotkey', hotkey)
        self.app.update_hotkey(hotkey)

    def set_auto_start(self, enabled):
        self.config.set('auto_start', enabled)
        self.app.set_auto_start(enabled)
