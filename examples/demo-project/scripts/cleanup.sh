#!/usr/bin/env bash
# 데모가 남긴 /tmp/mdwiz-demo-* 파일 정리.
set -uo pipefail

echo "── cleanup ──"
files=(/tmp/mdwiz-demo-*)
if [ ! -e "${files[0]}" ]; then
  echo "  (정리할 파일 없음)"
  exit 0
fi

for f in "${files[@]}"; do
  rm -f "$f"
  echo "  removed: $f"
done
echo "완료"
