#!/usr/bin/env python3
"""
mdwiz-helper.py — sideband server for mdwiz.

Listens on a unix socket. mdwiz-mcp connects for two kinds of operations:

  1. prompt_request — shell_run hit an interactive prompt (password etc.).
     Helper pops `tmux display-popup -E` over the user's tmux session,
     runs mdwiz-pwprompt.sh to capture the input, and sends it back.
  2. stream_open / stream_close — shell_run is running with stream=True.
     Helper splits a tmux pane that `tail -F`'s the raw output log so the
     user sees progress while the inner PTY runs.

Protocol (newline-delimited JSON):
  prompt:
    client → helper:  {"op":"prompt_request","prompt":"...","cmd":"...","meta":{...}}
    helper → client:  {"value":"<entered text>"}            # success
    helper → client:  {"value":"","cancelled":true}         # cancelled
    helper → client:  {"value":"","error":"..."}            # internal error
  stream (fire-and-forget — helper does not respond):
    client → helper:  {"op":"stream_open","pid":N,"log_path":"...","title":"..."}
    client → helper:  {"op":"stream_close","pid":N,"log_path":"...","exit_code":N}
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PWPROMPT = HERE / "mdwiz-pwprompt.py"

# pid → tmux pane id, for stream_open/close lifecycle. Multiple shell_run
# 호출이 동시에 발생할 일은 단일 mcp 서버에서 거의 없지만 (tool dispatch 가
# 순차) handler thread 별로 dict 를 건드리므로 lock.
_panes: dict[int, str] = {}
_panes_lock = threading.Lock()


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


def open_stream_pane(session: str, req: dict) -> None:
    """tmux split-window 으로 위쪽 40% pane 띄워 tail -F 시작."""
    pid = req.get("pid")
    log_path = req.get("log_path")
    title = (req.get("title") or "").replace("'", "")[:60]
    if not (isinstance(pid, int) and log_path):
        log(f"stream_open: invalid req {req!r}")
        return

    # pane 안에서 실행할 셸 한 줄. exit 후 사용자가 read 키 누를 때까지 유지
    # (helper 가 stream_close 받았을 때 자동 닫을지 결정 — close handler 가
    #  exit_code=0 이면 kill-pane 으로 내림. read 는 fallback).
    banner = f"[mdwiz stream — {title}]" if title else "[mdwiz stream]"
    inner = (
        f"echo '{banner}'; "
        f"tail -F {shlex.quote(log_path)} 2>/dev/null; "
        f"echo; echo '[done — 아무 키나 눌러 닫기]'; "
        f"read -n1 -s"
    )

    # -v: vertical split (위/아래로 가름), -b: 새 pane 을 위쪽에, -l 40%: 새 pane 크기.
    # -d: 새 pane 으로 포커스 넘기지 않음 — 스트림 pane 은 표시 전용이고,
    #     사용자 입력 포커스는 chat pane(%0)에 그대로 남겨야 한다.
    # -P -F '#{pane_id}' 로 새 pane id 받음.
    try:
        out = subprocess.check_output(
            [
                "tmux", "split-window",
                "-t", f"{session}:0",
                "-v", "-b", "-d",
                "-l", "40%",
                "-P", "-F", "#{pane_id}",
                inner,
            ],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        log(f"stream_open: tmux split-window failed: {e.stderr.decode(errors='replace').strip()}")
        return

    pane_id = out.decode().strip()
    with _panes_lock:
        _panes[pid] = pane_id
    log(f"stream_open: pid={pid} pane={pane_id} log={log_path}")


def close_stream_pane(req: dict) -> None:
    """exit_code=0 이면 짧게 보여주고 kill-pane, 아니면 사용자 q 까지 유지."""
    pid = req.get("pid")
    log_path = req.get("log_path")
    exit_code = req.get("exit_code", -1)
    if not isinstance(pid, int):
        log(f"stream_close: invalid req {req!r}")
        return

    with _panes_lock:
        pane_id = _panes.pop(pid, None)

    def _finalize() -> None:
        # 0.5초 — tail -F 폴링이 마지막 chunk 를 보여줄 시간.
        time.sleep(0.5)
        if pane_id and exit_code == 0:
            subprocess.run(
                ["tmux", "kill-pane", "-t", pane_id],
                check=False,
                stderr=subprocess.DEVNULL,
            )
        # 로그 파일 unlink — pane 이 살아있어도 tail -F 는 inode 유지하고 있어 OK.
        if log_path:
            try:
                os.unlink(log_path)
            except FileNotFoundError:
                pass
            except OSError as e:
                log(f"stream_close: unlink {log_path} failed: {e}")

    threading.Thread(target=_finalize, daemon=True).start()
    log(f"stream_close: pid={pid} exit={exit_code} pane={pane_id or '(none)'}"
        f"{' — auto-close' if exit_code == 0 else ' — keep-open'}")


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
        op = req.get("op", "prompt_request")

        if op == "stream_open":
            open_stream_pane(session, req)
            return  # fire-and-forget, no response

        if op == "stream_close":
            close_stream_pane(req)
            return  # fire-and-forget, no response

        # default: prompt_request
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


def _cleanup_stream_logs() -> None:
    """비정상 종료로 남은 /tmp/mdwiz-stream-*.log 잔재를 지운다.
    O_CREAT 로 helper 가 만든 게 아니라 mcp 가 만든 것이므로, 권한 없는
    (타 user) 파일은 unlink 가 자연스레 실패 — 무시."""
    for f in glob.glob("/tmp/mdwiz-stream-*.log"):
        try:
            os.unlink(f)
        except OSError:
            pass


def serve(socket_path: str, session: str) -> None:
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    os.chmod(socket_path, 0o600)
    srv.listen(8)
    _cleanup_stream_logs()
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
        _cleanup_stream_logs()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", required=True)
    ap.add_argument("--session", required=True)
    args = ap.parse_args()
    serve(args.socket, args.session)
