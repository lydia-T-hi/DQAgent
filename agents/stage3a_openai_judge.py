"""
Stage 3A: OpenAI — 의미 기반 DQ Judge
Claude와 독립적 관점으로 데이터 품질을 판단합니다.
RunnableParallel에서 호출되므로 state를 받아 자신의 판단 결과만 반환합니다.
"""
import json
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

load_dotenv()

_SYSTEM = """\
당신은 데이터 품질 검사 전문가입니다.
전처리된 데이터와 원본 통계 프로파일을 바탕으로 독립적인 DQ 판단을 수행합니다.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "issues": [
    {{
      "record_index": <정수 또는 null (전체 적용)>,
      "field": <필드명 또는 null>,
      "severity": "critical|warning|info",
      "issue_type": <문제 유형 예: "semantic_inconsistency", "domain_violation", "data_accuracy">,
      "description": <문제 설명>,
      "confidence": <0.0 ~ 1.0>
    }}
  ],
  "overall_score": <0 ~ 100 정수, DQ 종합 점수>,
  "summary": <전반적인 데이터 품질 평가 한 문단>
}}
"""

_HUMAN = """\
## 원본 통계 프로파일
{profile_summary}

## 전처리된 데이터 ({record_count}건)
{preprocessed_json}

## 규칙 기반 위반 참고 (DuckDB Stage 1 결과)
{violations_summary}

위 데이터의 의미 기반 품질을 독립적으로 판단하고 JSON으로 반환하세요.
"""


def _build_chain():
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=os.environ.get("OPENAI_API_KEY"),
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human",  _HUMAN),
    ])
    return prompt | llm | JsonOutputParser()


def _profile_summary(profile: dict) -> str:
    lines = []
    for field, p in profile.items():
        base = f"  {field}: null={p['null_pct']}%, distinct={p['distinct_count']}"
        if "avg" in p:
            base += f", range=[{p['min']}, {p['max']}]"
        lines.append(base)
    return "\n".join(lines)


def _violations_summary(violations: list) -> str:
    if not violations:
        return "  없음"
    return "\n".join(
        f"  [{v['severity'].upper()}] {v['field']}.{v['rule']}: {v['detail']}"
        for v in violations
    )


def _run(state: dict) -> dict:
    print("[Stage3A-OpenAI] DQ 판단 시작")

    preprocessed = state.get("preprocessed_data", [])
    print(f"[Stage3A-OpenAI] 판단 레코드: {len(preprocessed)}건")

    chain = _build_chain()
    result = chain.invoke({
        "profile_summary":    _profile_summary(state["profile"]),
        "preprocessed_json":  json.dumps(preprocessed, ensure_ascii=False, indent=2, default=str),
        "violations_summary": _violations_summary(state.get("rule_violations", [])),
        "record_count":       len(preprocessed),
    })

    issues = result.get("issues", [])
    score  = result.get("overall_score", 0)
    crit   = sum(1 for i in issues if i["severity"] == "critical")
    warn   = sum(1 for i in issues if i["severity"] == "warning")
    print(f"[Stage3A-OpenAI] 완료 — 이슈 {len(issues)}건 (C:{crit} W:{warn}), 점수 {score}")

    return {
        "issues":        issues,
        "overall_score": score,
        "summary":       result.get("summary", ""),
    }


stage3a_openai_judge = RunnableLambda(_run)
