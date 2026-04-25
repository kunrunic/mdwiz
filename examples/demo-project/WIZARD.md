---
mdwiz:
  prompts:
    - "API Key:"
  commands:
    # deploy.sh 는 가상 스크립트라 빨리 끝나지만, 실전 배포라면 길게 잡는 예시
    - match: "bash scripts/deploy.sh prod*"
      inactivity_sec: 600
      timeout_sec: 3600
---
# demo-project — mdwiz 워크플로우 가이드

이 프로젝트는 mdwiz 의 동작을 보여주는 가상 데모다. 실제 외부 시스템 호출 없이 `echo` / `sleep` / `read` 로만 시뮬레이션한다.

> 상단 frontmatter 의 `mdwiz:` 영역은 mdwiz 가 자동으로 읽는 설정. `prompts` 추가 → 1차 매칭 즉시. `commands` → cmd 별 inactivity/timeout 오버라이드.

## 자주 할 작업

| 작업 | 명령 | 비번 | 설명 |
|---|---|---|---|
| `check`    | `bash scripts/check.sh`            | X | 환경 의존성 점검 (bash, python3, tmux) |
| `register` | `bash scripts/register.sh <env>`   | O | 가상 라이센스 등록 (`License Key:` prompt — default 매칭 X) |
| `deploy`   | `bash scripts/deploy.sh <env>`     | O | 가상 배포 — env 별 정책 다름 (아래 표) |
| `status`   | `bash scripts/status.sh <env>`     | X | 가상 서비스 상태 조회 |
| `cleanup`  | `bash scripts/cleanup.sh`          | X | 데모가 남긴 `/tmp/mdwiz-demo-*` 정리 |

> **데모 학습 단계 (의도적으로 미완성으로 둔 부분)**
> - frontmatter 의 `prompts` 에 `License Key:` 가 **빠져 있다**. `register` 첫 실행 때 mdwiz inactivity fallback (60초) 로 popup 됨 → 그 직후 claude 가 사용자에게 "frontmatter 에 추가할까요?" 제안 → 추가 후 다음번부턴 즉시.
> - `deploy` 가 `register` 를 선행 요구한다는 사실이 본문에 **명시 안 되어 있다**. 첫 `deploy` 실행 시 라이센스 미등록 에러 → claude 가 "이 의존을 본문에 추가할까요?" 제안 → 추가.
>
> 이 두 단계가 mdwiz 의 lint→고도화 사이클을 직접 체험하는 부분.

### deploy 의 env 별 정책 (가상)

| env | API Key 최소 길이 | 재시도 | 추가 step | 데모 의도 |
|---|---|---|---|---|
| `dev`     | 1자 (loose)  | 1회 | — | 빠른 로컬 테스트 — popup 한 번만 |
| `staging` | 8자          | 3회 | — | 일반적 secret 입력 + 재시도 popup |
| `prod`    | 16자         | 3회 | `Type CONFIRM-PROD to proceed:` | 비표준 prompt → **mdwiz inactivity fallback** 시연 (default 패턴에 안 잡혀서 60s 후 popup) |

## 워크플로우

1. **점검 → 배포 → 상태확인** 순서가 일반적.
2. `deploy` 는 `<env>` 인자가 필요 (`dev` / `staging` / `prod` 중 하나). 사용자에게 chat 으로 묻고 진행.
3. `deploy` 중 `API Key:` 프롬프트가 뜨면 mdwiz popup 이 자동으로 처리. 비번은 chat 에 안 남는다.
4. 모든 작업은 `shell_run` 으로. 결과의 `tail_log` 와 `exit_code` 를 사용자에게 짧게 요약.

## 주의사항

- 이 데모는 **완전 가상**. 실제 서비스 / 디스크 / 네트워크 영향 없음.
- `cleanup` 은 `/tmp/mdwiz-demo-*` 파일만 지움. 다른 경로 안 건드림.
- `progress("...")` 는 단계별로 호출해서 mdwiz 진행 추적 가능하게 한다.
