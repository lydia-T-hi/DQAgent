"""
Stage 3B 독립 테스트 — Python/DuckDB 수치 검증 + 환각 탐지
API 키 불필요. Stage 2 출력을 입력으로 사용합니다.

Usage:
  python tests/test_stage3b.py
  python tests/test_stage3b.py --input tests/output/stage2_output.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR    = os.path.join(ROOT, "tests", "output")
IN_DEFAULT = os.path.join(OUT_DIR, "stage2_output.json")
OUT_FILE   = os.path.join(OUT_DIR, "stage3b_output.json")

SEV = {"critical": "[!]", "warning": "[~]", "info": "[i]"}


def main():
    parser = argparse.ArgumentParser(description="Stage 3B 테스트 (API 키 불필요)")
    parser.add_argument("--input", default=IN_DEFAULT, help="Stage 2 출력 파일")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Stage 2 출력 없음: {args.input}")
        print("  먼저 python tests/test_stage2.py 를 실행하세요.")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        stage2_state = json.load(f)

    from agents.stage3b_numerical_agent import stage3b_numerical_agent

    print("\n" + "=" * 64)
    print("  Stage 3B: 수치 검증 + 환각 탐지  (LLM 없음)")
    print("=" * 64)

    result = stage3b_numerical_agent.invoke(stage2_state)

    # 환각
    hallucinations = result.get("hallucinations", [])
    print(f"\n[환각 탐지]  {len(hallucinations)}건")
    print("-" * 64)
    if not hallucinations:
        print("  없음")
    else:
        for h in hallucinations:
            print(f"  [!] record#{h.get('record_index')}  {h.get('field'):<18}  "
                  f"생성값={h.get('generated_value')}  원본={h.get('original_value')}")
            print(f"       {h.get('reason')}")

    # 수치 위반
    num_v = result.get("numerical_violations", [])
    print(f"\n[수치 검증 위반]  {len(num_v)}건")
    print("-" * 64)
    if not num_v:
        print("  없음")
    else:
        for v in num_v:
            print(f"  {SEV.get(v.get('severity'), '[ ]')} [{v.get('severity','?').upper():<8}] "
                  f"{v.get('field'):<18} {v.get('rule'):<25} {v.get('detail')}")

    # 드리프트
    drifts = result.get("value_drifts", [])
    print(f"\n[값 드리프트]  {len(drifts)}건")
    print("-" * 64)
    if not drifts:
        print("  없음")
    else:
        for d in drifts:
            print(f"  {d.get('field'):<18} {d.get('pct')}% 변경  ({d.get('changed')}/{d.get('total')}건)  "
                  f"{d.get('detail')}")

    # 요약
    s = result.get("summary", {})
    print(f"\n[요약]  환각={s.get('hallucination_count',0)}  "
          f"수치위반={s.get('numerical_violation_count',0)}  "
          f"드리프트={s.get('drift_count',0)}")

    # 저장
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  출력 저장: {OUT_FILE}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
