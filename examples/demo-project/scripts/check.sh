#!/usr/bin/env bash
# 환경 의존성 점검 — 비번 없이 진행.
set -uo pipefail

echo "── demo-project 환경 점검 ──"
sleep 0.3

rc=0
for tool in bash python3 tmux; do
  if path=$(command -v "$tool" 2>/dev/null); then
    printf "  [OK] %-8s  %s\n" "$tool" "$path"
  else
    printf "  [--] %-8s  (없음)\n" "$tool"
    rc=1
  fi
done

echo
if [ "$rc" = "0" ]; then
  echo "결론: 모든 의존성 OK"
else
  echo "결론: 누락된 의존성 있음 (위 [--] 항목)"
fi
exit $rc
