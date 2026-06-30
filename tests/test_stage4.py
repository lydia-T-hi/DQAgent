"""
Stage 4 독립 테스트 — 합의 기반 최종 보고서
API 키 불필요. Stage 2 + Stage 3A + Stage 3B 출력을 합쳐 실행합니다.

Usage:
  python tests/test_stage4.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = os.path.join(ROOT, "tests", "output")

REQUIRED = {
    "stage2": os.path.join(OUT_DIR, "stage2_output.json"),
    "stage3a": os.path.join(OUT_DIR, "stage3a_output.json"),
    "stage3b": os.path.join(OUT_DIR, "stage3b_output.json"),
}

GRADE_COLOR = {"A": "우수", "B": "양호", "C": "주의", "D": "위험"}


def main():
    # 입력 파일 확인
    missing = [k for k, p in REQUIRED.items() if not os.path.exists(p)]
    if missing:
        print("[ERROR] 아래 단계를 먼저 실행하세요:")
        for k in missing:
            step = k.replace("stage", "")
            print(f"  python tests/test_stage{step}.py")
        sys.exit(1)

    # 로드
    with open(REQUIRED["stage2"],  encoding="utf-8") as f:
        stage2_state = json.load(f)
    with open(REQUIRED["stage3a"], encoding="utf-8") as f:
        stage3a_result = json.load(f)
    with open(REQUIRED["stage3b"], encoding="utf-8") as f:
        stage3b_result = json.load(f)

    # 합성 state 구성
    full_state = {
        **stage2_state,
        "stage3a": stage3a_result,
        "stage3b": stage3b_result,
    }

    from agents.stage4_report_agent import stage4_report_agent

    print("\n" + "=" * 64)
    print("  Stage 4: 합의 기반 최종 보고서")
    print("=" * 64)

    result = stage4_report_agent.invoke(full_state)

    # 점수
    scores = result.get("scores", {})
    grade  = result.get("grade", "?")
    print(f"\n[DQ 점수]")
    print("-" * 64)
    print(f"  DuckDB 규칙  (40%)  : {scores.get('duckdb_rules', '?')}/100")
    print(f"  OpenAI 판단  (35%)  : {scores.get('openai_judge', '?')}/100")
    print(f"  수치 검증    (25%)  : {scores.get('numerical', '?')}/100")
    print(f"  ─────────────────────────────")
    print(f"  최종 가중 점수       : {scores.get('weighted_final', '?')}/100  [{grade}등급 — {GRADE_COLOR.get(grade,'?')}]")

    # 합의 요약
    cs = result.get("consensus_summary", {})
    print(f"\n[합의 요약]")
    print("-" * 64)
    print(f"  Critical 필드 : {cs.get('critical_fields', 0)}")
    print(f"  Warning 필드  : {cs.get('warning_fields', 0)}")
    print(f"  Pass 필드     : {cs.get('pass_fields', 0)}")
    print(f"  총 발견 건수  : {cs.get('total_findings', 0)}")

    print(f"\n  보고서 저장: {result.get('output_path')}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
