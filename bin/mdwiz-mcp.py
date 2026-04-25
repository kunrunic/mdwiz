#!/usr/bin/env python3
"""
mdwiz-mcp: stdio MCP server for the mdwiz interactive runner.

Generic tools for running shell + file ops within a project root, paired
with a sideband socket for interactive prompts (passwords, confirmations)
that pop up via tmux display-popup.

Tools exposed to Claude:
  shell_run(cmd, cwd?, env?, prompt_patterns?, timeout_sec?, tail_lines?)
                          run cmd in a PTY, capture output, surface prompts
  fs_read(path)           read file (or list dir) within read whitelist
  fs_write(path, content) write file within write whitelist (idempotent)
  progress(stage, ...)    notify progress (stderr log; future: TUI hook)

Required env:
  MDWIZ_ROOT              project root — also default cwd + read whitelist
                          base. fs_read / shell_run cwd default here.

Optional env:
  MDWIZ_READ_GLOBS        colon-separated extra read paths (in addition to
                          MDWIZ_ROOT/**). Globs allowed.
                          Example: "/tmp/report-*.md:/etc/myapp/**"
  MDWIZ_WRITE_GLOBS       comma-separated glob patterns under MDWIZ_ROOT
                          allowed for fs_write. EMPTY (default) = fs_write
                          disabled (read-only mode).
                          Example: "manifests/*.yaml,scripts/*.sh"
  MDWIZ_SOCKET            sideband socket path. When set, shell_run on prompt
                          match calls the helper instead of killing the cmd.
"""

from __future__ import annotations

import fcntl
import fnmatch
import json
import os
import pty
import re
import select
import signal
import socket as _socket
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# config (env-driven, no project-specific hardcoded paths)
# ---------------------------------------------------------------------------

ROOT_RAW = os.environ.get("MDWIZ_ROOT")
if not ROOT_RAW:
    print("[mdwiz-mcp] FATAL: MDWIZ_ROOT not set", file=sys.stderr, flush=True)
    sys.exit(2)
ROOT = Path(ROOT_RAW).resolve()
if not ROOT.is_dir():
    print(f"[mdwiz-mcp] FATAL: MDWIZ_ROOT is not a directory: {ROOT}", file=sys.stderr)
    sys.exit(2)

READ_EXTRAS = [
    Path(p).expanduser() for p in os.environ.get("MDWIZ_READ_GLOBS", "").split(":") if p
]
WRITE_GLOBS = [
    g.strip() for g in os.environ.get("MDWIZ_WRITE_GLOBS", "").split(",") if g.strip()
]
SOCKET = os.environ.get("MDWIZ_SOCKET")

DEFAULT_PROMPT_PATTERNS: list[str] = [
    r"[Pp]assword[^:]*:\s*$",
    r"[Pp]assphrase[^:]*:\s*$",
    r"Username for [^:]+:\s*$",
]

mcp = FastMCP("mdwiz")


def _log(msg: str) -> None:
    print(f"[mdwiz-mcp] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# path whitelist
# ---------------------------------------------------------------------------

def _path_under(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_readable(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if _path_under(p, ROOT):
        return p
    for extra in READ_EXTRAS:
        # extra may be a literal path or a glob. If it has glob chars, match;
        # otherwise treat as a directory whose subtree is allowed.
        s_extra = str(extra)
        if any(c in s_extra for c in "*?["):
            if fnmatch.fnmatch(str(p), s_extra):
                return p
        else:
            if _path_under(p, extra):
                return p
    raise PermissionError(f"path not in read whitelist: {path}")


def _check_writable(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not _path_under(p, ROOT):
        raise PermissionError(f"write target outside MDWIZ_ROOT: {path}")
    rel = str(p.relative_to(ROOT))
    # WIZARD.md at the root is always writable so claude can create / edit
    # the project's wizard guide regardless of MDWIZ_WRITE_GLOBS.
    if rel == "WIZARD.md":
        return p
    if not WRITE_GLOBS:
        raise PermissionError(
            "fs_write disabled — set MDWIZ_WRITE_GLOBS to enable "
            "(comma-separated globs relative to MDWIZ_ROOT). "
            "Note: WIZARD.md is always writable as a special case."
        )
    for g in WRITE_GLOBS:
        if fnmatch.fnmatch(rel, g):
            return p
    raise PermissionError(
        f"path '{rel}' does not match any MDWIZ_WRITE_GLOBS pattern: {WRITE_GLOBS}"
    )


# ---------------------------------------------------------------------------
# shell_run — PTY exec with prompt sideband
# ---------------------------------------------------------------------------

def _mask_prompts(text: str, patterns: list[re.Pattern[str]]) -> str:
    out = []
    for line in text.splitlines():
        masked = line
        for pat in patterns:
            if pat.search(line):
                masked = "<PROMPT LINE MASKED>"
                break
        out.append(masked)
    return "\n".join(out)


def _kill_tree(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _request_sideband_input(prompt: str, cmd: str, meta: dict) -> str | None:
    """Request user input via mdwiz-helper. None if no socket or cancelled."""
    if not SOCKET:
        return None
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(180)
        s.connect(SOCKET)
        s.sendall(json.dumps({
            "op": "prompt_request",
            "prompt": prompt, "cmd": cmd, "meta": meta or {},
        }).encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        s.close()
        if not buf:
            return None
        resp = json.loads(buf.split(b"\n", 1)[0])
        if resp.get("cancelled"):
            return None
        return resp.get("value", "")
    except Exception as e:
        _log(f"sideband error: {e}")
        return None


@mcp.tool()
def shell_run(
    cmd: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    prompt_patterns: list[str] | None = None,
    timeout_sec: int = 1800,
    tail_lines: int = 200,
) -> dict:
    """
    Run a shell command in a PTY. Combined stdout/stderr captured.

    On prompt match (default patterns: Password/Passphrase/Username), if
    MDWIZ_SOCKET is set, asks the user via tmux popup and writes the response
    to the PTY's stdin so the command continues. Without socket, the command
    is killed and the prompt is recorded.

    Returns:
      {exit_code, tail_log, prompts_seen, duration_sec, killed_for_prompt}
    """
    pat_strings = list(DEFAULT_PROMPT_PATTERNS) + list(prompt_patterns or [])
    patterns = [re.compile(p) for p in pat_strings]
    cmd_env = os.environ.copy()
    if env:
        cmd_env.update(env)
    work_cwd = cwd or str(ROOT)

    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.chdir(work_cwd)
            os.execvpe("/bin/bash", ["/bin/bash", "-c", cmd], cmd_env)
        except Exception as exc:
            print(f"exec failed: {exc}", file=sys.stderr, flush=True)
            os._exit(127)

    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    start = time.time()
    output = bytearray()
    line_buf = ""
    prompts_seen: list[str] = []
    killed = False
    exit_code: int | None = None

    try:
        while True:
            if time.time() - start > timeout_sec:
                _log(f"timeout {timeout_sec}s — killing pid={pid}")
                _kill_tree(pid)
                killed = True
                break

            try:
                r, _, _ = select.select([fd], [], [], 0.1)
            except (OSError, ValueError):
                break

            if fd in r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    output.extend(chunk)
                    line_buf += chunk.decode("utf-8", errors="replace")

                    while "\n" in line_buf:
                        line, line_buf = line_buf.split("\n", 1)
                        for pat in patterns:
                            if pat.search(line):
                                prompts_seen.append(line.strip())
                                break

                    for pat in patterns:
                        if pat.search(line_buf):
                            prompt_text = line_buf.strip()
                            prompts_seen.append(prompt_text)
                            value = _request_sideband_input(
                                prompt_text, cmd, {"cwd": work_cwd, "exec": "shell_run"},
                            )
                            if value is not None:
                                _log(f"sideband ok ({len(value)} chars) → PTY stdin")
                                try:
                                    os.write(fd, (value + "\n").encode("utf-8"))
                                except OSError as e:
                                    _log(f"PTY write failed: {e}")
                                line_buf = ""
                            else:
                                _log(f"prompt + no sideband — killing: {prompt_text!r}")
                                _kill_tree(pid)
                                killed = True
                                line_buf = ""
                            break
                    if killed:
                        break

            try:
                wpid, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break
            if wpid == pid:
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    exit_code = -os.WTERMSIG(status)
                try:
                    while True:
                        chunk = os.read(fd, 4096)
                        if not chunk:
                            break
                        output.extend(chunk)
                except OSError:
                    pass
                break
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

    if exit_code is None:
        try:
            wpid, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                exit_code = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                exit_code = -os.WTERMSIG(status)
            else:
                exit_code = -1
        except ChildProcessError:
            exit_code = -1

    text = output.decode("utf-8", errors="replace")
    masked = _mask_prompts(text, patterns)
    tail = "\n".join(masked.splitlines()[-tail_lines:])

    return {
        "exit_code": exit_code,
        "tail_log": tail,
        "prompts_seen": prompts_seen,
        "duration_sec": round(time.time() - start, 2),
        "killed_for_prompt": killed and bool(prompts_seen),
    }


# ---------------------------------------------------------------------------
# fs_read / fs_write
# ---------------------------------------------------------------------------

@mcp.tool()
def fs_read(path: str) -> str:
    """
    Read a file (or list a directory) within the read whitelist
    (MDWIZ_ROOT subtree + MDWIZ_READ_GLOBS).

    Directory paths return a newline-separated list of immediate children.
    """
    p = _check_readable(path)
    if not p.exists():
        raise FileNotFoundError(f"not found: {path}")
    if p.is_dir():
        return "\n".join(sorted(c.name for c in p.iterdir()))
    return p.read_text(encoding="utf-8", errors="replace")


@mcp.tool()
def fs_write(path: str, content: str) -> dict:
    """
    Write a file under MDWIZ_ROOT, restricted by MDWIZ_WRITE_GLOBS.
    Idempotent — returns {"changed": False, ...} when content matches existing.
    """
    p = _check_writable(path)
    if p.exists() and p.read_text(encoding="utf-8") == content:
        return {"changed": False, "path": str(p)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"changed": True, "path": str(p)}


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------

@mcp.tool()
def progress(
    stage: str,
    detail: str | None = None,
    percent: int | None = None,
) -> dict:
    """
    Notify wizard progress. Currently logs to stderr; a UI hook may pick this up
    in future. Call at major milestones (e.g. "clone", "build", "install").
    """
    parts = [f"stage={stage}"]
    if detail is not None:
        parts.append(f"detail={detail!r}")
    if percent is not None:
        parts.append(f"percent={percent}")
    _log("progress: " + " ".join(parts))
    return {"ok": True}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _log(
        f"starting root={ROOT} "
        f"read_extras={[str(e) for e in READ_EXTRAS]} "
        f"write_globs={WRITE_GLOBS} "
        f"socket={SOCKET or '(unset)'}"
    )
    mcp.run()
