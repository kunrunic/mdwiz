#!/usr/bin/env python3
"""
mdwiz-pwprompt.py — runs inside `tmux display-popup -E`.

bash read -s 는 echo 자체를 끄므로 사용자에게 입력 진행 피드백이 없음.
Python 으로 raw 모드 + char-by-char 읽기 → 키 누를 때마다 `*` 즉시 표시.

Args:
  $1  meta_file (JSON: {prompt, cmd, meta})
  $2  result_file (write entered value here, raw, no trailing newline)

동작:
  - context (cmd, meta, prompt) 위에 표시
  - 입력 시 한 글자당 `*` 한 개
  - Backspace / Delete (`\\x7f`, `\\x08`) → 마지막 글자 삭제 + 화면도 지움
  - Enter (`\\r`, `\\n`) → 종료, RESULT 에 입력값 저장
  - Ctrl+C (`\\x03`) → 취소, RESULT 에 빈 값, exit 130
  - 그 외 control char → 무시
"""

from __future__ import annotations

import json
import os
import sys
import termios
import tty


def show_context(meta_file: str) -> None:
    try:
        with open(meta_file) as f:
            m = json.load(f)
    except Exception:
        return
    cmd = m.get("cmd", "")
    if cmd:
        s = cmd if len(cmd) <= 80 else cmd[:77] + "..."
        print(f"  cmd    : {s}")
    for k, v in m.get("meta", {}).items():
        print(f"  {k:6s} : {v}")
    print(f"  prompt : {m.get('prompt', 'Password:')}")
    print()


def read_masked() -> tuple[bytes, bool]:
    """Returns (entered_bytes, cancelled)."""
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        # not a tty — fallback to plain readline (no masking, but works)
        line = sys.stdin.readline().rstrip("\n")
        return line.encode(), False

    buf = bytearray()
    cancelled = False
    try:
        tty.setraw(fd)
        while True:
            ch = os.read(fd, 1)
            if not ch:
                break
            if ch in (b"\r", b"\n"):
                break
            if ch == b"\x03":  # Ctrl+C
                cancelled = True
                break
            if ch in (b"\x7f", b"\x08"):  # Backspace / Delete
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            if ord(ch) < 32:  # 그 외 control chars
                continue
            buf.extend(ch)
            sys.stdout.write("*")
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return bytes(buf), cancelled


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: mdwiz-pwprompt.py <meta_file> <result_file>", file=sys.stderr)
        return 2

    meta_file, result_file = sys.argv[1], sys.argv[2]

    show_context(meta_file)

    sys.stdout.write("입력 (Enter 확인, Ctrl+C 취소): ")
    sys.stdout.flush()

    value, cancelled = read_masked()

    sys.stdout.write("\n")

    if cancelled:
        print("취소됨")
        with open(result_file, "wb") as f:
            f.write(b"")
        try:
            os.chmod(result_file, 0o600)
        except Exception:
            pass
        return 130

    with open(result_file, "wb") as f:
        f.write(value)
    try:
        os.chmod(result_file, 0o600)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
