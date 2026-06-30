"""Stage 2A 결정론적 정규화 단독 테스트"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

INPUT  = os.path.join(os.path.dirname(__file__), "output", "stage1_output.json")
OUTPUT = os.path.join(os.path.dirname(__file__), "output", "stage2a_output.json")

from agents.stage2a_deterministic import _run

def main():
    print("=" * 60)
    print("  Stage 2A: 결정론적 정규화")
    print("=" * 60)

    with open(INPUT, encoding="utf-8") as f:
        state = json.load(f)

    result = _run(state)

    cl = result["changelog"]
    am = result["ambiguous_indices"]

    print(f"\n[Changelog]  {len(cl)}건")
    print("-" * 60)
    for c in cl:
        orig = str(c["original"])[:20]
        new  = str(c["new_value"])[:20] if c["new_value"] is not None else "null"
        print(f"  [#{c['record_index']}][{c['action']:<9}] {c['field']:<16} {orig:>22} → {new}")
        print(f"       ↳ {c['reason']}")

    print(f"\n[2B 대상(이상치)] {len(am)}건: {am}")

    print(f"\n[처리 후 레코드 미리보기]  처음 2건")
    print("-" * 60)
    for rec in result["preprocessed_data"][:2]:
        print(" ", json.dumps(rec, ensure_ascii=False, default=str))

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  출력 저장: {OUTPUT}")
    print("=" * 60)

if __name__ == "__main__":
    main()
