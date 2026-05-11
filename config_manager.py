import json
import os

DEFAULT_CONFIG = {
    "hotkey": "ctrl+`",
    "auto_start": False,
    "double_click_interval": 300
}


class ConfigManager:
    def __init__(self, filepath=None):
        if filepath is None:
            self.filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        else:
            self.filepath = filepath
        self.config = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        config = dict(DEFAULT_CONFIG)
        self._save_data(config)
        return config

    def _save_data(self, config=None):
        if config is None:
            config = self.config
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def save(self):
        self._save_data()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def get_all(self):
        return dict(self.config)
