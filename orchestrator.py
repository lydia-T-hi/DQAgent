"""
DQ Multi-Agent Orchestrator — LCEL 파이프라인 정의

Stage 1 → 2A → 2B → (3A ‖ 3B) → 4

하네스 구조 개선사항:
  - Stage 2A: 결정론적 정규화 (LLM 불필요, 밀리초)
  - Stage 2B: Claude (통계적 이상치 해석만, 필요한 레코드만 호출)
  - ambiguous_indices: 2A → 2B 라우팅 키
  - schemas.py: 스테이지 간 상태 계약
"""
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

load_dotenv()

_SKIP_3A_RESULT = {
    "issues":        [],
    "overall_score": None,
    "summary":       "OpenAI 검증 건너뜀 (--skip-openai)",
}


def build_pipeline(skip_openai: bool = False):
    from agents.stage1_duckdb_agent      import stage1_duckdb_agent
    from agents.stage2a_deterministic    import stage2a_deterministic
    from agents.stage2b_claude_agent     import stage2b_claude_agent
    from agents.stage3a_openai_judge     import stage3a_openai_judge
    from agents.stage3b_numerical_agent  import stage3b_numerical_agent
    from agents.stage4_report_agent      import stage4_report_agent

    stage3a = (
        RunnableLambda(lambda _: _SKIP_3A_RESULT)
        if skip_openai
        else stage3a_openai_judge
    )

    return (
        stage1_duckdb_agent
        | stage2a_deterministic          # 결정론적 정규화 (전체 레코드)
        | stage2b_claude_agent           # Claude 모호성 판단 (이상치만)
        | RunnablePassthrough.assign(
            stage3a=stage3a,
            stage3b=stage3b_numerical_agent,
        )
        | stage4_report_agent
    )


def run(file_path: str, batch_size: int = 500, skip_openai: bool = False) -> dict:
    pipeline = build_pipeline(skip_openai=skip_openai)
    return pipeline.invoke({"file_path": file_path, "batch_size": batch_size})
