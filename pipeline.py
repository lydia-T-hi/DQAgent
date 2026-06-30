"""
전체 DQ 파이프라인 — Stage 1~4 LCEL 조합
Usage:
  python pipeline.py sample_input.csv
  python pipeline.py sample_input.jsonl --batch-size 2
"""
import argparse
import sys

from dotenv import load_dotenv
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()


def build_pipeline():
    from agents.stage1_duckdb_agent     import stage1_duckdb_agent
    from agents.stage2_claude_agent     import stage2_claude_agent
    from agents.stage3a_openai_judge    import stage3a_openai_judge
    from agents.stage3b_numerical_agent import stage3b_numerical_agent
    from agents.stage4_report_agent     import stage4_report_agent

    return (
        stage1_duckdb_agent
        | stage2_claude_agent
        | RunnablePassthrough.assign(
            stage3a=stage3a_openai_judge,
            stage3b=stage3b_numerical_agent,
        )
        | stage4_report_agent
    )


def main():
    parser = argparse.ArgumentParser(description="DQ 파이프라인 (Stage 1~4 전체 실행)")
    parser.add_argument("file_path",    help="입력 파일 경로")
    parser.add_argument("--batch-size", type=int, default=500, help="배치 크기 (기본: 500)")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  DQ Pipeline: Stage 1 → 2 → (3A ‖ 3B) → 4")
    print("=" * 64)

    pipeline = build_pipeline()
    result = pipeline.invoke({
        "file_path":  args.file_path,
        "batch_size": args.batch_size,
    })

    print("\n" + "=" * 64)
    print("  파이프라인 완료")
    print("=" * 64)
    scores = result.get("scores", {})
    grade  = result.get("grade", "?")
    print(f"  최종 DQ 점수 : {scores.get('weighted_final', '?')}/100  [{grade}등급]")
    print(f"  보고서       : {result.get('output_path')}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
