#!/usr/bin/env python3
"""
mdwiz-helper.py — sideband server for mdwiz.

Listens on a unix socket. When mdwiz-mcp's shell_run hits an interactive
prompt (e.g. git password) inside its inner PTY, it connects, sends a JSON
request, and blocks for a JSON response. This helper handles each request
by popping `tmux display-popup -E` over the user's tmux session, running
mdwiz-pwprompt.sh to capture the input.

Protocol (newline-delimited JSON):
  client → helper:  {"op":"prompt_request","prompt":"...","cmd":"...","meta":{...}}
  helper → client:  {"value":"<entered text>"}            # success
  helper → client:  {"value":"","cancelled":true}         # cancelled
  helper → client:  {"value":"","error":"..."}            # internal error
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


HERE = Path(__file__).resolve().parent
PWPROMPT = HERE / "mdwiz-pwprompt.py"


def log(msg: str) -> None:
    print(f"[mdwiz-helper] {msg}", file=sys.stderr, flush=True)


def show_popup(session: str, req: dict) -> dict:
    """Pop wizard-pwprompt.sh over the tmux session, return {value, cancelled?}."""
    meta_fd, meta_path = tempfile.mkstemp(suffix=".json", prefix="mdwiz-meta-")
    res_fd, res_path = tempfile.mkstemp(suffix=".txt", prefix="mdwiz-res-")
    os.close(meta_fd)
    os.close(res_fd)
    try:
        with open(meta_path, "w") as f:
            json.dump(
                {
                    "prompt": req.get("prompt", "Password:"),
                    "cmd": req.get("cmd", ""),
                    "meta": req.get("meta", {}),
                },
                f,
            )

        # 같은 python 으로 popup 도 실행 (helper 가 쓰는 Python = sys.executable)
        result = subprocess.run(
            [
                "tmux", "display-popup",
                "-t", session,
                "-E",
                "-w", "70",
                "-h", "12",
                "-T", " mdwiz 입력 요청 ",
                sys.executable, str(PWPROMPT), meta_path, res_path,
            ],
            check=False,
        )
        cancelled = result.returncode == 130

        try:
            with open(res_path, "r") as f:
                value = f.read()
        except Exception:
            value = ""

        return {"value": value, "cancelled": cancelled}
    finally:
        for p in (meta_path, res_path):
            try:
                os.unlink(p)
            except Exception:
                pass


def handle_client(conn: socket.socket, session: str) -> None:
    try:
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
        line, _ = buf.split(b"\n", 1)
        req = json.loads(line)
        log(f"prompt_request from cmd={req.get('cmd','?')[:40]!r}")
        resp = show_popup(session, req)
        conn.sendall(json.dumps(resp).encode() + b"\n")
        log(f"responded ({'cancelled' if resp['cancelled'] else 'ok'})")
    except Exception as e:
        log(f"handler error: {e}")
        try:
            conn.sendall(json.dumps({"value": "", "error": str(e)}).encode() + b"\n")
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def serve(socket_path: str, session: str) -> None:
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    os.chmod(socket_path, 0o600)
    srv.listen(8)
    log(f"listening on {socket_path} (session={session})")

    try:
        while True:
            conn, _ = srv.accept()
            threading.Thread(
                target=handle_client, args=(conn, session), daemon=True
            ).start()
    except KeyboardInterrupt:
        log("shutdown (SIGINT)")
    finally:
        try:
            os.unlink(socket_path)
        except Exception:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", required=True)
    ap.add_argument("--session", required=True)
    args = ap.parse_args()
    serve(args.socket, args.session)
