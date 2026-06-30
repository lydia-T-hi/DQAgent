"""
Stage 2 독립 테스트 — Claude 의미 기반 전처리
Stage 1 출력(tests/output/stage1_output.json)을 입력으로 사용합니다.

Usage:
  python tests/test_stage2.py
  python tests/test_stage2.py --input tests/output/stage1_output.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR     = os.path.join(ROOT, "tests", "output")
IN_DEFAULT  = os.path.join(OUT_DIR, "stage1_output.json")
OUT_FILE    = os.path.join(OUT_DIR, "stage2_output.json")


def main():
    parser = argparse.ArgumentParser(description="Stage 2 테스트 (ANTHROPIC_API_KEY 필요)")
    parser.add_argument("--input", default=IN_DEFAULT, help="Stage 1 출력 파일")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Stage 1 출력 없음: {args.input}")
        print("  먼저 python tests/test_stage1.py <파일> 을 실행하세요.")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        stage1_state = json.load(f)

    from agents.stage2_claude_agent import stage2_claude_agent

    print("\n" + "=" * 64)
    print("  Stage 2: Claude 의미 기반 전처리")
    print("=" * 64)

    result = stage2_claude_agent.invoke(stage1_state)

    # Changelog 출력
    changelog = result.get("changelog", [])
    print(f"\n[Changelog]  {len(changelog)}건 변경")
    print("-" * 64)
    if not changelog:
        print("  변경 없음")
    else:
        for c in changelog:
            print(f"  [#{c.get('record_index')}] {c.get('field'):<18} "
                  f"{c.get('action'):<12} "
                  f"{str(c.get('original'))[:20]:<22} → {str(c.get('new_value'))[:20]:<22} "
                  f"{c.get('reason', '')}")

    # Interpretations 출력
    interpretations = result.get("interpretations", [])
    print(f"\n[규칙 해석]  {len(interpretations)}건")
    print("-" * 64)
    for i in interpretations:
        print(f"  [{i.get('recommendation','?').upper():<6}] {i.get('field','?'):<18} "
              f"{i.get('rule','?'):<25} {i.get('interpretation','')}")

    # 전처리 결과 미리보기
    preprocessed = result.get("preprocessed_data", [])
    print(f"\n[전처리 결과 미리보기]  {len(preprocessed)}건 중 처음 2건")
    print("-" * 64)
    for rec in preprocessed[:2]:
        print(" ", json.dumps(rec, ensure_ascii=False, default=str))

    # 저장
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  출력 저장: {OUT_FILE}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
