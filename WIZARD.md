# mdwiz WIZARD

## 프로젝트 개요

**mdwiz** — 마크다운 기반 AI 워크플로우 러너. 이 레포는 mdwiz 도구 **그 자체**의 소스입니다 (다른 프로젝트의 가이드가 아니라).

핵심 구성:
- `bin/mdwiz` — 메인 진입점 (bash, tmux + claude 띄우는 오케스트레이터)
- `bin/mdwiz-mcp.py` — MCP 서버 (`shell_run` / `fs_read` / `fs_write` / `progress` 도구 제공)
- `bin/mdwiz-helper.py` — 비번 popup 유닉스 소켓 서버
- `bin/mdwiz-pwprompt.py` — 비번 입력 UI (마스크)
- `bin/mdwiz-system.md` — claude 에 주입되는 기본 시스템 프롬프트
- `setup.sh` — PATH 등록 / pip install / doctor 실행 (idempotent)
- `examples/walkthrough.md` — 사용 시나리오 예시

## 자주 할 작업

| # | 작업 | 목적 |
|---|---|---|
| 1 | **설치 / 재설치** | `setup.sh` 실행 — pip 의존성 + PATH 등록 + doctor |
| 2 | **doctor 진단** | tmux / claude / python+mcp 의존성 OK 인지 확인 |
| 3 | **세션 관리** | 떠있는 mdwiz 세션 list / 단일 kill / 전체 kill |
| 4 | **소스 수정 후 검증** | `bin/*` 또는 시스템 프롬프트 수정 → doctor → 다른 디렉터리에서 테스트 실행 |
| 5 | **시스템 프롬프트 튜닝** | `bin/mdwiz-system.md` 편집 (이 파일 = claude 의 페르소나/규칙) |
| 6 | **MCP 도구 동작 변경** | `bin/mdwiz-mcp.py` 의 `shell_run` / `fs_read` / `fs_write` / `progress` 수정 |
| 7 | **README / walkthrough 업데이트** | 사용법 / 환경변수 표 / 시나리오 예제 갱신 |

## 각 작업의 절차

### 1. 설치 / 재설치

```
shell_run("bash setup.sh")
```

옵션:
- `bash setup.sh --no-pip` — Python 패키지 설치 건너뜀 (이미 설치됨)
- `bash setup.sh --system` — `/usr/local/bin/mdwiz` symlink (sudo 필요, 다른 사용자도 사용 가능)
- `bash setup.sh --rc <path>` — rc 파일 직접 지정 (자동 감지 실패 시)

마지막에 `mdwiz --doctor` 자동 실행됨.

### 2. doctor 진단

```
shell_run("bin/mdwiz --doctor")
```

확인 항목: `tmux`, `claude`, `python3`, `python3 -c "import mcp"`, root/session/socket 경로.
실패 항목 ✗ 가 뜨면 그 줄의 안내대로 조치 (보통 `pip install -r requirements.txt`).

### 3. 세션 관리

```
shell_run("bin/mdwiz --list")              # 떠있는 모든 mdwiz-* 세션
shell_run("bin/mdwiz --kill")              # 현재 cwd 의 세션
shell_run("bin/mdwiz --kill <label>")      # 특정 라벨 (예: webshop-backend)
shell_run("bin/mdwiz --kill --all")        # 전부 (interactive 확인 필요 — chat 통해서 사용자에게 묻고 진행)
```

### 4. 소스 수정 후 검증

> mdwiz 자체를 디버깅 중이라면 **이 mdwiz 세션 안에서 또 mdwiz 를 실행하는 self-host 상황**에 주의. 다른 터미널에서 테스트하는 게 깔끔.

순서:
1. `bin/*` 수정 (`fs_write` 화이트리스트 안이라면 직접, 아니면 사용자에게 알리고 안내)
2. `shell_run("bin/mdwiz --doctor")` — 기본 sanity
3. (별도 터미널 권장) 임시 디렉터리에서 `mdwiz` 띄워서 새 동작 확인

### 5. 시스템 프롬프트 튜닝

대상 파일: `bin/mdwiz-system.md`

이 파일이 claude 에게 페르소나 / 도구 사용 규칙 / 응답 스타일을 알려줍니다. 수정 시 반드시:
- "이 사항이 모든 프로젝트의 mdwiz 세션에 적용됨" 을 사용자에게 상기
- 변경 내용 미리보기 (이 파일은 `.md` 라 chat 에 그대로 렌더해서 검토)
- confirm 후 `fs_write('bin/mdwiz-system.md', ...)`

### 6. MCP 도구 동작 변경

대상 파일: `bin/mdwiz-mcp.py`

도구 함수 추가/수정 시:
- 새 도구를 추가하면 시스템 프롬프트의 도구 표도 같이 갱신
- 화이트리스트 / 권한 검증 로직은 함부로 느슨하게 풀지 말 것 (보안상 fs_write 가 핵심)
- 수정 후 doctor + 별도 터미널 테스트

### 7. README / walkthrough 업데이트

- `README.md` — 환경변수 표 / 설치 절차 / 트러블슈팅
- `examples/walkthrough.md` — 시나리오 예제

## 사용자에게 물어야 할 정보

| 시점 | 질문 |
|---|---|
| 설치 시 | `--system` (sudo 전역) 으로 할지, 사용자 셸 rc 만 수정할지 |
| `--kill --all` | 정말 전부 종료할지 (사용자 confirm) |
| 시스템 프롬프트 수정 | "변경이 모든 프로젝트에 영향" 알리고 confirm |
| 새 의존성 추가 | requirements.txt 에 넣을지, 옵션으로 둘지 |

## 주의사항 / 위험한 단계

| 위험도 | 단계 | 설명 | 대응 |
|---|---|---|---|
| 높음 | `bin/mdwiz-system.md` 수정 | 모든 mdwiz 세션의 claude 동작 변경 | 변경 내용 전부 미리보기 + confirm |
| 높음 | `bin/mdwiz-mcp.py` 의 fs_write 화이트리스트 로직 수정 | 보안 게이트 — 잘못 풀면 임의 파일 쓰기 가능 | 변경 후 의도한 거부 케이스 직접 테스트 |
| 중간 | `setup.sh --system` | `/usr/local/bin` 에 symlink, sudo 필요 | 사용자 동의 받고 진행 |
| 중간 | `setup.sh` 의 rc 파일 수정 | `.zshrc` 등에 PATH 라인 추가 | marker 주석으로 식별 가능, idempotent (이미 있으면 skip) |
| 낮음 | `mdwiz --kill --all` | 다른 작업 중인 세션도 같이 끔 | confirm 거치므로 보통 안전 |

## 쓰기 권한 (MDWIZ_WRITE_GLOBS)

이 프로젝트의 mdwiz 세션을 띄울 때 쓰기 가능 패턴 권장:
```
MDWIZ_WRITE_GLOBS='bin/*,bin/*.md,bin/*.py,setup.sh,README.md,examples/*.md,requirements.txt' mdwiz
```

`WIZARD.md` 자체는 화이트리스트와 무관하게 항상 쓰기 허용 (가이드 갱신용).
