from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath


def draw_rounded_fill_box(painter, rect, radius, background, border, border_width=1.0):
    outer_rect = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    inner_rect = outer_rect.adjusted(border_width, border_width, -border_width, -border_width)

    outer_path = QPainterPath()
    outer_path.addRoundedRect(outer_rect, radius, radius)
    painter.fillPath(outer_path, border)

    inner_path = QPainterPath()
    inner_radius = max(0.0, radius - border_width)
    inner_path.addRoundedRect(inner_rect, inner_radius, inner_radius)
    painter.fillPath(inner_path, background)


def window_theme(widget):
    current = widget
    while current is not None:
        config = getattr(current, "config", None)
        if config is not None:
            return config.get("theme", "light")
        current = current.parentWidget()
    return "light"


def in_dark_dialog(widget):
    current = widget
    while current is not None:
        if current.objectName() == "darkDialog":
            return True
        current = current.parentWidget()
    return False
