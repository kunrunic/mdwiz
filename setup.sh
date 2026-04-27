#!/usr/bin/env bash
# setup.sh — mdwiz 를 사용자 환경에 등록 (idempotent, sudo 불필요).
#
# 하는 일:
#   1. 프로젝트 디렉터리 안에 .venv 를 만들고 requirements.txt 설치
#      (Homebrew/PEP 668 환경에서도 안전)
#   2. 사용자 셸 rc 파일 감지 (zsh > bash > fish)
#   3. rc 에 mdwiz/bin 을 PATH 에 추가 (이미 있으면 skip)
#   4. 마지막에 `mdwiz --doctor` 실행해 결과 확인
#
# 사용:
#   bash setup.sh                    # 기본 (.venv 사용)
#   bash setup.sh --no-venv          # venv 안 만들고 시스템 python 에 설치
#   bash setup.sh --rc <path>        # rc 파일 직접 지정
#   bash setup.sh --no-pip           # python 패키지 설치 건너뛰기
#   bash setup.sh --system           # /usr/local/bin 에 symlink 생성 (sudo 필요)
#   bash setup.sh -h | --help

set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$DIR/bin"
VENV_DIR="$DIR/.venv"
MARKER_BEGIN="# mdwiz PATH (added by setup.sh)"

NO_PIP=0
NO_VENV=0
SYSTEM=0
RC=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-pip)   NO_PIP=1; shift ;;
    --no-venv)  NO_VENV=1; shift ;;
    --system)   SYSTEM=1; shift ;;
    --rc)       RC="$2"; shift 2 ;;
    -h|--help)  sed -n '2,19p' "$0"; exit 0 ;;
    *)          echo "✗ unknown option: $1" >&2; exit 1 ;;
  esac
done

[ -d "$BIN_DIR" ] || { echo "✗ bin 디렉터리 없음: $BIN_DIR" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Python mcp 패키지
# ---------------------------------------------------------------------------

echo "[1/4] Python 환경 준비"
PY=$(command -v python3 || echo "")
if [ -z "$PY" ]; then
  echo "  ✗ python3 없음 — Python 3.10+ 가 필요합니다" >&2
  exit 1
fi
echo "  ✓ python3: $PY"

if [ "$NO_VENV" = "1" ]; then
  TARGET_PY="$PY"
  echo "  · --no-venv: 시스템 python 에 직접 설치합니다"
else
  if [ -x "$VENV_DIR/bin/python3" ]; then
    echo "  ✓ venv 이미 존재: $VENV_DIR"
  else
    echo "  → venv 생성: $PY -m venv $VENV_DIR"
    if ! "$PY" -m venv "$VENV_DIR"; then
      echo "  ✗ venv 생성 실패" >&2
      echo "    Linux: 'python3-venv' 패키지가 필요할 수 있습니다 (apt install python3-venv 등)" >&2
      echo "    venv 없이 진행하려면: bash setup.sh --no-venv" >&2
      exit 1
    fi
    echo "  ✓ venv 생성 완료"
  fi
  TARGET_PY="$VENV_DIR/bin/python3"
fi

if "$TARGET_PY" -c "import mcp" 2>/dev/null; then
  echo "  ✓ mcp 패키지 이미 설치됨 ($TARGET_PY)"
else
  if [ "$NO_PIP" = "1" ]; then
    echo "  · mcp 패키지 미설치 (--no-pip 라 설치 건너뜀)"
    echo "    수동: $TARGET_PY -m pip install -r $DIR/requirements.txt"
  else
    echo "  → 설치 시도: $TARGET_PY -m pip install -r $DIR/requirements.txt"
    if "$TARGET_PY" -m pip install -r "$DIR/requirements.txt"; then
      echo "  ✓ 설치 완료"
    else
      echo "  ✗ pip install 실패" >&2
      if [ "$NO_VENV" = "1" ]; then
        echo "    Homebrew 등 PEP 668 환경에서는 venv 모드를 권장합니다 (--no-venv 빼고 다시 실행)" >&2
      fi
      exit 1
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 2. 시스템 전역 symlink (옵션, sudo 필요)
# ---------------------------------------------------------------------------

if [ "$SYSTEM" = "1" ]; then
  echo ""
  echo "[2/4] 시스템 전역 symlink (/usr/local/bin/mdwiz)"
  TARGET="/usr/local/bin/mdwiz"
  if [ -L "$TARGET" ] && [ "$(readlink "$TARGET")" = "$BIN_DIR/mdwiz" ]; then
    echo "  ✓ 이미 등록됨: $TARGET → $BIN_DIR/mdwiz"
  else
    echo "  → sudo ln -sf $BIN_DIR/mdwiz $TARGET"
    if sudo ln -sf "$BIN_DIR/mdwiz" "$TARGET"; then
      echo "  ✓ 등록 완료"
    else
      echo "  ✗ symlink 실패 (sudo 권한 확인)" >&2
    fi
  fi
  echo ""
  echo "[3/4] (--system 모드라 PATH 등록 건너뜀)"
  echo "  · 다른 사용자도 'mdwiz' 명령 사용 가능"
else
  # ---------------------------------------------------------------------------
  # 3. 셸 rc 파일에 PATH 추가
  # ---------------------------------------------------------------------------

  echo ""
  echo "[2/4] (--system 안 줬으므로 sudo 없이 사용자 셸 rc 에 등록)"

  echo ""
  echo "[3/4] 셸 rc 감지 + PATH 등록"

  if [ -z "$RC" ]; then
    case "$(basename "${SHELL:-}")" in
      zsh)
        RC="$HOME/.zshrc"
        ;;
      bash)
        if [ -f "$HOME/.bash_profile" ]; then RC="$HOME/.bash_profile"
        else RC="$HOME/.bashrc"
        fi
        ;;
      fish)
        RC="$HOME/.config/fish/config.fish"
        ;;
      *)
        echo "  ✗ 셸 자동 감지 실패 (\$SHELL=$SHELL)" >&2
        echo "    --rc <path> 로 직접 지정하세요" >&2
        exit 1
        ;;
    esac
  fi
  echo "  → 대상 rc: $RC"

  # 이미 등록돼 있는지 확인 (BIN_DIR 문자열로)
  if [ -f "$RC" ] && grep -Fq "$BIN_DIR" "$RC"; then
    echo "  ✓ 이미 등록됨 ($RC 에 $BIN_DIR 발견)"
  else
    # rc 파일 없으면 생성
    [ -f "$RC" ] || { mkdir -p "$(dirname "$RC")"; touch "$RC"; }

    case "$RC" in
      *config.fish)
        # fish 문법
        {
          echo ""
          echo "$MARKER_BEGIN"
          echo "set -gx PATH \"$BIN_DIR\" \$PATH"
        } >> "$RC"
        ;;
      *)
        # bash / zsh
        {
          echo ""
          echo "$MARKER_BEGIN"
          echo "export PATH=\"$BIN_DIR:\$PATH\""
        } >> "$RC"
        ;;
    esac
    echo "  ✓ $RC 에 추가됨"
    echo "    이번 셸에 즉시 반영하려면:  source $RC"
    echo "    또는 새 터미널 창을 여세요"
  fi
fi

# ---------------------------------------------------------------------------
# 4. doctor 확인
# ---------------------------------------------------------------------------

echo ""
echo "[4/4] mdwiz --doctor"
"$BIN_DIR/mdwiz" --doctor
DOCTOR_RC=$?

echo ""
if [ $DOCTOR_RC -eq 0 ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ✓ mdwiz 설치 완료"
  echo "  사용:  mdwiz <project-dir>   또는   cd <project>; mdwiz"
  if [ "$SYSTEM" = "0" ]; then
    echo "  (PATH 적용:  source $RC  또는 새 터미널)"
  fi
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
  echo "✗ doctor 실패 — 위 출력 확인" >&2
  exit 1
fi
