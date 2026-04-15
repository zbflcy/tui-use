"""Unix Socket daemon: manages TUI sessions and handles CLI requests."""

import json
import os
import socket
import threading
from typing import Any

from tui_agent.protocol import (
    decode_request,
    encode_response,
    ok_response,
    error_response,
    get_socket_path,
)
from tui_agent.session import Session


class Daemon:
    def __init__(self, socket_path: str | None = None):
        self._socket_path = socket_path or get_socket_path()
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._server: socket.socket | None = None
        self._running = False

    def serve(self) -> None:
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self._socket_path)
        self._server.listen(5)
        self._server.settimeout(1.0)
        self._running = True
        try:
            while self._running:
                try:
                    conn, _ = self._server.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
        finally:
            self._server.close()
            if os.path.exists(self._socket_path):
                os.unlink(self._socket_path)

    def shutdown(self) -> None:
        self._running = False
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk
            req = decode_request(buf)
            resp = self._dispatch(req)
            conn.sendall(encode_response(resp))
        except Exception as e:
            try:
                conn.sendall(encode_response(error_response(str(e))))
            except Exception:
                pass
        finally:
            conn.close()

    def _dispatch(self, req: dict[str, Any]) -> dict[str, Any]:
        action = req.get("action", "")
        handlers = {
            "start": self._handle_start,
            "stop": self._handle_stop,
            "stop-all": self._handle_stop_all,
            "list": self._handle_list,
            "status": self._handle_status,
            "capture": self._handle_capture,
            "scrollback": self._handle_scrollback,
            "type": self._handle_type,
            "key": self._handle_key,
            "paste": self._handle_paste,
            "click": self._handle_click,
            "scroll-up": self._handle_scroll_up,
            "scroll-down": self._handle_scroll_down,
            "wait": self._handle_wait,
            "resize": self._handle_resize,
            "snapshot": self._handle_snapshot,
            "diff": self._handle_diff,
        }
        handler = handlers.get(action)
        if not handler:
            return error_response(f"Unknown action: {action!r}")
        return handler(req)

    def _get_session(self, req: dict[str, Any]) -> Session:
        name = req.get("name", "")
        with self._lock:
            session = self._sessions.get(name)
        if session is None:
            raise KeyError(f"Session {name!r} not found")
        return session

    def _handle_start(self, req):
        name = req["name"]
        with self._lock:
            if name in self._sessions:
                return error_response(f"Session {name!r} already exists")
        cmd = req["cmd"]
        cols = req.get("cols", 80)
        rows = req.get("rows", 24)
        cwd = req.get("cwd")
        session = Session(name=name, cmd=cmd, cols=cols, rows=rows, cwd=cwd)
        with self._lock:
            self._sessions[name] = session
        return ok_response({"pid": session.pid})

    def _handle_stop(self, req):
        name = req.get("name", "")
        with self._lock:
            session = self._sessions.pop(name, None)
        if session is None:
            return error_response(f"Session {name!r} not found")
        session.close()
        return ok_response()

    def _handle_stop_all(self, req):
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            s.close()
        return ok_response({"stopped": len(sessions)})

    def _handle_list(self, req):
        with self._lock:
            sessions = list(self._sessions.values())
        result = []
        for s in sessions:
            st = s.status()
            st["name"] = s.name
            result.append(st)
        return ok_response({"sessions": result})

    def _handle_status(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        return ok_response(session.status())

    def _handle_capture(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        top = req.get("top")
        if top is not None:
            lines = session.capture_region(top=top, left=req.get("left", 0), height=req.get("height", 24), width=req.get("width", 80))
        else:
            lines = session.capture()
        data: dict[str, Any] = {"screen": "\n".join(lines)}
        if req.get("cursor"):
            row, col = session.cursor_position()
            data["cursor"] = {"row": row, "col": col}
        if req.get("save"):
            session.save_snapshot(req["save"])
        return ok_response(data)

    def _handle_scrollback(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        lines = session.scrollback(lines=req.get("lines", 100))
        return ok_response({"lines": lines})

    def _handle_type(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.type_text(req["text"])
        if req.get("enter"):
            session.send_key("Enter")
        return ok_response()

    def _handle_key(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        for key_name in req["keys"]:
            session.send_key(key_name)
        return ok_response()

    def _handle_paste(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.paste(req["text"])
        return ok_response()

    def _handle_click(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.mouse_click(row=req["row"], col=req["col"])
        return ok_response()

    def _handle_scroll_up(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.mouse_scroll_up(row=req["row"], col=req["col"], lines=req.get("lines", 3))
        return ok_response()

    def _handle_scroll_down(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.mouse_scroll_down(row=req["row"], col=req["col"], lines=req.get("lines", 3))
        return ok_response()

    def _handle_wait(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        timeout = req.get("timeout", 10)
        if req.get("stable") is not None:
            ok = session.wait_for_stable(duration=req["stable"], timeout=timeout)
        elif req.get("absent"):
            ok = session.wait_for_absent(req["text"], timeout=timeout)
        else:
            ok = session.wait_for_text(req["text"], timeout=timeout)
        if ok:
            return ok_response()
        return error_response(f"Timeout after {timeout}s")

    def _handle_resize(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.resize(rows=req["rows"], cols=req["cols"])
        return ok_response()

    def _handle_snapshot(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        session.save_snapshot(req["snapshot_name"])
        return ok_response()

    def _handle_diff(self, req):
        try:
            session = self._get_session(req)
        except KeyError as e:
            return error_response(str(e))
        try:
            diffs = session.diff_snapshot(req["snapshot"])
            return ok_response({"diff": diffs})
        except ValueError as e:
            return error_response(str(e))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default=None)
    args = parser.parse_args()
    d = Daemon(socket_path=args.socket)
    d.serve()
