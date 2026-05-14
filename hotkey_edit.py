from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter
from PySide6.QtWidgets import QLineEdit

from ui_helpers import draw_rounded_fill_box, window_theme


class HotkeyEdit(QLineEdit):
    hotkeyChanged = Signal(str)

    def __init__(self, hotkey):
        super().__init__(hotkey)
        self.setReadOnly(True)
        self.setPlaceholderText("按下快捷键")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setTextMargins(8, 0, 8, 0)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_unknown):
            return
        if key in (Qt.Key_Backspace, Qt.Key_Delete):
            self.clear()
            event.accept()
            return

        hotkey = self._event_to_hotkey(event)
        if hotkey:
            self.setText(hotkey)
            self.hotkeyChanged.emit(hotkey)
        event.accept()

    def mousePressEvent(self, event):
        self.selectAll()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        theme = window_theme(self)
        focused = self.hasFocus()
        if theme == "dark":
            background = QColor(16, 18, 34, 245) if focused else QColor(12, 14, 28, 235)
            border = QColor("#d9b368") if focused else QColor(217, 179, 104, 64)
        else:
            background = QColor(255, 255, 255, 255) if focused else QColor(250, 246, 252, 245)
            border = QColor("#C67A25") if focused else QColor(195, 180, 210, 80)
        draw_rounded_fill_box(painter, self.rect(), 10.0, background, border, 1.0)
        painter.end()
        super().paintEvent(event)

    def _event_to_hotkey(self, event):
        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.MetaModifier:
            parts.append("win")

        key_text = self._key_name(event.key())
        if not key_text:
            sequence = QKeySequence(event.key())
            key_text = sequence.toString(QKeySequence.PortableText).lower()
        if not key_text:
            return None
        parts.append(key_text)
        return "+".join(parts)

    def _key_name(self, key):
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(ord("a") + key - Qt.Key_A)
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(ord("0") + key - Qt.Key_0)
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            return f"f{key - Qt.Key_F1 + 1}"
        special = {
            Qt.Key_QuoteLeft: "`",
            Qt.Key_Space: "space",
            Qt.Key_Tab: "tab",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc",
        }
        return special.get(key)
