import json
import os
import tempfile
import unittest

import win32con
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRect
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from app_constants import DEFAULT_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH
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
from resize_geometry import resize_handle_geometries, resized_window_geometry
from rounded_widgets import RoundedTextEdit
from symbol_drag import SYMBOL_MIME_TYPE, parse_symbol_drag_payload, symbol_insert_index_at, symbol_insert_marker_rect


class FakeButton:
    def __init__(self, item_index, rect):
        self.item_index = item_index
        self._rect = rect

    def geometry(self):
        return self._rect


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
            self.assertEqual(manager.get("window_width"), DEFAULT_WINDOW_WIDTH)
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


class ResizeGeometryTests(unittest.TestCase):
    def test_resized_window_geometry_expands_from_south_east(self):
        result = resized_window_geometry("se", QRect(10, 20, 400, 350), QPoint(30, 40))
        self.assertEqual(result, QRect(10, 20, 430, 390))

    def test_resized_window_geometry_clamps_from_north_west(self):
        result = resized_window_geometry("nw", QRect(100, 120, 380, 340), QPoint(100, 80))
        self.assertEqual(result, QRect(100 + 380 - MIN_WINDOW_WIDTH, 120 + 340 - MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT))

    def test_resize_handle_geometries_cover_all_handles(self):
        geometries = resize_handle_geometries(400, 360)
        self.assertEqual(set(geometries), {"n", "s", "e", "w", "ne", "se", "sw", "nw"})
        self.assertEqual(geometries["n"], QRect(16, 8, 368, 8))
        self.assertEqual(geometries["se"], QRect(376, 336, 16, 16))


class SymbolDragTests(unittest.TestCase):
    def test_parse_symbol_drag_payload_normalizes_types(self):
        mime_data = QMimeData()
        mime_data.setData(SYMBOL_MIME_TYPE, QByteArray(b'{"group_index":"1","item_index":"2","symbol":123}'))

        self.assertEqual(
            parse_symbol_drag_payload(mime_data),
            {"group_index": 1, "item_index": 2, "symbol": "123"},
        )

    def test_symbol_insert_index_uses_button_geometry(self):
        buttons = [
            FakeButton(0, QRect(0, 0, 40, 30)),
            FakeButton(1, QRect(50, 0, 40, 30)),
        ]

        self.assertEqual(symbol_insert_index_at(QPoint(45, 10), buttons), 1)
        self.assertEqual(symbol_insert_index_at(QPoint(120, 10), buttons), 2)

    def test_symbol_insert_marker_rect_uses_target_or_tail(self):
        buttons = [
            FakeButton(0, QRect(0, 0, 40, 30)),
            FakeButton(1, QRect(50, 0, 40, 30)),
        ]

        self.assertEqual(symbol_insert_marker_rect(1, buttons, 120), QRect(44, 0, 4, 30))
        self.assertEqual(symbol_insert_marker_rect(2, buttons, 120), QRect(97, 0, 4, 30))


class RoundedTextEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_applies_font_fallback_per_character(self):
        editor = RoundedTextEdit()
        editor.set_font_resolver(lambda ch: "Segoe UI Emoji" if ch == "★" else "Microsoft YaHei UI")
        editor.setPlainText("A★")

        cursor = QTextCursor(editor.document())
        cursor.setPosition(1)
        cursor.setPosition(2, QTextCursor.KeepAnchor)
        self.assertIn("Segoe UI Emoji", cursor.charFormat().fontFamilies())


if __name__ == "__main__":
    unittest.main()
