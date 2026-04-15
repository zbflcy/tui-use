import json
import os
import socket
import threading
import time

import pytest

from tui_agent.daemon import Daemon
from tui_agent.protocol import encode_request, decode_response


@pytest.fixture
def daemon_instance(tmp_path):
    # macOS limits AF_UNIX paths to 104 bytes; use /tmp for a short path
    import tempfile
    short_dir = tempfile.mkdtemp(prefix="tui-", dir="/tmp")
    sock_path = os.path.join(short_dir, "t.sock")
    d = Daemon(socket_path=sock_path)
    t = threading.Thread(target=d.serve, daemon=True)
    t.start()
    time.sleep(0.2)
    yield d, sock_path
    d.shutdown()
    import shutil
    shutil.rmtree(short_dir, ignore_errors=True)


def _send_request(sock_path: str, req: dict) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(sock_path)
    client.sendall(encode_request(req))
    buf = b""
    while b"\n" not in buf:
        chunk = client.recv(4096)
        if not chunk:
            break
        buf += chunk
    client.close()
    return decode_response(buf)


def test_start_session(daemon_instance):
    d, sock_path = daemon_instance
    resp = _send_request(sock_path, {
        "action": "start", "name": "testcat", "cmd": ["/bin/cat"], "cols": 80, "rows": 24,
    })
    assert resp["ok"] is True
    assert "pid" in resp["data"]


def test_start_duplicate_name(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "dup", "cmd": ["/bin/cat"]})
    resp = _send_request(sock_path, {"action": "start", "name": "dup", "cmd": ["/bin/cat"]})
    assert resp["ok"] is False
    assert "already exists" in resp["error"]


def test_capture(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "cap", "cmd": ["/bin/cat"]})
    time.sleep(0.2)
    resp = _send_request(sock_path, {"action": "capture", "name": "cap"})
    assert resp["ok"] is True
    assert "screen" in resp["data"]
    assert isinstance(resp["data"]["screen"], str)


def test_capture_with_cursor(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "cur", "cmd": ["/bin/cat"]})
    time.sleep(0.2)
    resp = _send_request(sock_path, {"action": "capture", "name": "cur", "cursor": True})
    assert resp["ok"] is True
    assert "cursor" in resp["data"]
    assert "row" in resp["data"]["cursor"]
    assert "col" in resp["data"]["cursor"]


def test_type_text(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "typ", "cmd": ["/bin/cat"]})
    _send_request(sock_path, {"action": "type", "name": "typ", "text": "hello"})
    _send_request(sock_path, {"action": "key", "name": "typ", "keys": ["Enter"]})
    time.sleep(0.3)
    resp = _send_request(sock_path, {"action": "capture", "name": "typ"})
    assert "hello" in resp["data"]["screen"]


def test_status(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "st", "cmd": ["/bin/cat"]})
    resp = _send_request(sock_path, {"action": "status", "name": "st"})
    assert resp["ok"] is True
    assert resp["data"]["state"] == "running"


def test_list_sessions(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "s1", "cmd": ["/bin/cat"]})
    _send_request(sock_path, {"action": "start", "name": "s2", "cmd": ["/bin/cat"]})
    resp = _send_request(sock_path, {"action": "list"})
    assert resp["ok"] is True
    names = [s["name"] for s in resp["data"]["sessions"]]
    assert "s1" in names
    assert "s2" in names


def test_stop_session(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "stp", "cmd": ["/bin/cat"]})
    resp = _send_request(sock_path, {"action": "stop", "name": "stp"})
    assert resp["ok"] is True
    resp = _send_request(sock_path, {"action": "status", "name": "stp"})
    assert resp["ok"] is False


def test_stop_all(daemon_instance):
    d, sock_path = daemon_instance
    _send_request(sock_path, {"action": "start", "name": "a1", "cmd": ["/bin/cat"]})
    _send_request(sock_path, {"action": "start", "name": "a2", "cmd": ["/bin/cat"]})
    resp = _send_request(sock_path, {"action": "stop-all"})
    assert resp["ok"] is True
    resp = _send_request(sock_path, {"action": "list"})
    assert len(resp["data"]["sessions"]) == 0


def test_unknown_action(daemon_instance):
    d, sock_path = daemon_instance
    resp = _send_request(sock_path, {"action": "nonexistent"})
    assert resp["ok"] is False
    assert "Unknown action" in resp["error"]


def test_session_not_found(daemon_instance):
    d, sock_path = daemon_instance
    resp = _send_request(sock_path, {"action": "capture", "name": "nope"})
    assert resp["ok"] is False
    assert "not found" in resp["error"]
