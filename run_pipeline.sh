#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Multi-Agent DQ Pipeline — 실행 훅 스크립트
# 사용법: ./run_pipeline.sh <input.json> [--output-dir <dir>]
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

# ── 색상 정의 ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 사용법 안내 ───────────────────────────────────────────────────
usage() {
  echo -e ""
  echo -e "${BOLD}Usage:${NC}"
  echo -e "  $0 <input.json> [options]"
  echo -e ""
  echo -e "${BOLD}Options:${NC}"
  echo -e "  --output-dir <dir>   보고서 저장 폴더 (기본값: report)"
  echo -e "  -h, --help           도움말 출력"
  echo -e ""
  echo -e "${BOLD}환경변수 (.env 또는 export):${NC}"
  echo -e "  ANTHROPIC_API_KEY    Claude API 키 (필수)"
  echo -e "  OPENAI_API_KEY       OpenAI API 키 (필수)"
  echo -e ""
  echo -e "${BOLD}예시:${NC}"
  echo -e "  $0 sample_input.json"
  echo -e "  $0 data/employees.json --output-dir results"
  echo -e ""
  exit 1
}

# ── .env 파일 로드 ────────────────────────────────────────────────
load_env() {
  local env_file="$SCRIPT_DIR/.env"
  if [[ -f "$env_file" ]]; then
    echo -e "${CYAN}[env]${NC} .env 파일 로드: $env_file"
    while IFS= read -r line || [[ -n "$line" ]]; do
      # 주석과 빈 줄 제외
      [[ -z "$line" || "$line" == \#* ]] && continue
      export "$line" 2>/dev/null || true
    done < "$env_file"
  else
    echo -e "${YELLOW}[env]${NC} .env 파일 없음 — 환경변수에서 키를 읽습니다"
  fi
}

# ── API 키 검증 ───────────────────────────────────────────────────
check_env() {
  local missing=()
  [[ -z "${ANTHROPIC_API_KEY:-}" ]] && missing+=("ANTHROPIC_API_KEY")
  [[ -z "${OPENAI_API_KEY:-}" ]]    && missing+=("OPENAI_API_KEY")

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo -e "${RED}[ERROR]${NC} 환경변수 누락:"
    for var in "${missing[@]}"; do
      echo -e "  ${RED}✗${NC} $var"
    done
    echo -e ""
    echo -e "  .env 파일에 추가하거나 직접 export 하세요:"
    echo -e "    export ANTHROPIC_API_KEY=sk-ant-..."
    echo -e "    export OPENAI_API_KEY=sk-..."
    exit 1
  fi

  echo -e "${GREEN}[env]${NC} API 키: OK"
}

# ── Python 확인 ───────────────────────────────────────────────────
check_python() {
  local python_cmd=""

  if command -v python3 &>/dev/null; then
    python_cmd="python3"
  elif command -v python &>/dev/null; then
    python_cmd="python"
  else
    echo -e "${RED}[ERROR]${NC} Python을 찾을 수 없습니다. Python 3.10 이상을 설치하세요."
    exit 1
  fi

  local version
  version=$("$python_cmd" --version 2>&1)
  echo -e "${GREEN}[env]${NC} Python: $version ($python_cmd)"
  echo "$python_cmd"
}

# ── 의존성 확인 ───────────────────────────────────────────────────
check_deps() {
  local python_cmd="$1"
  if ! "$python_cmd" -c "import langchain" &>/dev/null; then
    echo -e "${YELLOW}[deps]${NC} 패키지 설치 중..."
    "$python_cmd" -m pip install -q -r "$SCRIPT_DIR/requirements.txt"
    echo -e "${GREEN}[deps]${NC} 설치 완료"
  else
    echo -e "${GREEN}[deps]${NC} 패키지: OK"
  fi
}

# ── 인수 파싱 ─────────────────────────────────────────────────────
INPUT_FILE=""
OUTPUT_DIR="report"

[[ $# -eq 0 ]] && usage

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      [[ -z "${2:-}" ]] && { echo -e "${RED}[ERROR]${NC} --output-dir 값이 없습니다"; usage; }
      OUTPUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo -e "${RED}[ERROR]${NC} 알 수 없는 옵션: $1"
      usage
      ;;
    *)
      if [[ -z "$INPUT_FILE" ]]; then
        INPUT_FILE="$1"
      else
        echo -e "${RED}[ERROR]${NC} 인수가 너무 많습니다: $1"
        usage
      fi
      shift
      ;;
  esac
done

[[ -z "$INPUT_FILE" ]] && { echo -e "${RED}[ERROR]${NC} 입력 파일이 필요합니다"; usage; }
[[ ! -f "$INPUT_FILE" ]] && { echo -e "${RED}[ERROR]${NC} 파일을 찾을 수 없습니다: $INPUT_FILE"; exit 1; }

# ── 메인 실행 ─────────────────────────────────────────────────────
echo -e ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}  Multi-Agent DQ Pipeline  │  LangChain LCEL${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════${NC}"

load_env
check_env
PYTHON_CMD=$(check_python)
check_deps "$PYTHON_CMD"

echo -e ""
echo -e "${YELLOW}[pipeline]${NC} 입력  : $INPUT_FILE"
echo -e "${YELLOW}[pipeline]${NC} 출력  : $OUTPUT_DIR/"
echo -e "${YELLOW}[pipeline]${NC} 시작  : $(date '+%Y-%m-%d %H:%M:%S')"
echo -e ""

START_TS=$(date +%s)

cd "$SCRIPT_DIR"
"$PYTHON_CMD" main.py "$INPUT_FILE" --output-dir "$OUTPUT_DIR"
EXIT_CODE=$?

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

echo -e ""
if [[ $EXIT_CODE -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}${BOLD}  완료  │  소요 시간: ${ELAPSED}초  │  보고서: $OUTPUT_DIR/${NC}"
  echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════${NC}"
else
  echo -e "${RED}${BOLD}══════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}${BOLD}  실패  │  종료 코드: $EXIT_CODE${NC}"
  echo -e "${RED}${BOLD}══════════════════════════════════════════════════════════${NC}"
fi

exit $EXIT_CODE
