from tui_agent.mouse import mouse_click, mouse_scroll_up, mouse_scroll_down


def test_click_generates_sgr_press_and_release():
    seq = mouse_click(row=5, col=20)
    # SGR mouse: press button 0 at (col, row) then release
    # SGR is 1-indexed for col and row
    assert seq == "\x1b[<0;21;6M\x1b[<0;21;6m"


def test_click_origin():
    seq = mouse_click(row=0, col=0)
    assert seq == "\x1b[<0;1;1M\x1b[<0;1;1m"


def test_scroll_up():
    seq = mouse_scroll_up(row=10, col=20, lines=3)
    single = "\x1b[<64;21;11M"
    assert seq == single * 3


def test_scroll_down():
    seq = mouse_scroll_down(row=10, col=20, lines=2)
    single = "\x1b[<65;21;11M"
    assert seq == single * 2


def test_scroll_default_lines():
    seq = mouse_scroll_up(row=0, col=0, lines=1)
    assert seq == "\x1b[<64;1;1M"
