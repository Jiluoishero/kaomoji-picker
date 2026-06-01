import win32con


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


def parse_hotkey(hotkey):
    modifiers = MOD_NOREPEAT
    key = None
    aliases = {
        "`": 0xC0,
        "grave": 0xC0,
        "space": win32con.VK_SPACE,
        "tab": win32con.VK_TAB,
        "enter": win32con.VK_RETURN,
        "return": win32con.VK_RETURN,
        "esc": win32con.VK_ESCAPE,
        "escape": win32con.VK_ESCAPE,
        "backspace": win32con.VK_BACK,
        "delete": win32con.VK_DELETE,
    }

    for part in [p.strip().lower() for p in hotkey.split("+") if p.strip()]:
        if part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part in ("win", "meta", "cmd"):
            modifiers |= MOD_WIN
        elif part in aliases:
            key = aliases[part]
        elif len(part) == 1 and part.isalpha():
            key = ord(part.upper())
        elif len(part) == 1 and part.isdigit():
            key = ord(part)
        elif part.startswith("f") and part[1:].isdigit():
            number = int(part[1:])
            if 1 <= number <= 24:
                key = win32con.VK_F1 + number - 1

    if key is None:
        raise ValueError(f"Unsupported hotkey: {hotkey}")
    return modifiers, key
