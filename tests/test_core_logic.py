import json
import os
import tempfile
import unittest

import win32con

from app_paths import runtime_file
from config_manager import ConfigManager
from data_manager import DataManager
from hotkey_parser import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    parse_hotkey,
)


class HotkeyParserTests(unittest.TestCase):
    def test_parse_common_hotkeys(self):
        self.assertEqual(parse_hotkey("ctrl+q"), (MOD_NOREPEAT | MOD_CONTROL, ord("Q")))
        self.assertEqual(parse_hotkey("Ctrl + Shift + F12"), (MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, win32con.VK_F12))
        self.assertEqual(parse_hotkey("alt+grave"), (MOD_NOREPEAT | MOD_ALT, 0xC0))
        self.assertEqual(parse_hotkey("win+space"), (MOD_NOREPEAT | MOD_WIN, win32con.VK_SPACE))

    def test_rejects_modifier_only_hotkey(self):
        with self.assertRaises(ValueError):
            parse_hotkey("ctrl+shift")


class RuntimePathTests(unittest.TestCase):
    def test_runtime_file_uses_module_directory_when_not_frozen(self):
        path = runtime_file(__file__, "sample.json")
        self.assertEqual(path, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.json"))


class ManagerTests(unittest.TestCase):
    def test_config_manager_fills_missing_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"hotkey": "alt+q"}, f)

            manager = ConfigManager(path)

            self.assertEqual(manager.get("hotkey"), "alt+q")
            self.assertEqual(manager.get("window_width"), 420)
            self.assertTrue(os.path.exists(path))

    def test_data_manager_moves_items_by_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.json")
            data = {
                "groups": [
                    {"name": "A", "items": [{"symbol": "1"}, {"symbol": "2"}]},
                    {"name": "B", "items": [{"symbol": "3"}]},
                ]
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            manager = DataManager(path)
            moved = manager.move_item_by_index(0, 1, 1, 0)

            self.assertTrue(moved)
            self.assertEqual([item["symbol"] for item in manager.get_groups()[0]["items"]], ["1"])
            self.assertEqual([item["symbol"] for item in manager.get_groups()[1]["items"]], ["2", "3"])


if __name__ == "__main__":
    unittest.main()
