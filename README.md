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

## 권장 터미널

| 터미널 | Shift+Enter | 비고 |
|---|---|---|
| **iTerm2** | ✓ | **권장** — 확장 키 시퀀스 지원 |
| CMUX | ✓ | 확장 키 시퀀스 지원 |
| macOS Terminal.app | ✗ | Shift+Enter 구분 불가 |
| VSCode 내장 터미널 | ✗ | Shift+Enter 구분 불가 |

> Shift+Enter 줄 바꿈은 터미널 에뮬레이터가 확장 키 시퀀스를 지원해야 동작합니다. mdwiz 자체의 제한이 아닙니다.

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
| `shell_run(cmd, cwd?, env?, timeout_sec?, stream?)` | 셸 명령 실행 (PTY 환경). 비밀번호 프롬프트 자동 감지 → popup. `stream=True` 또는 WIZARD.md frontmatter `stream: true` 매칭 시 tmux split-pane 에 실시간 출력 | `shell_run("git clone ssh://...")` |
| `fs_read(path)` | 파일 읽기 또는 디렉터리 목록 | `fs_read('README.md')` 또는 `fs_read('.')` |
| `fs_write(path, content)` | 파일 쓰기 (화이트리스트 내에서만) | `fs_write('config.json', '...')` |
| `progress(stage, ...)` | 진행 단계 알림 | `progress('clone', '완료')` |

**비밀번호 처리**: `shell_run` 안에서 "Password:", "Passphrase:" 같은 패턴이 나타나면 mdwiz가 자동으로 popup을 띄웁니다. Claude는 비밀번호를 채팅에서 묻지 않습니다.

**실시간 출력 (`stream`)**: 긴 빌드/설치처럼 진행 상황이 중요한 명령은 위쪽 40% 에 split-pane 이 떠서 raw 출력을 `tail -F` 로 보여줍니다. 성공 시 자동 닫힘, 실패 시 사용자 키 입력까지 유지. ⚠️ 사내 스크립트에서 비번을 받는다면 반드시 `read -s VAR` (echo off) 사용 — 그렇지 않으면 입력값이 pane 에 노출됩니다.

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
| Shift+Enter로 줄 바꿈이 안 됨 | 터미널 에뮬레이터가 확장 키 시퀀스를 지원하지 않는 경우입니다. **iTerm2** 사용을 권장합니다. |
| 종료 후 터미널 폰트/입력이 이상함 | `reset` 또는 `stty sane` 입력. mdwiz는 종료 시 터미널 상태를 자동 복구하려 시도합니다. |
| "1 MCP server failed" 에러 | MCP 설정의 Python 절대 경로를 확인. `mdwiz --doctor` 실행해서 의존성 재확인. |
| tmux 세션이 이미 존재한다고 나옴 | `mdwiz --kill`로 기존 세션을 정리한 후 다시 시도. |
| ssh로 접속해서 mdwiz를 띄우면 Claude가 매번 로그인을 요구함 (macOS) | Keychain ACL 문제입니다. → [SSH 환경에서의 Claude 인증](#ssh-환경에서의-claude-인증-macos) |
| `Your organization has disabled Claude subscription access` | `CLAUDE_CODE_OAUTH_TOKEN`이 로컬 세션까지 새어 Keychain 인증을 덮어쓴 경우입니다. → [SSH 환경에서의 Claude 인증](#ssh-환경에서의-claude-인증-macos) |

## SSH 환경에서의 Claude 인증 (macOS)

mdwiz는 tmux 세션 안에서 Claude Code를 띄웁니다(`bin/mdwiz:424`). macOS에서 **ssh로 접속해
mdwiz를 실행하면 Claude가 매번 로그인 화면을 띄우는데**, 로컬 GUI 터미널에서는 멀쩡합니다.

**원인**: Claude Code의 자격증명은 macOS login Keychain(`Claude Code-credentials`)에 저장되는데,
ssh 세션은 GUI와 다른 security session이라 그 항목을 읽지 못합니다. Keychain이 `no-timeout`이어도
마찬가지입니다 — 그건 GUI 세션 한정입니다. ssh 세션 안에서 진단:

```bash
security find-generic-password -s "Claude Code-credentials" -w >/dev/null; echo "exit=$?"
# 36 = errSecInteractionNotAllowed (ACL 거부) → 아래 해결책 적용
# 44 = 항목 없음 / 0 = 정상(다른 원인)
```

**해결**: OAuth 토큰을 **ssh 세션에만** 주입합니다.

```bash
claude setup-token                                  # GUI 터미널에서 발급

umask 077
printf '%s' 'sk-ant-oat01-...' > ~/.claude/ssh-token   # echo 금지 (아래 주의)
chmod 600 ~/.claude/ssh-token
```

`~/.zshenv`에 추가:

```zsh
# 인바운드 ssh 세션에서만 Claude Code 토큰을 주입한다.
# 로컬에는 주입하지 않는다 — 로컬은 keychain 으로 정상 인증되며,
# 여기서 export 하면 그 인증을 덮어써 organization 오류가 난다.
if [[ -n "${SSH_CONNECTION:-}" && -r "$HOME/.claude/ssh-token" ]]; then
  export CLAUDE_CODE_OAUTH_TOKEN="$(<"$HOME/.claude/ssh-token")"
fi
```

검증:

```zsh
zsh -c 'echo "local=[${CLAUDE_CODE_OAUTH_TOKEN:-empty}]"'                 # empty 여야 정상
SSH_CONNECTION="x" zsh -c 'echo "ssh=[${CLAUDE_CODE_OAUTH_TOKEN:0:12}]"'  # 토큰이 나와야 정상
```

**주의사항**

- **토큰을 `~/.zshenv`에 무조건 `export` 하지 마세요.** ssh뿐 아니라 로컬 세션 전체로 퍼져
  Keychain 인증을 덮어쓰고 `Your organization has disabled Claude subscription access`를 냅니다.
  토큰이 만료되면 로컬까지 같이 죽습니다. 반드시 위처럼 `SSH_CONNECTION` 가드를 씁니다.
- **`echo` 대신 `printf`**. `echo '%s' '<토큰>'`은 포맷을 해석하지 않아 파일에 `%s <토큰>`이
  그대로 들어가고 개행까지 붙어 인증이 깨집니다. `wc -c < ~/.claude/ssh-token`이 토큰 길이와
  정확히 같아야 정상입니다.
- **토큰을 바꾸거나 지운 뒤에는 `tmux kill-server` + 터미널 재시작.** tmux 서버는 기동 시점의
  환경을 죽을 때까지 유지하며 새 pane마다 주입합니다. 이미 열린 셸도 자기 env에 옛 값을
  들고 있습니다. 둘 다 정리하지 않으면 파일을 고쳐도 옛 토큰이 계속 쓰입니다.
  확인: `tmux show-environment -g | grep CLAUDE_CODE_OAUTH`
- Claude 배너가 `Claude API`면 토큰 모드, 계정 표시가 뜨면 구독(Keychain) 모드입니다.
  로컬에서 `Claude API`가 보이면 토큰이 새고 있다는 신호입니다.

> 같은 증상을 tmux/ssh 관점에서 더 자세히 다룬 문서: `claude-bridge/docs/troubleshooting.md`

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
