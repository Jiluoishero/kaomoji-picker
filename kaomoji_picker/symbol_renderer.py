from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from kaomoji_picker.symbol_button import SymbolButton


def render_symbols(window, generation=None):
    if generation is not None and generation != window._layout_generation:
        return
    window._resize_render_pending = False
    groups = window.data.get_groups()
    _clear_symbol_container(window)

    viewport_width = max(0, window.scroll.viewport().width())
    window._last_render_width = viewport_width
    window.symbol_container.setFixedWidth(viewport_width)
    available_width = max(120, viewport_width - 2)

    if not groups:
        _render_empty_state(window, available_width)
        return

    content_height = _render_group_symbols(window, groups[window.current_group_index], available_width)
    window.symbol_container.setMinimumHeight(max(1, content_height))
    window.symbol_container.resize(viewport_width, max(1, content_height))
    window._adjust_window_to_content(content_height)


def _clear_symbol_container(window):
    for child in window.symbol_container.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
        child.hide()
        child.setParent(None)
        child.deleteLater()


def _render_empty_state(window, available_width):
    label = QLabel("还没有分组", window.symbol_container)
    label.setGeometry(0, 0, available_width, 32)
    window.symbol_container.setMinimumHeight(40)
    window._adjust_window_to_content(40)


def _render_group_symbols(window, group, available_width):
    gap = window._scaled(10)
    row_gap = window._scaled(10)
    x = 0
    y = 0
    row_height = 0

    for item_index, item in enumerate(group.get("items", [])):
        symbol = item["symbol"]
        button = SymbolButton(
            symbol,
            window.font_resolver.font_for_char,
            window,
            window.current_group_index,
            item_index,
        )
        button.setParent(window.symbol_container)
        button.setContextMenuPolicy(Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos, b=button, s=symbol: window._show_symbol_context_menu(b, s, pos)
        )
        button.clicked.connect(lambda s=symbol: window._paste_symbol(s))

        hint = button.sizeHint()
        width = min(hint.width(), available_width)
        height = hint.height()
        if x > 0 and x + width > available_width:
            x = 0
            y += row_height + row_gap
            row_height = 0
        button.setGeometry(x, y, width, height)
        button.show()
        x += width + gap
        row_height = max(row_height, height)

    return y + row_height
