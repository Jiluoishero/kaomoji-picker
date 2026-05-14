from PySide6.QtCore import QRect

from app_constants import MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH


def resize_handle_geometries(width, height):
    edge = 8
    corner = 16
    inset = 8
    return {
        "n": QRect(corner, inset, max(0, width - corner * 2), edge),
        "s": QRect(corner, height - inset - edge, max(0, width - corner * 2), edge),
        "e": QRect(width - inset - edge, corner, edge, max(0, height - corner * 2)),
        "w": QRect(inset, corner, edge, max(0, height - corner * 2)),
        "ne": QRect(width - inset - corner, inset, corner, corner),
        "se": QRect(width - inset - corner, height - inset - corner, corner, corner),
        "sw": QRect(inset, height - inset - corner, corner, corner),
        "nw": QRect(inset, inset, corner, corner),
    }


def resized_window_geometry(direction, start_geometry, delta):
    x = start_geometry.x()
    y = start_geometry.y()
    width = start_geometry.width()
    height = start_geometry.height()
    dx = delta.x()
    dy = delta.y()

    if "e" in direction:
        width += dx
    if "s" in direction:
        height += dy
    if "w" in direction:
        x += dx
        width -= dx
        if width < MIN_WINDOW_WIDTH:
            x -= MIN_WINDOW_WIDTH - width
            width = MIN_WINDOW_WIDTH
    if "n" in direction:
        y += dy
        height -= dy
        if height < MIN_WINDOW_HEIGHT:
            y -= MIN_WINDOW_HEIGHT - height
            height = MIN_WINDOW_HEIGHT

    width = max(MIN_WINDOW_WIDTH, width)
    height = max(MIN_WINDOW_HEIGHT, height)
    return QRect(x, y, width, height)
