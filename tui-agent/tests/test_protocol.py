import json
from tui_agent.protocol import (
    encode_request,
    decode_request,
    encode_response,
    decode_response,
    ok_response,
    error_response,
    get_socket_path,
)


def test_encode_decode_request():
    req = {"action": "capture", "name": "myapp", "cursor": True}
    raw = encode_request(req)
    assert isinstance(raw, bytes)
    assert raw.endswith(b"\n")
    decoded = decode_request(raw)
    assert decoded == req


def test_encode_decode_response():
    resp = {"ok": True, "data": {"screen": "hello"}}
    raw = encode_response(resp)
    assert isinstance(raw, bytes)
    assert raw.endswith(b"\n")
    decoded = decode_response(raw)
    assert decoded == resp


def test_ok_response():
    resp = ok_response({"pid": 123})
    assert resp == {"ok": True, "data": {"pid": 123}}


def test_ok_response_no_data():
    resp = ok_response()
    assert resp == {"ok": True, "data": None}


def test_error_response():
    resp = error_response("session not found")
    assert resp == {"ok": False, "error": "session not found"}


def test_socket_path_contains_tmp():
    path = get_socket_path()
    assert "tui-agent" in path
