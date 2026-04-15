"""Key name → terminal escape sequence mapping."""

_NAMED_KEYS: dict[str, str] = {
    "enter": "\r",
    "return": "\r",
    "tab": "\t",
    "escape": "\x1b",
    "esc": "\x1b",
    "backspace": "\x7f",
    "delete": "\x1b[3~",
    "insert": "\x1b[2~",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
    "space": " ",
}

_CTRL_KEYS: dict[str, str] = {
    f"ctrl-{chr(c)}": chr(c - ord('a') + 1)
    for c in range(ord('a'), ord('z') + 1)
}


def resolve_key(name: str) -> str:
    """Resolve a human-readable key name to its terminal escape sequence.
    Raises ValueError if the key name is not recognized.
    """
    lower = name.lower().strip()
    if lower in _NAMED_KEYS:
        return _NAMED_KEYS[lower]
    if lower in _CTRL_KEYS:
        return _CTRL_KEYS[lower]
    raise ValueError(f"Unknown key: {name!r}")
