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

import yaml
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
    # 비번류
    r"[Pp]assword[^:]*:\s*$",
    r"[Pp]assphrase[^:]*:\s*$",
    # 토큰 / API Key / Secret 류 (일반적 시크릿 입력 프롬프트)
    r"[Aa][Pp][Ii][ _-]?[Kk]ey[^:]*:\s*$",
    r"[Tt]oken[^:]*:\s*$",
    r"[Ss]ecret[^:]*:\s*$",
    # git / ssh 사용자명
    r"Username for [^:]+:\s*$",
]

mcp = FastMCP("mdwiz")


def _log(msg: str) -> None:
    print(f"[mdwiz-mcp] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# WIZARD.md frontmatter — project-specific config
# ---------------------------------------------------------------------------
#
# 프로젝트의 WIZARD.md 상단에 YAML frontmatter 로 mdwiz 설정을 둘 수 있다:
#
#   ---
#   mdwiz:
#     prompts:                                # default 패턴에 추가될 regex
#       - "API Key:"
#       - "[Cc]ode:"
#     commands:                               # cmd 매칭 시 timing/stream 오버라이드
#       - match: "bash scripts/deploy.sh prod*"  # fnmatch glob against full cmd
#         inactivity_sec: 1800
#         timeout_sec: 7200
#         stream: true                        # 긴 명령 — split-pane 자동 발동
#       - match: "bash scripts/build.sh*"
#         inactivity_sec: 600
#         stream: true
#   ---
#
# - prompts: default + per-call prompt_patterns 와 함께 union
# - commands: 첫 매치가 적용. 호출자가 명시 인자를 줬으면 그걸 우선.
#             stream 키는 호출자가 stream=False (default) 일 때만 적용.
#
# 매 shell_run 호출 시 새로 read — claude 가 mid-session 에 WIZARD.md 갱신해도
# 다음 호출부터 즉시 반영.

def _load_wizard_config() -> dict:
    """WIZARD.md frontmatter 의 mdwiz: 섹션을 dict 로 반환. 없으면 {}."""
    wp = ROOT / "WIZARD.md"
    if not wp.exists():
        return {}
    try:
        text = wp.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
        if not m:
            return {}
        data = yaml.safe_load(m.group(1)) or {}
        return data.get("mdwiz") or {}
    except Exception as e:
        _log(f"WIZARD.md frontmatter 파싱 실패: {e}")
        return {}


def _wizard_command_overrides(cmd: str, config: dict) -> dict:
    """cmd 에 매치되는 첫 commands 항목 반환 ({} 가능)."""
    for entry in (config.get("commands") or []):
        glob = entry.get("match", "")
        if glob and fnmatch.fnmatch(cmd, glob):
            return entry
    return {}


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


def _request_sideband_input(prompt: str, cmd: str, meta: dict) -> tuple[str | None, str | None]:
    """Request user input via mdwiz-helper.

    반환 (value, error):
      ("입력값", None)  — 정상
      (None, None)      — 사용자가 popup 에서 취소 (Ctrl+C)
      (None, "사유")    — sideband 자체가 불가 (helper 없음 / popup 실패 등).
                          이 경우 빈 값을 stdin 에 주입하면 안 된다 — 사용자에게는
                          "인증 실패" 로만 보이고 원인 추적이 불가능해지기 때문.
    """
    if not SOCKET:
        return None, "MDWIZ_SOCKET 미설정 — helper 없이 실행 중"
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
            return None, "helper 응답 없음 (연결 끊김)"
        resp = json.loads(buf.split(b"\n", 1)[0])
        if resp.get("cancelled"):
            return None, None
        err = resp.get("error")
        if err:
            return None, str(err)
        value = resp.get("value")
        if value is None:
            return None, "helper 응답에 value 없음"
        return value, None
    except Exception as e:
        _log(f"sideband error: {e}")
        return None, f"sideband 통신 실패: {e}"


def _sideband_notify(msg: dict) -> None:
    """Fire-and-forget sideband message (no response expected)."""
    if not SOCKET:
        return
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(SOCKET)
        s.sendall(json.dumps(msg).encode() + b"\n")
        s.close()
    except Exception as e:
        _log(f"sideband notify error ({msg.get('op','?')}): {e}")


@mcp.tool()
def shell_run(
    cmd: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    prompt_patterns: list[str] | None = None,
    timeout_sec: int = 1800,
    tail_lines: int = 200,
    inactivity_sec: int = 60,
    stream: bool = False,
) -> dict:
    """
    Run a shell command in a PTY. Combined stdout/stderr captured.

    Two ways the popup can fire:
      1. Pattern match — `prompt_patterns` (default covers Password / Passphrase
         / API Key / Token / Secret / Username for ...). Fast and exact.
      2. Inactivity fallback — if the process produces no output for
         `inactivity_sec` seconds AND is still alive, mdwiz assumes it is
         blocked on stdin and pops the popup with the last output line as
         context. Catches non-standard prompts ("Enter code:", etc.).
         Set `inactivity_sec=0` to disable.

    User in popup can either type the value (injected to PTY stdin) or cancel
    (Ctrl+C) which kills the process.

    Long-running commands: pass `stream=True` (or set `stream: true` on the
    matching commands[] entry in WIZARD.md frontmatter) to also tee raw
    output to a tmux split-pane while the command runs. The pane auto-closes
    on exit_code=0; non-zero stays open (user closes with q).

    Args:
      cmd            : full command line (passed to bash -c).
      cwd            : working directory (default: MDWIZ_ROOT).
      env            : extra env vars (merged on top of os.environ).
      prompt_patterns: extra regex patterns; defaults are added too.
      timeout_sec    : hard kill after this many seconds (default 30 min).
      tail_lines     : tail length to return (default 200).
      inactivity_sec : seconds of silence before fallback popup fires
                       (default 60; 0 = disabled).
      stream         : if True, raw stdout/stderr is also tail -F'd in a tmux
                       split-pane while the command runs (default False —
                       short commands keep the silent behaviour).

    Returns:
      {exit_code, tail_log, prompts_seen, duration_sec, killed_for_prompt}
      + sideband_error : popup 을 띄우지 못해 명령을 중단한 경우에만 존재.
                         명령 자체의 실패가 아니라 mdwiz 환경 문제 (tmux 3.2 미만,
                         helper 미기동 등) 이므로 사용자에게 그대로 전달할 것.
    """
    # WIZARD.md frontmatter 의 prompts / commands 반영
    wiz_cfg = _load_wizard_config()
    wiz_prompts = wiz_cfg.get("prompts") or []
    pat_strings = list(DEFAULT_PROMPT_PATTERNS) + list(wiz_prompts) + list(prompt_patterns or [])
    patterns = [re.compile(p) for p in pat_strings]

    overrides = _wizard_command_overrides(cmd, wiz_cfg)
    # 호출자가 default 값으로 두었을 때만 WIZARD.md 의 값을 적용 — explicit 인자 우선.
    if overrides:
        if timeout_sec == 1800 and "timeout_sec" in overrides:
            timeout_sec = int(overrides["timeout_sec"])
            _log(f"WIZARD.md override: timeout_sec={timeout_sec} (cmd matched '{overrides['match']}')")
        if inactivity_sec == 60 and "inactivity_sec" in overrides:
            inactivity_sec = int(overrides["inactivity_sec"])
            _log(f"WIZARD.md override: inactivity_sec={inactivity_sec} (cmd matched '{overrides['match']}')")
        if not stream and "stream" in overrides:
            stream = bool(overrides["stream"])
            if stream:
                _log(f"WIZARD.md override: stream=True (cmd matched '{overrides['match']}')")

    cmd_env = os.environ.copy()
    # PTY pager 함정 원천 차단: git(config/log/diff/show/branch...) · man · systemctl 등이
    # stdout=TTY 를 보고 pager(less) 를 띄워 hang 되는 것을 막는다. cat 은 즉시 EOF 로 흘려보냄.
    # 명시적으로 넘어온 env 는 아래에서 override 가능 (의도적 pager 사용 여지 유지).
    cmd_env["GIT_PAGER"] = "cat"
    cmd_env["PAGER"] = "cat"
    cmd_env["MANPAGER"] = "cat"
    cmd_env["SYSTEMD_PAGER"] = ""
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
    sideband_error: str | None = None   # popup 인프라 실패 사유 (사용자 취소와 구분)
    exit_code: int | None = None
    last_output_time = time.time()

    # stream 모드 — child pid 기반 로그파일 + helper 에 split-pane 띄우라고 통지.
    # pid 는 helper 측 pane 추적 dict 의 key 로도 쓰임 (close 시 매칭).
    stream_log_path: str | None = None
    stream_log_fd: int | None = None
    if stream:
        stream_log_path = f"/tmp/mdwiz-stream-{pid}.log"
        try:
            stream_log_fd = os.open(
                stream_log_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            _sideband_notify({
                "op": "stream_open",
                "pid": pid,
                "log_path": stream_log_path,
                "title": cmd[:60],
            })
        except OSError as e:
            _log(f"stream log open failed ({stream_log_path}): {e} — falling back to non-stream")
            stream_log_fd = None
            stream_log_path = None

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
                    last_output_time = time.time()
                    output.extend(chunk)
                    if stream_log_fd is not None:
                        try:
                            os.write(stream_log_fd, chunk)
                        except OSError as e:
                            _log(f"stream log write failed: {e}")
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
                            value, sb_err = _request_sideband_input(
                                prompt_text, cmd, {"cwd": work_cwd, "exec": "shell_run"},
                            )
                            if value is not None:
                                _log(f"sideband ok ({len(value)} chars) → PTY stdin")
                                try:
                                    os.write(fd, (value + "\n").encode("utf-8"))
                                    last_output_time = time.time()
                                except OSError as e:
                                    _log(f"PTY write failed: {e}")
                                line_buf = ""
                            else:
                                if sb_err:
                                    sideband_error = sb_err
                                    _log(f"sideband 불가 ({sb_err}) — killing: {prompt_text!r}")
                                else:
                                    _log(f"사용자 취소 — killing: {prompt_text!r}")
                                _kill_tree(pid)
                                killed = True
                                line_buf = ""
                            break
                    if killed:
                        break

            # Inactivity fallback — 패턴 매칭 안 된 비표준 프롬프트도 잡기 위함.
            # PTY 출력이 N초간 없고 프로세스 살아있으면 stdin 대기 가능성 → popup.
            if (inactivity_sec > 0 and not killed and
                    time.time() - last_output_time > inactivity_sec):
                # 마지막 출력 라인을 hint 로
                hint = line_buf.strip()
                if not hint:
                    text_so_far = output.decode("utf-8", errors="replace").splitlines()
                    hint = text_so_far[-1].strip() if text_so_far else "(no output yet)"
                prompt_text = f"[inactivity {inactivity_sec}s] {hint}"
                prompts_seen.append(prompt_text)
                _log(f"inactivity fallback fired — hint: {hint!r}")
                value, sb_err = _request_sideband_input(
                    prompt_text, cmd,
                    {"cwd": work_cwd, "exec": "shell_run", "reason": f"inactivity {inactivity_sec}s"},
                )
                if value is not None:
                    _log(f"sideband ok ({len(value)} chars) → PTY stdin")
                    try:
                        os.write(fd, (value + "\n").encode("utf-8"))
                    except OSError as e:
                        _log(f"PTY write failed: {e}")
                    last_output_time = time.time()  # reset
                    line_buf = ""
                else:
                    if sb_err:
                        sideband_error = sb_err
                        _log(f"inactivity popup 불가 ({sb_err}) — killing")
                    else:
                        _log("inactivity popup 취소 — killing")
                    _kill_tree(pid)
                    killed = True
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
                        if stream_log_fd is not None:
                            try:
                                os.write(stream_log_fd, chunk)
                            except OSError:
                                pass
                except OSError:
                    pass
                break
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        if stream_log_fd is not None:
            try:
                os.close(stream_log_fd)
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

    if stream_log_path is not None:
        _sideband_notify({
            "op": "stream_close",
            "pid": pid,
            "log_path": stream_log_path,
            "exit_code": exit_code if exit_code is not None else -1,
        })

    result = {
        "exit_code": exit_code,
        "tail_log": tail,
        "prompts_seen": prompts_seen,
        "duration_sec": round(time.time() - start, 2),
        "killed_for_prompt": killed and bool(prompts_seen),
    }
    if sideband_error:
        # popup 을 띄우지 못해 중단된 경우 — 명령 자체의 실패가 아니라 mdwiz 환경
        # 문제임을 AI 가 사용자에게 그대로 전달할 수 있도록 별도 필드로 반환.
        result["sideband_error"] = sideband_error
    return result


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
