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

# 라이센스 등록 선행 요구 — 의도적으로 WIZARD.md 본문에 적시 안 함.
# 첫 실행 시 사용자가 이 메시지를 보고 "deploy 전에 register 가 필요" 라는 사실을
# 알게 되고, claude 에게 WIZARD.md 본문 갱신을 시킬 수 있도록 함 (workflow 학습 demo).
LIC_FILE="/tmp/mdwiz-demo-license-${ENV}.txt"
if [ ! -f "$LIC_FILE" ]; then
  log "ERROR: 라이센스 미등록"
  log "       먼저 'register' 를 실행해야 합니다 — bash scripts/register.sh $ENV"
  exit 1
fi
log "라이센스 확인됨 ($LIC_FILE)"

log "이미지 fetch 시뮬"
sleep 0.7
log "이미지 fetch 완료 (가상)"

log "인증 필요 — API Key 요청"

# 환경별 정책 (가상)
case "$ENV" in
  dev)      MIN_KEY_LEN=1  ; MAX_ATTEMPT=1 ; CONFIRM_PROD=0 ;;  # loose
  staging)  MIN_KEY_LEN=8  ; MAX_ATTEMPT=3 ; CONFIRM_PROD=0 ;;  # 일반 secret
  prod)     MIN_KEY_LEN=16 ; MAX_ATTEMPT=3 ; CONFIRM_PROD=1 ;;  # 엄격 + 최종 confirm
esac
log "  policy: min_key_len=${MIN_KEY_LEN} max_attempt=${MAX_ATTEMPT} confirm_prod=${CONFIRM_PROD}"

attempt=0
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

# prod 에선 한 단계 더 — 비표준 prompt 라 default 패턴 매칭 안 됨.
# mdwiz 의 inactivity fallback (60초) 으로 잡힌다.
if [ "$CONFIRM_PROD" = "1" ]; then
  log "PROD 확정 입력 필요"
  printf 'Type CONFIRM-PROD to proceed: '
  read -r CONFIRM
  if [ "$CONFIRM" != "CONFIRM-PROD" ]; then
    log "ERROR: PROD 확정 실패 (입력: '${CONFIRM}')"
    exit 1
  fi
  log "PROD 확정 완료"
fi
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
