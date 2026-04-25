# mdwiz

**마크다운 기반 AI 워크플로우 런너.** 어떤 프로젝트에서든 `mdwiz` 명령으로 Claude Code를 터미널에 띄우면, 프로젝트 루트의 `WIZARD.md` 가이드를 자동으로 읽고 사용자의 요청에 따라 워크플로우를 진행합니다. 비밀번호가 필요하면 팝업 대화상자가 자동으로 나타나 입력값이 채팅 기록에 남지 않도록 처리합니다.

> 한 내부 설치 마법사의 필요에서 시작해 일반화되었습니다.

## 무엇을 하나요

mdwiz는 다음을 자동화합니다:

1. **tmux 세션 생성** — Claude Code를 프로젝트 디렉터리에서 실행합니다.
2. **MCP 도구 제공** — 셸 명령 실행(`shell_run`), 파일 읽기/쓰기(`fs_read`/`fs_write`), 진행 상황 알림(`progress`).
3. **비밀번호 팝업** — `git clone` 등에서 비밀번호를 묻으면 tmux 팝업이 자동으로 나타나 입력값을 마스킹합니다 (채팅 기록 안 남음).
4. **네이티브 TUI** — Claude의 기본 터미널 UI를 그대로 사용합니다 (미러링 없음 = 지연 없음).

## 설치

**한 번에 끝내기 (권장)**:

```bash
# 의존성 확인 + Python 패키지 설치 + 셸 rc 에 PATH 추가 + doctor 까지 자동
bash setup.sh

# 옵션:
#   --no-pip       Python 패키지 설치 건너뛰기
#   --rc <path>    rc 파일 직접 지정 (자동 감지 외)
#   --system       /usr/local/bin 에 symlink (sudo 필요, 다른 사용자도 사용 가능)
```

**수동으로 하려면**:

```bash
# 의존성 확인:
#   - claude (Claude Code CLI)
#   - tmux
#   - python3 + pip

# 1. Python 의존성 설치
python3 -m pip install -r requirements.txt

# 2. bin/ 을 PATH 에 추가 (또는 홈 bin 폴더에 symlink)
export PATH="$HOME/mdwiz/bin:$PATH"

# 3. 의존성 확인
mdwiz --doctor
```

## 빠른 시작

```bash
cd /your/project          # WIZARD.md 또는 다른 마크다운 가이드가 있는 디렉터리
mdwiz                     # tmux 세션 시작, Claude TUI 표시
```

tmux 세션 안에서 Claude와 자연스럽게 대화하면 됩니다.

**파일 쓰기 권한 활성화** (기본값: 비활성화):

```bash
MDWIZ_WRITE_GLOBS='manifests/*.yaml,scripts/*.sh' mdwiz
```

**다른 터미널에서 세션 종료**:

```bash
mdwiz --kill
```

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `MDWIZ_ROOT` | 현재 디렉터리 | 프로젝트 루트 (Claude의 작업 디렉터리이자 파일 읽기 기본 경로) |
| `MDWIZ_WRITE_GLOBS` | (비활성화) | 쉼표로 구분된 glob 패턴 — `fs_write`로 쓸 수 있는 파일 범위 |
| `MDWIZ_READ_GLOBS` | (없음) | 콜론으로 구분된 추가 읽기 경로 (프로젝트 루트 외 영역도 포함 가능) |
| `MDWIZ_TMUX_SESSION` | `mdwiz-<project-name>` | tmux 세션 이름 (여러 프로젝트 동시 실행 시 구분) |
| `MDWIZ_PYTHON` | `python3` (PATH 에서 검색) | 사용할 Python 인터프리터 |
| `MDWIZ_SYSTEM_PROMPT` | (없음) | 기본 시스템 프롬프트에 추가할 텍스트 |
| `MDWIZ_GUIDE` | `$MDWIZ_ROOT/WIZARD.md` | 워크플로우 가이드 파일 위치 |

## WIZARD.md

프로젝트 루트의 선택적 마크다운 파일로, **이 프로젝트에서 mdwiz로 자주 할 작업의 절차**를 정의합니다:

- 프로젝트가 무엇인지
- 설치, 빌드, 배포 같은 주요 작업의 단계
- 각 작업에서 사용자에게 물어볼 정보 (디렉터리, 옵션 등)
- 주의사항

**없으면**: mdwiz 실행 시 Claude가 자동으로 프로젝트의 기존 문서(`README*`, `CLAUDE*`, 다른 `*.md`)를 읽어 WIZARD.md 초안을 제안합니다.

**좋은 구조 예**:

```markdown
# 프로젝트명 WIZARD

이 프로젝트는 [목적].

## 자주 할 작업

### 1. 개발 환경 설정
- 단계 1: ...
- 단계 2: ...

### 2. 빌드 및 테스트
- 단계 1: ...
```

## MCP 도구

| 도구 | 용도 | 예 |
|---|---|---|
| `shell_run(cmd, cwd?, env?, timeout_sec?)` | 셸 명령 실행 (PTY 환경). 비밀번호 프롬프트 자동 감지 → popup | `shell_run("git clone ssh://...")` |
| `fs_read(path)` | 파일 읽기 또는 디렉터리 목록 | `fs_read('README.md')` 또는 `fs_read('.')` |
| `fs_write(path, content)` | 파일 쓰기 (화이트리스트 내에서만) | `fs_write('config.json', '...')` |
| `progress(stage, ...)` | 진행 단계 알림 | `progress('clone', '완료')` |

**비밀번호 처리**: `shell_run` 안에서 "Password:", "Passphrase:" 같은 패턴이 나타나면 mdwiz가 자동으로 popup을 띄웁니다. Claude는 비밀번호를 채팅에서 묻지 않습니다.

## 비밀번호 팝업 동작

1. `shell_run`이 내부 PTY에서 "Password:" 같은 프롬프트를 감지합니다.
2. 유닉스 소켓을 통해 helper 프로세스에 요청을 보냅니다.
3. Helper가 `tmux display-popup -E`로 팝업을 띄웁니다.
4. 사용자가 팝업 안에서 입력합니다 (입력값은 `*` 마스크로 표시).
5. 입력값이 명령의 stdin으로 주입되고 명령이 계속 진행됩니다.
6. 채팅 기록에는 아무것도 남지 않습니다.

## 아키텍처

```
┌────────────────┐
│ user terminal  │
└────────┬───────┘
         │ tmux attach
┌────────▼─────────────────────────┐
│ tmux session (mdwiz-<name>)      │
│  -> claude --mcp-config ... ─────┼──┐
└──────────────────────────────────┘  │ stdio MCP
                                      ▼
                              ┌──────────────────────┐
                              │ mdwiz-mcp.py         │
                              │   shell_run          │
                              │   fs_read / fs_write │
                              │   progress           │
                              └──────────┬───────────┘
                                         │ inner PTY
                                         ▼
                                command (git, bash, ...)
                                         │
                                   on prompt detect
                                         │
                              ┌──────────▼───────────┐
                              │ mdwiz-helper.py      │  unix socket
                              │ (sideband server)    │◄────────────
                              └──────────┬───────────┘
                                         │ tmux display-popup
                                         ▼
                              ┌──────────────────────┐
                              │ popup (masked input) │
                              └──────────────────────┘
```

## 단축키 및 종료

- **detach**: Ctrl+B d (Claude 세션은 백그라운드에서 유지)
- **종료**: Claude 안에서 `/exit` 명령 (mdwiz도 자동 종료) 또는 다른 터미널에서 `mdwiz --kill`
- **터미널 스크롤**: 마우스 트랙패드/휠 사용 (터미널 기본 스크롤백, 전체 history 보존)
- **복사 모드**: Ctrl+B [ (vi 키 지원) → q로 종료

## 트러블슈팅

| 문제 | 해결책 |
|---|---|
| Shift+Enter로 줄 바꿈이 안 됨 | `extended-keys` 설정이 문제일 수 있음. mdwiz를 재시작하세요. |
| 종료 후 터미널 폰트/입력이 이상함 | `reset` 또는 `stty sane` 입력. mdwiz는 종료 시 터미널 상태를 자동 복구하려 시도합니다. |
| "1 MCP server failed" 에러 | MCP 설정의 Python 절대 경로를 확인. `mdwiz --doctor` 실행해서 의존성 재확인. |
| tmux 세션이 이미 존재한다고 나옴 | `mdwiz --kill`로 기존 세션을 정리한 후 다시 시도. |

## 파일 구조

```
mdwiz/
├── README.md              ← 이 문서
├── requirements.txt       ← Python 의존성
├── bin/
│   ├── mdwiz              ← 메인 진입점 (bash)
│   ├── mdwiz-mcp.py       ← MCP 서버 (stdio)
│   ├── mdwiz-helper.py    ← 팝업 헬퍼 (socket)
│   ├── mdwiz-pwprompt.py  ← 팝업 UI (마스크 입력)
│   └── mdwiz-system.md    ← 기본 시스템 프롬프트
└── examples/
    └── ...                ← 사용 예제
```

## 라이선스

MIT
