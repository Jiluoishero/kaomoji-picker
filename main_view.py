from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from drag_widgets import SortableTabBar, SymbolContainer
from rounded_widgets import RoundedButton, RoundedFrame, RoundedTextEdit


def build_main_view(window):
    window.main_view = QWidget()
    layout = QVBoxLayout(window.main_view)
    layout.setContentsMargins(14, 10, 14, 14)
    layout.setSpacing(9)

    tab_row = QHBoxLayout()
    tab_row.setContentsMargins(0, 0, 0, 0)
    window.tabs = SortableTabBar(window)
    window.tabs.setExpanding(False)
    window.tabs.setMovable(True)
    window.tabs.currentChanged.connect(window._set_current_group)
    window.tabs.tabMoved.connect(window.data_actions.reorder_groups)
    window.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
    window.tabs.customContextMenuRequested.connect(window._show_group_context_menu)
    tab_row.addWidget(window.tabs, 1)
    layout.addLayout(tab_row)

    window.add_box = RoundedFrame("addBox", window)
    window.add_box.setObjectName("addBox")
    add_layout = QVBoxLayout(window.add_box)
    add_layout.setContentsMargins(10, 10, 10, 10)
    window.add_hint = QLabel("每行输入一个符号")
    window.add_text = RoundedTextEdit()
    window.add_text.setFixedHeight(76)
    add_buttons = QHBoxLayout()
    add_buttons.addStretch(1)
    cancel = RoundedButton("取消")
    confirm = RoundedButton("确认添加")
    cancel.clicked.connect(window._exit_add_mode)
    confirm.clicked.connect(window._confirm_add)
    add_buttons.addWidget(cancel)
    add_buttons.addWidget(confirm)
    add_layout.addWidget(window.add_hint)
    add_layout.addWidget(window.add_text)
    add_layout.addLayout(add_buttons)
    window.add_box.hide()
    layout.addWidget(window.add_box)

    window.scroll = QScrollArea()
    window.scroll.setWidgetResizable(True)
    window.scroll.setFrameShape(QFrame.NoFrame)
    window.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.symbol_container = SymbolContainer(window)
    window.symbol_container.setMinimumHeight(1)
    window.scroll.setWidget(window.symbol_container)
    layout.addWidget(window.scroll, 1)

    window.stack.addWidget(window.main_view)
