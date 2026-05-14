from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from hotkey_edit import HotkeyEdit
from rounded_widgets import RoundedButton, RoundedSwitch


def build_settings_view(window):
    window.settings_view = QWidget()
    layout = QVBoxLayout(window.settings_view)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    back = RoundedButton("‹")
    back.setFixedSize(30, 30)
    back.clicked.connect(window._show_main)
    title = QLabel("设置")
    title.setObjectName("settingsTitle")
    header.addWidget(back)
    header.addWidget(title)
    header.addStretch(1)
    layout.addLayout(header)

    hotkey_row = _setting_row("快捷键", "全局唤起面板")
    window.hotkey_edit = HotkeyEdit(window.config.get("hotkey", "ctrl+q"))
    window.hotkey_edit.setFixedWidth(150)
    window.hotkey_edit.hotkeyChanged.connect(window._update_hotkey)
    hotkey_row.addWidget(window.hotkey_edit)
    layout.addLayout(hotkey_row)

    auto_row = _setting_row("开机自启", "登录 Windows 后自动运行")
    window.autostart_check = RoundedSwitch()
    window.autostart_check.setChecked(window._is_auto_start_enabled())
    window.autostart_check.toggled.connect(window._set_auto_start)
    window.autostart_state = QLabel()
    window.autostart_state.setObjectName("settingDesc")
    window._sync_autostart_state_label(window.autostart_check.isChecked())
    window.autostart_check.toggled.connect(window._sync_autostart_state_label)
    auto_row.addWidget(window.autostart_state)
    auto_row.addWidget(window.autostart_check)
    layout.addLayout(auto_row)

    layout.addStretch(1)
    window.stack.addWidget(window.settings_view)


def _setting_row(label, desc):
    row = QHBoxLayout()
    text = QVBoxLayout()
    title = QLabel(label)
    title.setObjectName("settingLabel")
    subtitle = QLabel(desc)
    subtitle.setObjectName("settingDesc")
    text.addWidget(title)
    text.addWidget(subtitle)
    row.addLayout(text)
    row.addStretch(1)
    return row
