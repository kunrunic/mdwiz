#!/usr/bin/env bash
# 데모가 남긴 /tmp/mdwiz-bare-* 정리.
set -uo pipefail

echo "── clean ──"
shopt -s nullglob
files=(/tmp/mdwiz-bare-*)
if [ ${#files[@]} -eq 0 ]; then
  echo "  (정리할 파일 없음)"
  exit 0
fi

for f in "${files[@]}"; do
  rm -rf "$f"
  echo "  removed: $f"
done
echo "완료"
