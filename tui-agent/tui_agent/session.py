"""Session: wraps a PTY child process with a pyte virtual terminal screen."""

import os
import threading
import time
from typing import Any

import pexpect
import pyte

from tui_agent.keys import resolve_key
from tui_agent.mouse import (
    mouse_click as _mouse_click_seq,
    mouse_scroll_up as _mouse_scroll_up_seq,
    mouse_scroll_down as _mouse_scroll_down_seq,
)


class Session:
    """A single TUI session: one PTY process + one pyte virtual screen."""

    def __init__(
        self,
        name: str,
        cmd: list[str],
        cols: int = 80,
        rows: int = 24,
        history: int = 1000,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ):
        self.name = name
        self.cmd = cmd
        self._cols = cols
        self._rows = rows
        self._snapshots: dict[str, list[str]] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

        # pyte virtual terminal
        self._screen = pyte.HistoryScreen(cols, rows, history=history)
        self._stream = pyte.ByteStream(self._screen)

        # Spawn child process with PTY
        spawn_env = os.environ.copy()
        if env:
            spawn_env.update(env)
        spawn_env["TERM"] = "xterm-256color"

        self._child = pexpect.spawn(
            cmd[0],
            args=cmd[1:],
            dimensions=(rows, cols),
            env=spawn_env,
            encoding=None,  # bytes mode
            cwd=cwd,
        )

        # Background reader thread
        self._stop_event = threading.Event()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Continuously read PTY output and feed to pyte screen."""
        while not self._stop_event.is_set():
            try:
                data = self._child.read_nonblocking(size=4096, timeout=0.1)
                if data:
                    with self._lock:
                        self._stream.feed(data)
            except pexpect.TIMEOUT:
                continue
            except pexpect.EOF:
                break
            except Exception:
                break

    @property
    def pid(self) -> int:
        return self._child.pid

    def is_alive(self) -> bool:
        return self._child.isalive()

    def status(self) -> dict[str, Any]:
        if self.is_alive():
            return {
                "state": "running",
                "pid": self.pid,
                "cmd": self.cmd,
                "uptime": time.time() - self._start_time,
                "size": f"{self._cols}x{self._rows}",
            }
        return {
            "state": "exited",
            "pid": self.pid,
            "cmd": self.cmd,
            "exit_code": self._child.exitstatus,
            "signal": self._child.signalstatus,
        }

    def capture(self) -> list[str]:
        """Return the current screen content as a list of strings."""
        with self._lock:
            return list(self._screen.display)

    def capture_region(
        self, top: int, left: int, height: int, width: int
    ) -> list[str]:
        """Return a rectangular region of the screen."""
        with self._lock:
            lines = self._screen.display
        result = []
        for row_idx in range(top, min(top + height, len(lines))):
            line = lines[row_idx]
            result.append(line[left : left + width])
        return result

    def cursor_position(self) -> tuple[int, int]:
        """Return (row, col) of the cursor."""
        with self._lock:
            return (self._screen.cursor.y, self._screen.cursor.x)

    def type_text(self, text: str) -> None:
        """Send raw text to the PTY."""
        self._child.send(text.encode("utf-8"))

    def send_key(self, key_name: str) -> None:
        """Send a named key to the PTY."""
        seq = resolve_key(key_name)
        self._child.send(seq.encode("utf-8"))

    def paste(self, text: str) -> None:
        """Send text using bracketed paste mode."""
        bracket_start = "\x1b[200~"
        bracket_end = "\x1b[201~"
        payload = bracket_start + text + bracket_end
        self._child.send(payload.encode("utf-8"))

    def mouse_click(self, row: int, col: int) -> None:
        seq = _mouse_click_seq(row=row, col=col)
        self._child.send(seq.encode("utf-8"))

    def mouse_scroll_up(self, row: int, col: int, lines: int = 1) -> None:
        seq = _mouse_scroll_up_seq(row=row, col=col, lines=lines)
        self._child.send(seq.encode("utf-8"))

    def mouse_scroll_down(self, row: int, col: int, lines: int = 1) -> None:
        seq = _mouse_scroll_down_seq(row=row, col=col, lines=lines)
        self._child.send(seq.encode("utf-8"))

    def resize(self, rows: int, cols: int) -> None:
        """Resize the PTY and the virtual screen."""
        self._cols = cols
        self._rows = rows
        self._child.setwinsize(rows, cols)
        with self._lock:
            self._screen.resize(lines=rows, columns=cols)

    def wait_for_text(self, text: str, timeout: float = 10) -> bool:
        """Poll the screen until the given text appears."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.capture()
            screen_text = "\n".join(lines)
            if text in screen_text:
                return True
            time.sleep(0.1)
        return False

    def wait_for_absent(self, text: str, timeout: float = 10) -> bool:
        """Poll the screen until the given text disappears."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.capture()
            screen_text = "\n".join(lines)
            if text not in screen_text:
                return True
            time.sleep(0.1)
        return False

    def wait_for_stable(self, duration: float = 2, timeout: float = 10) -> bool:
        """Wait until the screen content stays unchanged for `duration` seconds."""
        deadline = time.time() + timeout
        prev = self.capture()
        stable_since = time.time()
        while time.time() < deadline:
            time.sleep(0.1)
            curr = self.capture()
            if curr != prev:
                prev = curr
                stable_since = time.time()
            elif time.time() - stable_since >= duration:
                return True
        return False

    def save_snapshot(self, name: str) -> None:
        self._snapshots[name] = self.capture()

    def diff_snapshot(self, name: str) -> list[str]:
        old = self._snapshots.get(name)
        if old is None:
            raise ValueError(f"Snapshot {name!r} not found")
        current = self.capture()
        diffs = []
        for i, (old_line, new_line) in enumerate(zip(old, current)):
            if old_line != new_line:
                diffs.append(f"line {i}: -{old_line.rstrip()}")
                diffs.append(f"line {i}: +{new_line.rstrip()}")
        return diffs

    def scrollback(self, lines: int = 100) -> list[str]:
        """Return lines from the scroll-back history buffer."""
        with self._lock:
            history_top = list(self._screen.history.top)
        result = []
        for history_line in history_top[-lines:]:
            chars = []
            if hasattr(history_line, "items"):
                max_col = max(history_line.keys()) if history_line else 0
                for c in range(max_col + 1):
                    char = history_line.get(c)
                    chars.append(char.data if char else " ")
            else:
                chars = [c.data for c in history_line]
            result.append("".join(chars))
        return result

    def close(self) -> None:
        """Stop the reader thread and terminate the child process."""
        self._stop_event.set()
        if self._child.isalive():
            self._child.terminate(force=True)
        self._reader_thread.join(timeout=2)
