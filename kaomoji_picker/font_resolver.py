from PySide6.QtGui import QFont, QRawFont


DEFAULT_FONT_CANDIDATES = [
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
    "Arial",
    "Segoe UI Symbol",
    "Segoe UI Emoji",
    "LXGW WenKai",
    "闇為箿鏂囨シ",
    "Gadugi",
    "Cambria Math",
]


class FontResolver:
    def __init__(self, candidates=None):
        self.candidates = list(candidates or DEFAULT_FONT_CANDIDATES)
        self._support_cache = {}

    def font_for_char(self, ch):
        cp = ord(ch)
        if cp in self._support_cache:
            return self._support_cache[cp]
        preferred = self._preferred_font_for_codepoint(cp)
        if preferred:
            self._support_cache[cp] = preferred
            return preferred
        for family in self.candidates:
            raw = QRawFont.fromFont(QFont(family, 12))
            if raw.isValid() and raw.supportsCharacter(cp):
                self._support_cache[cp] = family
                return family
        self._support_cache[cp] = "Microsoft YaHei UI"
        return "Microsoft YaHei UI"

    def _preferred_font_for_codepoint(self, cp):
        # Some Windows fonts report broad fallback coverage through Qt, but still
        # render tofu for uncommon kaomoji blocks. Prefer known-good fonts first.
        if 0x1400 <= cp <= 0x167F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Gadugi", "Segoe UI"], cp)
        if 0xA4D0 <= cp <= 0xA4FF:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "LXGW WenKai", "闇為箿鏂囨シ", "Segoe UI"], cp)
        if 0x1D00 <= cp <= 0x1D7F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"], cp)
        if 0x2070 <= cp <= 0x209F:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Cambria Math", "Segoe UI"], cp)
        if 0x0600 <= cp <= 0x06FF or 0xFE70 <= cp <= 0xFEFF:
            return self._first_available_font(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Microsoft Uighur", "Arial"], cp)
        if 0x2600 <= cp <= 0x27BF or 0x1F000 <= cp <= 0x1FAFF:
            return self._first_available_font(["Segoe UI Emoji", "Segoe UI Symbol"], cp)
        return None

    def _first_available_font(self, families, cp):
        for family in families:
            raw = QRawFont.fromFont(QFont(family, 12))
            if raw.isValid() and raw.supportsCharacter(cp):
                return family
        return None
