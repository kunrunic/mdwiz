#!/usr/bin/env bash
# 가상 라이센스 등록 — `License Key:` 프롬프트 사용.
#
# 의도 (데모 교육용):
#   - 'License Key:' 는 mdwiz 의 default 패턴 (Password / API Key / Token / ...) 매칭 X.
#   - 따라서 처음엔 mdwiz 의 inactivity fallback (60초) 으로만 popup 이 뜸.
#   - 이후 사용자가 WIZARD.md frontmatter 의 prompts 에 'License Key:' 를 추가하면
#     다음 실행부터 즉시 매칭 → 60초 안 기다림.
#
# 이게 mdwiz 의 "1번 lint → WIZARD.md 고도화 → 2번부터 즉시" 사이클의 시연.

set -uo pipefail

ENV="${1:-dev}"
case "$ENV" in
  dev|staging|prod) ;;
  *) echo "✗ env 인자가 dev|staging|prod 중 하나여야 합니다 (받은 값: '$ENV')" >&2; exit 2 ;;
esac

LIC_FILE="/tmp/mdwiz-demo-license-${ENV}.txt"

echo "[$ENV] 라이센스 등록 시작"
sleep 0.4

printf 'License Key: '
read -rs LICENSE
echo

if [ -z "$LICENSE" ]; then
  echo "ERROR: License Key 비어있음"
  exit 1
fi

# 길이 검증 — 가상이지만 실전 느낌
MIN_LEN=10
if [ "${#LICENSE}" -lt "$MIN_LEN" ]; then
  echo "ERROR: License Key 너무 짧음 (필요 ${MIN_LEN}+ 자, 받은 길이 ${#LICENSE})"
  exit 1
fi

# hash 만 저장 — 비번 자체는 디스크에 안 남김
echo "$LICENSE" | shasum -a 256 | cut -d' ' -f1 > "$LIC_FILE"
chmod 600 "$LIC_FILE" 2>/dev/null || true

echo "[$ENV] 등록 완료 (key length=${#LICENSE})"
echo "(라이센스 hash 저장: $LIC_FILE)"
