import time


def test_session_starts_and_is_alive(echo_session):
    assert echo_session.is_alive()
    assert echo_session.pid > 0


def test_session_capture_initial_screen(echo_session):
    time.sleep(0.1)
    lines = echo_session.capture()
    assert isinstance(lines, list)
    assert len(lines) == 24
    assert all(len(line) == 80 for line in lines)


def test_session_type_and_capture(echo_session):
    echo_session.type_text("hello")
    echo_session.send_key("Enter")
    time.sleep(0.2)
    lines = echo_session.capture()
    screen_text = "\n".join(lines)
    assert "hello" in screen_text


def test_session_cursor_position(echo_session):
    time.sleep(0.1)
    row, col = echo_session.cursor_position()
    assert isinstance(row, int)
    assert isinstance(col, int)


def test_session_send_key(echo_session):
    echo_session.type_text("test")
    echo_session.send_key("Enter")
    time.sleep(0.1)
    echo_session.send_key("Ctrl-C")
    time.sleep(0.3)
    assert not echo_session.is_alive()


def test_session_resize(echo_session):
    echo_session.resize(rows=40, cols=120)
    time.sleep(0.1)
    lines = echo_session.capture()
    assert len(lines) == 40
    assert all(len(line) == 120 for line in lines)


def test_session_close(echo_session):
    echo_session.close()
    assert not echo_session.is_alive()


def test_session_status_running(echo_session):
    status = echo_session.status()
    assert status["state"] == "running"
    assert "pid" in status


def test_session_status_exited(echo_session):
    echo_session.send_key("Ctrl-C")
    time.sleep(0.3)
    status = echo_session.status()
    assert status["state"] == "exited"


def test_session_wait_for_text(bash_session):
    found = bash_session.wait_for_text("READY$", timeout=5)
    assert found is True


def test_session_wait_for_text_timeout(echo_session):
    found = echo_session.wait_for_text("NEVER_APPEARS", timeout=0.5)
    assert found is False


def test_session_wait_for_absent(bash_session):
    bash_session.wait_for_text("READY$", timeout=5)
    absent = bash_session.wait_for_absent("READY$", timeout=0.5)
    assert absent is False


def test_session_wait_for_stable(echo_session):
    time.sleep(0.2)
    stable = echo_session.wait_for_stable(duration=0.3, timeout=2)
    assert stable is True


def test_session_snapshot_and_diff(bash_session):
    bash_session.wait_for_text("READY$", timeout=5)
    bash_session.save_snapshot("snap1")
    bash_session.type_text("echo changed")
    bash_session.send_key("Enter")
    time.sleep(0.3)
    diff = bash_session.diff_snapshot("snap1")
    assert len(diff) > 0


def test_session_scrollback(bash_session):
    bash_session.wait_for_text("READY$", timeout=5)
    bash_session.type_text("for i in $(seq 1 50); do echo line$i; done")
    bash_session.send_key("Enter")
    time.sleep(0.5)
    history = bash_session.scrollback(lines=30)
    assert isinstance(history, list)


def test_session_paste(echo_session):
    echo_session.paste("line1\nline2")
    time.sleep(0.2)
    lines = echo_session.capture()
    screen_text = "\n".join(lines)
    assert "line1" in screen_text


def test_session_mouse_click(echo_session):
    echo_session.mouse_click(row=0, col=0)


def test_session_mouse_scroll(echo_session):
    echo_session.mouse_scroll_up(row=0, col=0, lines=2)
    echo_session.mouse_scroll_down(row=0, col=0, lines=2)
