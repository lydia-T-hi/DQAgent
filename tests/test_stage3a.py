"""
Stage 3A 독립 테스트 — OpenAI DQ Judge
Stage 2 출력(tests/output/stage2_output.json)을 입력으로 사용합니다.

Usage:
  python tests/test_stage3a.py
  python tests/test_stage3a.py --input tests/output/stage2_output.json
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
OUT_FILE   = os.path.join(OUT_DIR, "stage3a_output.json")

SEV = {"critical": "[!]", "warning": "[~]", "info": "[i]"}


def main():
    parser = argparse.ArgumentParser(description="Stage 3A 테스트 (OPENAI_API_KEY 필요)")
    parser.add_argument("--input", default=IN_DEFAULT, help="Stage 2 출력 파일")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Stage 2 출력 없음: {args.input}")
        print("  먼저 python tests/test_stage2.py 를 실행하세요.")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        stage2_state = json.load(f)

    from agents.stage3a_openai_judge import stage3a_openai_judge

    print("\n" + "=" * 64)
    print("  Stage 3A: OpenAI DQ Judge")
    print("=" * 64)

    result = stage3a_openai_judge.invoke(stage2_state)

    # 이슈 목록
    issues = result.get("issues", [])
    score  = result.get("overall_score", "?")
    print(f"\n[DQ 이슈]  {len(issues)}건  |  종합 점수: {score}/100")
    print("-" * 64)
    if not issues:
        print("  없음")
    else:
        for iss in issues:
            idx_str = f"#{iss.get('record_index')}" if iss.get("record_index") is not None else "전체"
            conf = f" (신뢰도 {iss.get('confidence', '?')})" if iss.get("confidence") is not None else ""
            print(f"  {SEV.get(iss.get('severity'), '[ ]')} [{iss.get('severity','?').upper():<8}] "
                  f"{idx_str:<5} {iss.get('field', '-'):<18} "
                  f"{iss.get('issue_type',''):<28}{conf}")
            print(f"         → {iss.get('description', '')}")

    # 요약
    print(f"\n[OpenAI 종합 의견]")
    print("-" * 64)
    print(" ", result.get("summary", "(없음)"))

    # 저장
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  출력 저장: {OUT_FILE}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
