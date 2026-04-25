#!/usr/bin/env bash
# 가상 퍼블리시 — `Publish Token:` 프롬프트를 사용해서 비번 popup 동작을 시연.
#
# 의도 (생성 플로우 데모):
#   - claude 가 README + 이 파일을 읽고 WIZARD.md 초안을 작성할 때
#     `read -s TOKEN` 줄과 prompt 문자열을 발견해서 frontmatter prompts 에
#     'Publish Token:' 을 넣어주는지 (또는 못 넣고 첫 실행 시 inactivity 로
#     처리되는지) 를 관찰하기 위함.
set -uo pipefail

ENV="${1:-dev}"
case "$ENV" in
  dev|prod) ;;
  *) echo "✗ env 인자가 dev|prod 중 하나여야 합니다 (받은 값: '$ENV')" >&2; exit 2 ;;
esac

OUT="/tmp/mdwiz-bare-build"
LOG="/tmp/mdwiz-bare-publish-${ENV}.log"

if [ ! -d "$OUT" ]; then
  echo "✗ 빌드 산출물이 없음 — 먼저 'bash scripts/build.sh' 를 실행하세요." >&2
  exit 1
fi

log() { printf '[%s] %s\n' "$ENV" "$*" | tee -a "$LOG"; }

log "퍼블리시 시작 ($OUT)"
sleep 0.3
log "원격 인증 필요"

printf 'Publish Token: '
read -rs TOKEN
echo

if [ "${#TOKEN}" -lt 6 ]; then
  log "ERROR: Publish Token 너무 짧음 (필요 6+ 자, 받은 길이 ${#TOKEN})"
  exit 1
fi
log "토큰 검증 OK (length=${#TOKEN})"

log "업로드 시뮬 (3 파일)"
for f in $(ls "$OUT"); do
  sleep 0.2
  log "  uploaded: $f"
done

log "캐시 무효화 시뮬"
sleep 0.3
log "퍼블리시 완료"
echo
echo "(로그: $LOG)"
