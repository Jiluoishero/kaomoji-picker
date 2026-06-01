from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    """A real wrapping layout for variable-width symbol buttons."""

    def __init__(self):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.item_list = []
        self.h_spacing = 10
        self.v_spacing = 10

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def clear(self):
        while self.count():
            item = self.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_wrapped(self, widgets, max_width):
        self.clear()
        for widget in widgets:
            self.addWidget(widget)
        self.invalidate()

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        right_padding = 28
        usable_width = max(1, effective.width() - right_padding)
        x = effective.x()
        y = effective.y()
        line_height = 0
        max_right = effective.x() + usable_width - 1

        for item in self.item_list:
            hint = item.sizeHint()
            item_width = min(hint.width(), usable_width)
            item_height = hint.height()
            next_x = x + item_width + self.h_spacing
            if x > effective.x() and next_x - self.h_spacing > max_right + 1:
                x = effective.x()
                y += line_height + self.v_spacing
                next_x = x + item_width + self.h_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_width, item_height)))

            x = next_x
            line_height = max(line_height, item_height)

        return y + line_height - rect.y() + margins.bottom()
