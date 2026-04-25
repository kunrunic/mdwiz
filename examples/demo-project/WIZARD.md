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
| `check`   | `bash scripts/check.sh`            | X | 환경 의존성 점검 (bash, python3, tmux) |
| `deploy`  | `bash scripts/deploy.sh <env>`     | O | 가상 배포 — `API Key:` popup 트리거 |
| `status`  | `bash scripts/status.sh <env>`     | X | 가상 서비스 상태 조회 |
| `cleanup` | `bash scripts/cleanup.sh`          | X | 데모가 남긴 `/tmp/mdwiz-demo-*` 정리 |

## 워크플로우

1. **점검 → 배포 → 상태확인** 순서가 일반적.
2. `deploy` 는 `<env>` 인자가 필요 (`dev` / `staging` / `prod` 중 하나). 사용자에게 chat 으로 묻고 진행.
3. `deploy` 중 `API Key:` 프롬프트가 뜨면 mdwiz popup 이 자동으로 처리. 비번은 chat 에 안 남는다.
4. 모든 작업은 `shell_run` 으로. 결과의 `tail_log` 와 `exit_code` 를 사용자에게 짧게 요약.

## 주의사항

- 이 데모는 **완전 가상**. 실제 서비스 / 디스크 / 네트워크 영향 없음.
- `cleanup` 은 `/tmp/mdwiz-demo-*` 파일만 지움. 다른 경로 안 건드림.
- `progress("...")` 는 단계별로 호출해서 mdwiz 진행 추적 가능하게 한다.
