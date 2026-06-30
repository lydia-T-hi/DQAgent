"""
Stage 1 독립 테스트 — DuckDB 프로파일링 + 규칙 검증

Usage:
  python tests/test_stage1.py sample_input.csv
  python tests/test_stage1.py sample_input.jsonl --batch-size 2
  python tests/test_stage1.py sample_input.xlsx
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR  = os.path.join(ROOT, "tests", "output")
OUT_FILE = os.path.join(OUT_DIR, "stage1_output.json")

SEV = {"critical": "[!]", "warning": "[~]", "info": "[i]"}


def main():
    parser = argparse.ArgumentParser(description="Stage 1 테스트")
    parser.add_argument("file_path", help="입력 파일 (csv/jsonl/parquet/xlsx 등)")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    from agents.stage1_duckdb_agent import stage1_duckdb_agent

    print("\n" + "=" * 64)
    print("  Stage 1: DuckDB 프로파일링 + 규칙 검증")
    print("=" * 64)

    result = stage1_duckdb_agent.invoke({
        "file_path":  args.file_path,
        "batch_size": args.batch_size,
    })

    # 프로파일
    print("\n[프로파일]")
    print("-" * 64)
    for field, p in result["profile"].items():
        null  = f"NULL {p['null_pct']}%"
        dist  = f"DISTINCT {p['distinct_count']}"
        extra = ""
        if "avg" in p:
            extra = f"  min={p['min']} avg={p['avg']} max={p['max']} std={p.get('stddev')}"
        tops = str(p.get("top_values", []))
        print(f"  {field:<18} {p['type']:<14} {null:<12} {dist:<14}{extra}")
        print(f"    top_values: {tops}")

    # 위반
    s = result["rule_summary"]
    print(f"\n[규칙 위반]  total={s['total']}  critical={s['critical']}  warning={s['warning']}  info={s['info']}")
    print("-" * 64)
    if not result["rule_violations"]:
        print("  없음")
    else:
        for v in result["rule_violations"]:
            ex = f"  예시={v['examples'][:2]}" if v.get("examples") else ""
            print(f"  {SEV.get(v['severity'], '[ ]')} [{v['severity'].upper():<8}] "
                  f"{v['field']:<18} {v['rule']:<25} {v['detail']}{ex}")

    # 데이터 미리보기
    print(f"\n[데이터 미리보기]  배치 1, 처음 2건")
    print("-" * 64)
    for rec in result["data"][0][:2]:
        print(" ", json.dumps(rec, ensure_ascii=False, default=str))

    # 저장
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  출력 저장: {OUT_FILE}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
