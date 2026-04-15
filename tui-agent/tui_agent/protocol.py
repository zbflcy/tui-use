"""JSON-over-Unix-Socket protocol: one request → one response per connection."""

import json
import os
import tempfile
from typing import Any


def get_socket_path() -> str:
    """Return the Unix socket path for the daemon."""
    return os.path.join(tempfile.gettempdir(), f"tui-agent-{os.getuid()}.sock")


def encode_request(req: dict[str, Any]) -> bytes:
    """Encode a request dict to newline-terminated JSON bytes."""
    return json.dumps(req, separators=(",", ":")).encode("utf-8") + b"\n"


def decode_request(raw: bytes) -> dict[str, Any]:
    """Decode newline-terminated JSON bytes to a request dict."""
    return json.loads(raw.strip())


def encode_response(resp: dict[str, Any]) -> bytes:
    """Encode a response dict to newline-terminated JSON bytes."""
    return json.dumps(resp, separators=(",", ":")).encode("utf-8") + b"\n"


def decode_response(raw: bytes) -> dict[str, Any]:
    """Decode newline-terminated JSON bytes to a response dict."""
    return json.loads(raw.strip())


def ok_response(data: Any = None) -> dict[str, Any]:
    """Build a success response."""
    return {"ok": True, "data": data}


def error_response(message: str) -> dict[str, Any]:
    """Build an error response."""
    return {"ok": False, "error": message}
