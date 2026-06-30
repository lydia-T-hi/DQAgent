#!/usr/bin/env python3
"""
file_input_agent 독립 테스트 스크립트
─────────────────────────────────────
Usage:
  python test_file_input.py <file_path> [--batch-size N] [--preview-rows N]

Examples:
  python test_file_input.py sample_input.json
  python test_file_input.py sample_input.csv  --batch-size 2
  python test_file_input.py data/large.parquet --batch-size 1000
"""
import argparse
import json
import sys
from pprint import pformat

# Windows 터미널 UTF-8 출력 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _divider(char="=", width=58):
    print(char * width)


def _print_batch(label: str, batch: list, preview_rows: int):
    print(f"\n{label}  ({len(batch)}건)")
    _divider()
    for row in batch[:preview_rows]:
        print(json.dumps(row, ensure_ascii=False, indent=2, default=str))
    if len(batch) > preview_rows:
        print(f"  ... 외 {len(batch) - preview_rows}건 생략")


def main():
    parser = argparse.ArgumentParser(
        description="file_input_agent 독립 테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "지원 파일 형식: .csv  .tsv  .parquet  .json  .jsonl  .xlsx  .xls\n\n"
            "Examples:\n"
            "  python test_file_input.py sample_input.json\n"
            "  python test_file_input.py sample_input.csv --batch-size 2\n"
        ),
    )
    parser.add_argument("file_path",     help="테스트할 파일 경로")
    parser.add_argument("--batch-size",  type=int, default=2,  help="배치 크기 (기본: 2)")
    parser.add_argument("--preview-rows",type=int, default=2,  help="배치당 미리보기 행 수 (기본: 2)")
    args = parser.parse_args()

    print()
    _divider()
    print("  file_input_agent 테스트")
    _divider()

    try:
        from agents.file_input_agent import file_input_agent
    except ImportError as e:
        print(f"[ERROR] 모듈 로드 실패: {e}")
        print("  pip install duckdb pandas openpyxl 을 실행하세요.")
        sys.exit(1)

    try:
        result = file_input_agent.invoke({
            "file_path":  args.file_path,
            "batch_size": args.batch_size,
        })
    except (FileNotFoundError, ValueError) as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    # ── 결과 요약 ────────────────────────────────────────────
    print()
    _divider()
    print("  결과 요약")
    _divider()
    print(f"  파일        : {result['source_file']}")
    print(f"  전체 레코드 : {result['total_records']:,}건")
    print(f"  배치 수     : {result['batch_count']}개")
    print(f"  배치 크기   : {result['batch_size']}건")
    print(f"  Pipeline ID : {result['pipeline_id']}")

    # ── 배치 미리보기 ────────────────────────────────────────
    batches = result["batches"]
    preview_count = min(3, result["batch_count"])   # 최대 3개 배치 미리보기

    print()
    _divider()
    print("  배치 미리보기")
    _divider()

    for i in range(preview_count):
        _print_batch(f"▶ 배치 {i + 1}", batches[i], args.preview_rows)

    if result["batch_count"] > preview_count:
        print(f"\n  ... 배치 {preview_count + 1} ~ {result['batch_count']} 생략")

    # ── 구조 확인 ────────────────────────────────────────────
    print()
    _divider()
    print("  반환 딕셔너리 키 확인 (파이프라인 연동용)")
    _divider()
    for key, val in result.items():
        if key == "batches":
            print(f"  {key:<14}: list[{len(val)}개 배치]")
        else:
            print(f"  {key:<14}: {val}")

    print()
    _divider()
    print("  테스트 완료")
    _divider()
    print()


if __name__ == "__main__":
    main()
