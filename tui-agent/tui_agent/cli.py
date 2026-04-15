"""CLI entry point: parses commands, sends requests to daemon via Unix socket."""

import json
import os
import socket
import subprocess
import sys
import time

import click

from tui_agent.protocol import (
    encode_request,
    decode_response,
    get_socket_path,
)


def _send(sock_path: str, req: dict, timeout: float = 30) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(sock_path)
    client.sendall(encode_request(req))
    buf = b""
    while b"\n" not in buf:
        chunk = client.recv(65536)
        if not chunk:
            break
        buf += chunk
    client.close()
    return decode_response(buf)


def _ensure_daemon(sock_path: str) -> None:
    if os.path.exists(sock_path):
        try:
            test = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test.connect(sock_path)
            test.close()
            return
        except (ConnectionRefusedError, FileNotFoundError):
            os.unlink(sock_path)
    subprocess.Popen(
        [sys.executable, "-m", "tui_agent.daemon", "--socket", sock_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(30):
        time.sleep(0.1)
        if os.path.exists(sock_path):
            try:
                test = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                test.connect(sock_path)
                test.close()
                return
            except (ConnectionRefusedError, FileNotFoundError):
                continue
    click.echo("Error: daemon failed to start", err=True)
    sys.exit(1)


@click.group()
@click.option("--socket", "sock_path", default=None, help="Unix socket path")
@click.pass_context
def main(ctx: click.Context, sock_path: str | None) -> None:
    """tui-agent: interact with TUI programs from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["sock_path"] = sock_path or get_socket_path()


@main.command()
@click.option("--name", required=True, help="Session name")
@click.option("--cols", default=80, help="Terminal columns")
@click.option("--rows", default=24, help="Terminal rows")
@click.argument("cmd", nargs=-1, required=True)
@click.pass_context
def start(ctx, name, cols, rows, cmd):
    """Start a TUI session."""
    sock_path = ctx.obj["sock_path"]
    _ensure_daemon(sock_path)
    resp = _send(sock_path, {"action": "start", "name": name, "cmd": list(cmd), "cols": cols, "rows": rows, "cwd": os.getcwd()})
    if resp["ok"]:
        click.echo(f'session "{name}" started (pid: {resp["data"]["pid"]})')
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command("list")
@click.pass_context
def list_sessions(ctx):
    """List all active sessions."""
    sock_path = ctx.obj["sock_path"]
    _ensure_daemon(sock_path)
    resp = _send(sock_path, {"action": "list"})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)
    sessions = resp["data"]["sessions"]
    if not sessions:
        click.echo("No active sessions")
        return
    click.echo(f"{'NAME':<16} {'PID':<8} {'SIZE':<10} {'STATE':<10} {'CMD'}")
    for s in sessions:
        cmd_str = " ".join(s.get("cmd", []))
        click.echo(f"{s['name']:<16} {s.get('pid','?'):<8} {s.get('size','?'):<10} {s['state']:<10} {cmd_str}")


@main.command()
@click.option("--name", required=True)
@click.pass_context
def status(ctx, name):
    """Check session process status."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "status", "name": name})
    if resp["ok"]:
        d = resp["data"]
        if d["state"] == "running":
            click.echo(f"running (pid: {d['pid']})")
        else:
            click.echo(f"exited (code: {d.get('exit_code')}, signal: {d.get('signal')})")
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.option("--cursor", is_flag=True)
@click.option("--save", default=None)
@click.option("--top", default=None, type=int)
@click.option("--left", default=None, type=int)
@click.option("--height", default=None, type=int)
@click.option("--width", default=None, type=int)
@click.pass_context
def capture(ctx, name, cursor, save, top, left, height, width):
    """Capture the current screen content."""
    sock_path = ctx.obj["sock_path"]
    req = {"action": "capture", "name": name}
    if cursor:
        req["cursor"] = True
    if save:
        req["save"] = save
    if top is not None:
        req["top"] = top
        req["left"] = left or 0
        req["height"] = height or 24
        req["width"] = width or 80
    resp = _send(sock_path, req)
    if resp["ok"]:
        click.echo(resp["data"]["screen"])
        if cursor and "cursor" in resp["data"]:
            c = resp["data"]["cursor"]
            click.echo(f"[cursor: row={c['row']}, col={c['col']}]")
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.option("--lines", default=100)
@click.pass_context
def scrollback(ctx, name, lines):
    """Read scrollback history buffer."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "scrollback", "name": name, "lines": lines})
    if resp["ok"]:
        for line in resp["data"]["lines"]:
            click.echo(line)
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command("type")
@click.option("--name", required=True)
@click.option("--enter", is_flag=True)
@click.argument("text")
@click.pass_context
def type_text(ctx, name, enter, text):
    """Type text into the session."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "type", "name": name, "text": text, "enter": enter})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.argument("keys", nargs=-1, required=True)
@click.pass_context
def key(ctx, name, keys):
    """Send special keys (Enter, Tab, Ctrl-C, Up, etc.)."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "key", "name": name, "keys": list(keys)})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.argument("text")
@click.pass_context
def paste(ctx, name, text):
    """Paste text using bracketed paste mode."""
    sock_path = ctx.obj["sock_path"]
    text = text.encode("utf-8").decode("unicode_escape")
    resp = _send(sock_path, {"action": "paste", "name": name, "text": text})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command("click")
@click.option("--name", required=True)
@click.option("--row", required=True, type=int)
@click.option("--col", required=True, type=int)
@click.pass_context
def click_cmd(ctx, name, row, col):
    """Send a mouse click."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "click", "name": name, "row": row, "col": col})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command("scroll-up")
@click.option("--name", required=True)
@click.option("--row", required=True, type=int)
@click.option("--col", required=True, type=int)
@click.option("--lines", default=3, type=int)
@click.pass_context
def scroll_up(ctx, name, row, col, lines):
    """Send mouse scroll-up events."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "scroll-up", "name": name, "row": row, "col": col, "lines": lines})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command("scroll-down")
@click.option("--name", required=True)
@click.option("--row", required=True, type=int)
@click.option("--col", required=True, type=int)
@click.option("--lines", default=3, type=int)
@click.pass_context
def scroll_down(ctx, name, row, col, lines):
    """Send mouse scroll-down events."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "scroll-down", "name": name, "row": row, "col": col, "lines": lines})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.option("--text", default=None)
@click.option("--absent", is_flag=True)
@click.option("--stable", default=None, type=float)
@click.option("--timeout", default=10, type=float)
@click.pass_context
def wait(ctx, name, text, absent, stable, timeout):
    """Wait for screen content condition."""
    sock_path = ctx.obj["sock_path"]
    req = {"action": "wait", "name": name, "timeout": timeout}
    if stable is not None:
        req["stable"] = stable
    elif text:
        req["text"] = text
        if absent:
            req["absent"] = True
    else:
        click.echo("Error: must specify --text or --stable", err=True)
        sys.exit(1)
    resp = _send(sock_path, req, timeout=timeout + 5)
    if resp["ok"]:
        click.echo("OK")
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.option("--cols", required=True, type=int)
@click.option("--rows", required=True, type=int)
@click.pass_context
def resize(ctx, name, cols, rows):
    """Resize the terminal."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "resize", "name": name, "cols": cols, "rows": rows})
    if not resp["ok"]:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", required=True)
@click.option("--snapshot", required=True)
@click.pass_context
def diff(ctx, name, snapshot):
    """Show diff between current screen and a saved snapshot."""
    sock_path = ctx.obj["sock_path"]
    resp = _send(sock_path, {"action": "diff", "name": name, "snapshot": snapshot})
    if resp["ok"]:
        for line in resp["data"]["diff"]:
            click.echo(line)
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


@main.command()
@click.option("--name", default=None)
@click.option("--all", "stop_all", is_flag=True)
@click.pass_context
def stop(ctx, name, stop_all):
    """Stop a session or all sessions."""
    sock_path = ctx.obj["sock_path"]
    if stop_all:
        resp = _send(sock_path, {"action": "stop-all"})
    elif name:
        resp = _send(sock_path, {"action": "stop", "name": name})
    else:
        click.echo("Error: must specify --name or --all", err=True)
        sys.exit(1)
    if resp["ok"]:
        click.echo("OK")
    else:
        click.echo(f"Error: {resp['error']}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
