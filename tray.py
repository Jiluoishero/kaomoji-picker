import pystray
from PIL import Image, ImageDraw


class TrayManager:
    def __init__(self, app):
        self.app = app
        self.icon = None

    def _create_icon_image(self):
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded purple background
        draw.rounded_rectangle([(2, 2), (62, 62)], radius=14, fill=(124, 111, 239, 255))

        # Simple cute face
        # Eyes - two dots
        draw.ellipse([(17, 20), (25, 28)], fill=(255, 255, 255, 255))
        draw.ellipse([(39, 20), (47, 28)], fill=(255, 255, 255, 255))

        # Smile arc
        draw.arc([(22, 30), (42, 46)], start=0, end=180, fill=(255, 255, 255, 255), width=2)

        # Cheek blush
        draw.ellipse([(10, 30), (20, 38)], fill=(255, 180, 200, 120))
        draw.ellipse([(44, 30), (54, 38)], fill=(255, 180, 200, 120))

        return img

    def run(self):
        image = self._create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem('显示面板', self._on_show),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('退出', self._on_exit),
        )
        self.icon = pystray.Icon('kaomoji_picker', image, 'Kaomoji Picker', menu)
        self.icon.run()

    def _on_show(self, icon, item):
        self.app.show_panel()

    def _on_exit(self, icon, item):
        self.icon.stop()
        self.app.quit()

    def stop(self):
        if self.icon:
            self.icon.stop()
