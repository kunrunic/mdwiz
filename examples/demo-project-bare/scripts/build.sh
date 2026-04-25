#!/usr/bin/env bash
# 가상 정적 사이트 빌드 — 비번 없이 진행. /tmp 아래에 가짜 산출물만 만든다.
set -uo pipefail

OUT="/tmp/mdwiz-bare-build"
mkdir -p "$OUT"

echo "── build ──"
sleep 0.3
echo "  pages 수집 ..."
sleep 0.3
echo "  마크다운 → HTML 변환 (가상)"
sleep 0.3

# 가상 산출물 — 진짜 빌드는 안 함
{
  echo "<!doctype html>"
  echo "<title>mdwiz-bare demo</title>"
  echo "<h1>built at $(date -Iseconds)</h1>"
} > "$OUT/index.html"
echo "asset placeholder" > "$OUT/style.css"

echo "  완료: $OUT"
ls "$OUT" | sed 's/^/    | /'
