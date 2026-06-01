from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from kaomoji_picker.rounded_widgets import RoundedButton, RoundedLineEdit
from kaomoji_picker.ui_helpers import draw_rounded_fill_box


class BaseDarkDialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setObjectName("darkDialog")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet(
            """
            QDialog#darkDialog {
                background: transparent;
                border: none;
            }
            QLabel {
                color: #e4e8f4;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 14px;
            }
            QLabel#dialogTitle {
                color: #cdd6f4;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit {
                color: #edf1ff;
                background: transparent;
                border: none;
                padding: 0px;
                selection-background-color: rgba(124, 111, 239, 0.55);
                font-size: 14px;
            }
            QPushButton {
                min-width: 70px;
                min-height: 30px;
                color: #e4e8f4;
                background: transparent;
                border: none;
                padding: 4px 10px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: transparent;
                border: none;
            }
            QPushButton#primaryButton {
                background: transparent;
                border: none;
            }
            QPushButton#dangerButton {
                background: transparent;
                border: none;
            }
            """
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        draw_rounded_fill_box(
            painter,
            self.rect(),
            12.0,
            QColor(12, 13, 22, 252),
            QColor(124, 111, 239, 87),
            1.0,
        )

    def exec_with_activation(self):
        # Dialogs temporarily opt out of the NOACTIVATE panel policy so inputs
        # can receive keyboard focus, then restore the picker behavior.
        self.parent_window._set_allow_activation(True)
        try:
            self.parent_window.activateWindow()
            return self.exec()
        finally:
            self.parent_window._set_allow_activation(False)


class SimpleInputDialog(BaseDarkDialog):
    def __init__(self, parent, title, label, initial_text=""):
        super().__init__(parent, title)
        self.setFixedWidth(270)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        message = QLabel(label)
        layout.addWidget(message)

        self.edit = RoundedLineEdit()
        self.edit.setText(initial_text)
        self.edit.selectAll()
        layout.addWidget(self.edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_button = RoundedButton("确定")
        ok_button.setObjectName("primaryButton")
        cancel_button = RoundedButton("取消")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    @staticmethod
    def get_text(parent, title, label, initial_text=""):
        dialog = SimpleInputDialog(parent, title, label, initial_text)
        result = dialog.exec_with_activation()
        return dialog.edit.text(), result == QDialog.Accepted


class ConfirmDialog(BaseDarkDialog):
    def __init__(self, parent, title, message, confirm_text="确定", cancel_text="取消"):
        super().__init__(parent, title)
        self.setFixedWidth(330)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        confirm_button = RoundedButton(confirm_text)
        confirm_button.setObjectName("dangerButton")
        cancel_button = RoundedButton(cancel_text)
        confirm_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    @staticmethod
    def ask(parent, title, message, confirm_text="确定", cancel_text="取消"):
        dialog = ConfirmDialog(parent, title, message, confirm_text, cancel_text)
        return dialog.exec_with_activation() == QDialog.Accepted
