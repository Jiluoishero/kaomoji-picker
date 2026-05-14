import json
import os

from app_paths import runtime_file

DEFAULT_CONFIG = {
    "hotkey": "ctrl+q",
    "auto_start": False,
    "double_click_interval": 300,
    "window_width": 420,
    "window_height": 480
}


class ConfigManager:
    def __init__(self, filepath=None):
        if filepath is None:
            self.filepath = runtime_file(__file__, 'config.json')
        else:
            self.filepath = filepath
        self.config = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                changed = False
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                        changed = True
                if changed:
                    self._save_data(config)
                return config
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
