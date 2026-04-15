import subprocess
import threading
import time
import sys

import pytest

from tui_agent.daemon import Daemon


_cli_counter = 0


@pytest.fixture
def daemon_with_path(tmp_path):
    # Use short path to avoid macOS 104-byte AF_UNIX limit
    import tempfile, os
    global _cli_counter
    _cli_counter += 1
    sock_path = os.path.join(tempfile.gettempdir(), f"tui-cli-{os.getpid()}-{_cli_counter}.sock")
    d = Daemon(socket_path=sock_path)
    t = threading.Thread(target=d.serve, daemon=True)
    t.start()
    time.sleep(0.3)
    yield sock_path
    d.shutdown()
    if os.path.exists(sock_path):
        os.unlink(sock_path)


def _run_cli(sock_path: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tui_agent.cli", "--socket", sock_path] + args,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_cli_start(daemon_with_path):
    result = _run_cli(daemon_with_path, ["start", "--name", "clitest", "--", "/bin/cat"])
    assert result.returncode == 0
    assert "started" in result.stdout.lower() or "pid" in result.stdout.lower()


def test_cli_list(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "l1", "--", "/bin/cat"])
    result = _run_cli(daemon_with_path, ["list"])
    assert result.returncode == 0
    assert "l1" in result.stdout


def test_cli_capture(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "cap", "--", "/bin/cat"])
    time.sleep(0.2)
    result = _run_cli(daemon_with_path, ["capture", "--name", "cap"])
    assert result.returncode == 0


def test_cli_type_and_key(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "tk", "--", "/bin/cat"])
    _run_cli(daemon_with_path, ["type", "--name", "tk", "hello"])
    result = _run_cli(daemon_with_path, ["key", "--name", "tk", "Enter"])
    assert result.returncode == 0


def test_cli_status(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "st", "--", "/bin/cat"])
    result = _run_cli(daemon_with_path, ["status", "--name", "st"])
    assert result.returncode == 0
    assert "running" in result.stdout.lower()


def test_cli_stop(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "stp", "--", "/bin/cat"])
    result = _run_cli(daemon_with_path, ["stop", "--name", "stp"])
    assert result.returncode == 0


def test_cli_stop_all(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "a1", "--", "/bin/cat"])
    result = _run_cli(daemon_with_path, ["stop", "--all"])
    assert result.returncode == 0


def test_cli_wait_timeout(daemon_with_path):
    _run_cli(daemon_with_path, ["start", "--name", "wt", "--", "/bin/cat"])
    result = _run_cli(daemon_with_path, [
        "wait", "--name", "wt", "--text", "NEVER", "--timeout", "1",
    ])
    assert result.returncode == 1
