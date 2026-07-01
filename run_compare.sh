#!/usr/bin/env bash
# ============================================================
#  DQ Agent 실행 + Before/After 비교 + 시간 비교
#
#  Usage:
#    ./run_compare.sh <파일>
#    ./run_compare.sh customer_data_quality_test_50.json
#    ./run_compare.sh data.jsonl --batch-size 200
# ============================================================
set -euo pipefail
export PYTHONIOENCODING=utf-8

# ── 색상 ────────────────────────────────────────────────────
BOLD='\033[1m'
CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
DIM='\033[2m'
RST='\033[0m'

# TTY 여부 확인 (파이프 출력 시 색상 제거)
if [ -t 1 ]; then USE_COLOR=1; else USE_COLOR=0; fi
col() { [ "$USE_COLOR" -eq 1 ] && echo -e "${1}${2}${RST}" || echo "$2"; }

# ── 인자 처리 ────────────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo "Usage: ./run_compare.sh <파일> [--batch-size N] [--skip-openai]"
    exit 1
fi

FILE="$1"
shift
EXTRA_ARGS="${*}"
BATCH_SIZE=100

# --batch-size 파싱
for arg in "$@"; do
    if [[ "$arg" =~ ^[0-9]+$ ]] && [[ "${prev_arg:-}" == "--batch-size" ]]; then
        BATCH_SIZE="$arg"
    fi
    prev_arg="$arg"
done

# 파일 존재 확인
if [ ! -f "$FILE" ]; then
    col "$RED" "[ERROR] 파일 없음: $FILE"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Python 확인 ──────────────────────────────────────────────
PYTHON=""
for cmd in python python3; do
    if command -v "$cmd" &>/dev/null; then PYTHON="$cmd"; break; fi
done
[ -z "$PYTHON" ] && { col "$RED" "[ERROR] Python을 찾을 수 없습니다."; exit 1; }

# ── 헤더 ─────────────────────────────────────────────────────
echo ""
col "$CYAN" "════════════════════════════════════════════════════════════════════════════════"
col "$BOLD" "  DQ Agent  —  실행 + Before/After 비교 + 시간 비교"
col "$CYAN" "════════════════════════════════════════════════════════════════════════════════"
echo -e "  파일     : $FILE"
echo -e "  배치크기 : $BATCH_SIZE"
echo ""

# ════════════════════════════════════════════════════════════════
# STEP 1 — DQ Agent 실행
# ════════════════════════════════════════════════════════════════
col "$CYAN" "── [1/3] DQ Agent 실행 ────────────────────────────────────────────────────────"
echo ""

T_AGENT_START=$($PYTHON -c "import time; print(time.time())")

"$PYTHON" "$SCRIPT_DIR/main.py" "$FILE" \
    --batch-size "$BATCH_SIZE" \
    --skip-openai \
    $EXTRA_ARGS

T_AGENT_END=$($PYTHON -c "import time; print(time.time())")
AGENT_SEC=$($PYTHON -c "print(round($T_AGENT_END - $T_AGENT_START, 1))")

echo ""
col "$GREEN" "  Agent 소요: ${AGENT_SEC}초"
echo ""

# ── 최신 보고서 파일 탐색 ────────────────────────────────────
REPORT=$($PYTHON - <<'PYEOF'
import glob, os
files = sorted(glob.glob("report/*.json"), key=os.path.getmtime, reverse=True)
print(files[0].replace("\\", "/") if files else "")
PYEOF
)
REPORT="${REPORT//$'\r'/}"   # Windows \r 제거

if [ -z "$REPORT" ]; then
    col "$RED" "[ERROR] report/ 디렉토리에 보고서가 없습니다."
    exit 1
fi
echo -e "  보고서    : $REPORT"
echo ""

# ════════════════════════════════════════════════════════════════
# STEP 2 — Pandas ROI 분석 실행
# ════════════════════════════════════════════════════════════════
col "$CYAN" "── [2/3] Pandas ROI 분석 실행 ─────────────────────────────────────────────────"
echo ""

EXPORT_FILE="roi_result_$(date +%Y%m%d_%H%M%S).xlsx"

T_PD_START=$($PYTHON -c "import time; print(time.time())")

"$PYTHON" "$SCRIPT_DIR/tools/roi_pandas.py" \
    "$FILE" \
    "$REPORT" \
    --hourly-rate 30000 \
    --export "$EXPORT_FILE"

T_PD_END=$($PYTHON -c "import time; print(time.time())")
PANDAS_SEC=$($PYTHON -c "print(round($T_PD_END - $T_PD_START, 1))")

echo ""
col "$GREEN" "  Pandas 소요: ${PANDAS_SEC}초  /  Excel: $EXPORT_FILE"
echo ""

# ════════════════════════════════════════════════════════════════
# STEP 3 — Before/After 비교 + 시간 비교 표
# ════════════════════════════════════════════════════════════════
col "$CYAN" "── [3/3] 비교 표 ───────────────────────────────────────────────────────────────"
echo ""

"$PYTHON" "$SCRIPT_DIR/tools/compare_table.py" \
    "$FILE" \
    "$REPORT" \
    --agent-sec "$AGENT_SEC" \
    --pandas-sec "$PANDAS_SEC" \
    --max-rows 50

# ════════════════════════════════════════════════════════════════
# 완료
# ════════════════════════════════════════════════════════════════
TOTAL_SEC=$($PYTHON -c "print(round($AGENT_SEC + $PANDAS_SEC, 1))")

col "$CYAN" "════════════════════════════════════════════════════════════════════════════════"
col "$BOLD" "  완료"
echo -e "  Agent       : ${AGENT_SEC}초"
echo -e "  Pandas 분석 : ${PANDAS_SEC}초"
echo -e "  합계        : ${TOTAL_SEC}초"
echo -e "  보고서      : $REPORT"
echo -e "  Excel       : $EXPORT_FILE"
col "$CYAN" "════════════════════════════════════════════════════════════════════════════════"
echo ""
