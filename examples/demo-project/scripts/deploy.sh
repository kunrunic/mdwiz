#!/usr/bin/env bash
# 가상 배포 — 인증 단계에서 `API Key:` 프롬프트가 뜨면 mdwiz popup 으로 처리됨.
set -uo pipefail

ENV="${1:-dev}"
case "$ENV" in
  dev|staging|prod) ;;
  *) echo "✗ env 인자가 dev|staging|prod 중 하나여야 합니다 (받은 값: '$ENV')" >&2; exit 2 ;;
esac

LOG="/tmp/mdwiz-demo-deploy-${ENV}.log"

log() { printf '[%s] %s\n' "$ENV" "$*" | tee -a "$LOG"; }

log "배포 시작"
log "이미지 fetch 시뮬"
sleep 0.7
log "이미지 fetch 완료 (가상)"

log "인증 필요 — API Key 요청"

# 가상의 검증 — 실전 느낌 살리기 위해 최소 길이 8자 + 3회 재시도.
MIN_KEY_LEN=8
attempt=0
MAX_ATTEMPT=3
while : ; do
  attempt=$((attempt + 1))
  if [ "$attempt" -eq 1 ]; then
    printf 'API Key: '
  else
    printf 'Invalid API Key (need >= %d chars), retry API Key [%d/%d]: ' \
      "$MIN_KEY_LEN" "$attempt" "$MAX_ATTEMPT"
  fi
  read -rs API_KEY
  echo
  if [ "${#API_KEY}" -ge "$MIN_KEY_LEN" ]; then
    break
  fi
  log "  → 길이 ${#API_KEY} (필요 ${MIN_KEY_LEN}+)"
  if [ "$attempt" -ge "$MAX_ATTEMPT" ]; then
    log "ERROR: API Key 검증 ${MAX_ATTEMPT}회 재시도 모두 실패"
    exit 1
  fi
done

log "인증 성공 (key length=${#API_KEY})"
sleep 0.4

log "롤아웃 시뮬 (3 단계)"
for step in 1 2 3; do
  sleep 0.3
  log "  rollout step $step / 3"
done

log "헬스체크 시뮬"
sleep 0.3
log "헬스체크 OK"
log "배포 완료"
echo
echo "(로그: $LOG)"
