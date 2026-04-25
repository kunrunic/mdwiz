#!/usr/bin/env bash
# 가상 서비스 상태 조회 — 비번 없이 진행.
set -uo pipefail

ENV="${1:-dev}"
case "$ENV" in
  dev|staging|prod) ;;
  *) echo "✗ env 인자가 dev|staging|prod 중 하나여야 합니다 (받은 값: '$ENV')" >&2; exit 2 ;;
esac

LOG="/tmp/mdwiz-demo-deploy-${ENV}.log"

echo "── [$ENV] 상태 ──"
echo "  service : running (mock)"
echo "  uptime  : $((RANDOM % 3600)) sec"
echo "  health  : OK"

if [ -f "$LOG" ]; then
  echo
  echo "  최근 배포 로그 (마지막 5줄, $LOG):"
  tail -5 "$LOG" | sed 's/^/    | /'
else
  echo
  echo "  배포 로그 없음 (아직 deploy 안 함)"
fi
