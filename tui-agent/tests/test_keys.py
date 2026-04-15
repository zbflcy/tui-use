# tests/test_keys.py
from tui_agent.keys import resolve_key


def test_enter():
    assert resolve_key("Enter") == "\r"


def test_tab():
    assert resolve_key("Tab") == "\t"


def test_escape_full_name():
    assert resolve_key("Escape") == "\x1b"


def test_escape_short_name():
    assert resolve_key("Esc") == "\x1b"


def test_ctrl_c():
    assert resolve_key("Ctrl-C") == "\x03"


def test_ctrl_d():
    assert resolve_key("Ctrl-D") == "\x04"


def test_ctrl_l():
    assert resolve_key("Ctrl-L") == "\x0c"


def test_backspace():
    assert resolve_key("Backspace") == "\x7f"


def test_arrow_up():
    assert resolve_key("Up") == "\x1b[A"


def test_arrow_down():
    assert resolve_key("Down") == "\x1b[B"


def test_arrow_right():
    assert resolve_key("Right") == "\x1b[C"


def test_arrow_left():
    assert resolve_key("Left") == "\x1b[D"


def test_f1():
    assert resolve_key("F1") == "\x1bOP"


def test_f12():
    assert resolve_key("F12") == "\x1b[24~"


def test_case_insensitive():
    assert resolve_key("enter") == "\r"
    assert resolve_key("ctrl-c") == "\x03"


def test_unknown_key_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown key"):
        resolve_key("NonExistentKey")


def test_generic_ctrl_key():
    # Ctrl-A = \x01, Ctrl-Z = \x1a
    assert resolve_key("Ctrl-A") == "\x01"
    assert resolve_key("Ctrl-Z") == "\x1a"
