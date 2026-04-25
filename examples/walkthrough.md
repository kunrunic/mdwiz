# mdwiz walkthrough — `demo-project` 따라 해보기

mdwiz 의 동작을 5분 안에 직접 체험하는 가이드. `examples/demo-project/` 에 들어 있는 가상 데모 (echo / sleep / read 만 쓰는 안전한 스크립트) 를 mdwiz 로 돌려본다. 실제 외부 시스템 영향 없음.

## 0. 목적 — 무엇을 보게 되는가

| 단계 | 보게 되는 것 |
|---|---|
| 1 | mdwiz 가 tmux 안에 Claude Code 를 띄우고 자동으로 첫 인사 |
| 2 | claude 가 `WIZARD.md` 를 자동으로 fs_read → 가능 작업 요약 |
| 3 | 사용자가 자연어로 "deploy 해줘" 요청 → claude 의 plan 표 |
| 4 | `shell_run` 이 가상 배포 스크립트 실행 |
| 5 | `API Key:` 프롬프트 → mdwiz popup 자동으로 뜸 (마스크 입력) |
| 6 | 입력값이 PTY stdin 에 주입되어 명령 계속 진행 |
| 7 | 결과 `tail_log` + `exit_code` 가 chat 으로 돌아옴 |

## 1. 사전 준비

mdwiz 가 PATH 에 있어야 한다 — 아직 안 했으면:

```bash
cd /path/to/mdwiz
bash setup.sh
source ~/.zshrc        # 또는 새 터미널 열기
mdwiz --doctor          # 의존성 OK 확인
```

## 2. 데모 디렉터리로 이동 + mdwiz 실행

```bash
cd /path/to/mdwiz/examples/demo-project
mdwiz
```

다음과 비슷한 메시지가 뜨고 tmux 안 claude TUI 로 attach 된다:

```
▶ mdwiz: mdwiz-demo-project  (/Users/.../examples/demo-project)
  종료: claude /exit  /  detach: Ctrl+B d  /  스크롤: 터미널 트랙패드·휠 그대로
```

이어서 claude 가 자동 인사:

```
이 프로젝트에는 `WIZARD.md` 가이드가 있습니다.
지금 그 파일을 읽고, 가능한 작업과 시작 시 필요 정보를 한 화면 분량으로 요약해 드릴게요.

(claude 가 fs_read('WIZARD.md') 호출 — 권한 확인 prompt 한 번 뜨면 Yes)

가능한 작업:
  - check        : 환경 의존성 점검
  - deploy <env> : 가상 배포 (dev/staging/prod), 진행 중 API Key 입력 필요
  - status <env> : 가상 서비스 상태
  - cleanup      : /tmp/mdwiz-demo-* 정리

무엇부터 도와드릴까요?
```

## 3. 시나리오 A — `check` (비번 없음)

```
> check 한 번 해줘
```

claude 가 `shell_run("bash scripts/check.sh")` 호출 → 첫 호출이므로 권한 prompt 뜸 →
**`Yes, and don't ask again for mdwiz - shell_run commands in /Users/.../demo-project`** 선택 권장 (이후 매번 안 묻는다).

결과:

```
exit_code : 0
tail_log  : ── demo-project 환경 점검 ──
            [OK] bash     /bin/bash
            [OK] python3  /Users/.../python3
            [OK] tmux     /opt/homebrew/bin/tmux
            결론: 모든 의존성 OK
```

## 4. 시나리오 B — `deploy` (비번 popup 체험)

```
> staging 환경에 deploy 해줘
```

기대 동작:

1. claude 가 plan 표 한 줄 보여줌 → confirm
2. `shell_run("bash scripts/deploy.sh staging")` 실행
3. inner PTY 가 `[staging] 인증 필요 — API Key 요청` 출력 후 `API Key:` 에서 멈춤
4. mdwiz 가 패턴 매칭 → `tmux display-popup` 자동으로 뜸:

   ```
   ┌───────── mdwiz 입력 요청 ──────────────────────┐
   │  cmd    : bash scripts/deploy.sh staging      │
   │  cwd    : /Users/.../demo-project              │
   │  exec   : shell_run                            │
   │  prompt : API Key:                             │
   │                                                │
   │  입력 (Enter 확인, Ctrl+C 취소): ******        │
   └────────────────────────────────────────────────┘
   ```

5. 아무 문자열 (예: `dummy-key-12345`) 입력 → Enter
6. popup 닫힘. PTY stdin 으로 그 값이 주입됨. 스크립트 계속 진행:

   ```
   [staging] 인증 성공 (key length=15)
   [staging] 롤아웃 시뮬 (3 단계)
     rollout step 1 / 3
     rollout step 2 / 3
     rollout step 3 / 3
   [staging] 헬스체크 OK
   [staging] 배포 완료
   ```

7. claude 가 결과 정리해서 chat 에 표시:

   ```
   exit_code : 0
   tail_log  : <PROMPT LINE MASKED>  ← API Key: 라인은 가려짐
               ... (배포 진행 로그) ...
               [staging] 배포 완료
               (로그: /tmp/mdwiz-demo-deploy-staging.log)
   prompts_seen : ["API Key:"]
   ```

   비번은 **chat history 에 안 남는다** — popup 으로만 처리되고 PTY 직결.

## 5. 시나리오 C — `status` (배포 결과 확인)

```
> staging 상태 알려줘
```

```
exit_code : 0
tail_log  : ── [staging] 상태 ──
              service : running (mock)
              uptime  : 1247 sec
              health  : OK

              최근 배포 로그 (마지막 5줄, /tmp/mdwiz-demo-deploy-staging.log):
                | [staging] rollout step 3 / 3
                | [staging] 헬스체크 시뮬
                | [staging] 헬스체크 OK
                | [staging] 배포 완료
```

## 6. 시나리오 D — `cleanup` (마무리)

```
> 데모 정리해줘
```

```
exit_code : 0
tail_log  : ── cleanup ──
              removed: /tmp/mdwiz-demo-deploy-staging.log
              완료
```

## 7. 종료

claude 입력칸에서:

```
/exit
```

자동으로 tmux 세션 종료 → mdwiz 가 helper / socket / 임시 파일 정리 → 터미널 상태 복구 → 원래 셸로 복귀.

다른 터미널에서 정리하려면:

```bash
mdwiz --kill mdwiz-demo-project   # 라벨 명시
mdwiz --kill --all                 # 모든 mdwiz-* 세션 (confirm)
mdwiz --list                       # 떠있는 세션 확인
```

## 8. 요약 — 무엇이 일어났는가

| 보이지 않는 부분 | 어디서 |
|---|---|
| LLM 추론 (도구 호출 결정, 응답 생성) | Anthropic 클라우드 (사용자의 Claude Max 구독 사용) |
| MCP 도구 실행 (shell_run / fs_read) | 로컬 `mdwiz-mcp.py` 자식 프로세스 |
| inner PTY 의 명령 실행 | 로컬 — 사용자 디스크에서 |
| 비번 popup | 로컬 — `mdwiz-helper.py` ↔ `mdwiz-pwprompt.py` (둘 다 로컬) |
| 비번 값의 이동 경로 | popup → unix socket → mdwiz-mcp → PTY stdin (절대 chat 경유 X) |

## 다음 단계 — 자기 프로젝트로

이 데모가 익숙해졌으면 자기 프로젝트의 root 에 `WIZARD.md` 를 만들어 `cd <project> && mdwiz` 한 번 띄우면 된다. claude 가 첫 메시지에서 워크플로우 요약 → 자유 대화로 진행. 필요하면 `MDWIZ_WRITE_GLOBS` 로 fs_write 화이트리스트도 지정.
