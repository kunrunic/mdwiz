#!/usr/bin/env bash
# 가상 미리보기 서버 — 실제 서버 안 띄움, URL 만 출력. 비번 X.
set -uo pipefail

OUT="/tmp/mdwiz-bare-build"
PORT="${1:-4321}"

if [ ! -d "$OUT" ]; then
  echo "✗ 빌드 산출물이 없음 ($OUT) — 먼저 'bash scripts/build.sh' 를 실행하세요." >&2
  exit 1
fi

echo "── preview (mock) ──"
echo "  serving $OUT"
echo "  → http://localhost:${PORT}/"
echo "  (실제 서버는 띄우지 않음 — 데모)"
