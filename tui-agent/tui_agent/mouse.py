"""Mouse event escape sequence generation (SGR mode)."""


def _sgr_event(button: int, col: int, row: int, release: bool = False) -> str:
    """Generate a single SGR mouse event escape sequence.
    SGR mouse coordinates are 1-indexed.
    Press uses 'M' suffix, release uses 'm' suffix.
    """
    suffix = "m" if release else "M"
    return f"\x1b[<{button};{col + 1};{row + 1}{suffix}"


def mouse_click(row: int, col: int) -> str:
    """Generate SGR mouse click (press + release) at the given 0-indexed position."""
    press = _sgr_event(button=0, col=col, row=row, release=False)
    release = _sgr_event(button=0, col=col, row=row, release=True)
    return press + release


def mouse_scroll_up(row: int, col: int, lines: int = 1) -> str:
    """Generate SGR scroll-up events at the given 0-indexed position."""
    single = _sgr_event(button=64, col=col, row=row)
    return single * lines


def mouse_scroll_down(row: int, col: int, lines: int = 1) -> str:
    """Generate SGR scroll-down events at the given 0-indexed position."""
    single = _sgr_event(button=65, col=col, row=row)
    return single * lines
