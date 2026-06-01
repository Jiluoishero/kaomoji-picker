import json

from PySide6.QtCore import QRect


SYMBOL_MIME_TYPE = "application/x-kaomoji-symbol"


def parse_symbol_drag_payload(mime_data):
    raw = bytes(mime_data.data(SYMBOL_MIME_TYPE)).decode("utf-8")
    payload = json.loads(raw)
    return {
        "group_index": int(payload["group_index"]),
        "item_index": int(payload["item_index"]),
        "symbol": str(payload.get("symbol", "")),
    }


def symbol_insert_index_at(pos, buttons):
    for button in sorted(buttons, key=lambda button: button.item_index):
        rect = button.geometry()
        if pos.y() < rect.center().y():
            if pos.x() < rect.center().x() or pos.y() < rect.top():
                return button.item_index
        if rect.top() <= pos.y() <= rect.bottom() and pos.x() < rect.center().x():
            return button.item_index
    return len(buttons)


def symbol_insert_marker_rect(insert_index, buttons, container_width):
    sorted_buttons = sorted(buttons, key=lambda button: button.item_index)
    if not sorted_buttons:
        return QRect(0, 0, 4, 44)

    for button in sorted_buttons:
        if insert_index <= button.item_index:
            rect = button.geometry()
            return QRect(max(0, rect.left() - 6), rect.top(), 4, rect.height())

    rect = sorted_buttons[-1].geometry()
    x = min(container_width - 4, rect.right() + 8)
    return QRect(max(0, x), rect.top(), 4, rect.height())
