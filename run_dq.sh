#!/usr/bin/env bash
# DQ Multi-Agent Pipeline — Bash 실행 훅 (Git Bash / WSL / Mac)
# Usage:
#   ./run_dq.sh sample_input.csv
#   ./run_dq.sh sample_input.jsonl --batch-size 100
#   ./run_dq.sh sample_input.csv --skip-openai

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}  DQ Multi-Agent Pipeline${NC}"
echo -e "${CYAN}================================================================${NC}"

# .env 로드
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
    echo -e "  ${GREEN}[OK] .env 로드 완료${NC}"
else
    echo -e "  ${YELLOW}[!] .env 파일 없음 — API 키를 환경변수로 직접 설정하세요${NC}"
fi

# 인자 확인
if [ $# -eq 0 ]; then
    echo -e "  ${RED}[ERROR] 파일 경로가 필요합니다.${NC}"
    echo "  사용법: ./run_dq.sh <파일경로> [--batch-size N] [--skip-openai]"
    exit 1
fi

# Python 확인
PYTHON=""
for cmd in python python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}[ERROR] Python을 찾을 수 없습니다.${NC}"
    exit 1
fi

PY_VER=$($PYTHON --version 2>&1)
echo -e "  ${GREEN}[OK] $PY_VER${NC}"

# 필수 패키지 확인
if ! $PYTHON -c "import duckdb, pandas, langchain_core, dotenv" 2>/dev/null; then
    echo -e "  ${RED}[ERROR] 필수 패키지가 없습니다. 아래 명령을 실행하세요:${NC}"
    echo "    pip install -r requirements.txt"
    exit 1
fi
echo -e "  ${GREEN}[OK] 패키지 확인 완료${NC}"
echo -e "${CYAN}================================================================${NC}"
echo ""

# 실행
export PYTHONIOENCODING=utf-8
START=$(date +%s)

set +e
$PYTHON "$SCRIPT_DIR/main.py" "$@"
EXIT_CODE=$?
set -e

END=$(date +%s)
ELAPSED=$((END - START))

echo ""
echo -e "${CYAN}================================================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}소요 시간: ${ELAPSED}초${NC}"
else
    echo -e "  ${RED}[ERROR] 실행 실패 (종료코드: $EXIT_CODE)${NC}"
fi
echo -e "${CYAN}================================================================${NC}"
echo ""

exit $EXIT_CODE
