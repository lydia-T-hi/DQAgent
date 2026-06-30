import json

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

_SYSTEM = "You are a data quality validation expert. Respond with valid JSON only."

_HUMAN = """Perform DQ validation on the following preprocessed data.

Preprocessed data:
{data}

Preprocessing changelog:
{changelog}

Validation dimensions:
1. Semantic consistency (e.g., age vs birth date alignment)
2. Domain-specific anomalies (unrealistic values)
3. Cross-field consistency (related fields must agree)
4. Completeness (missing required values)
5. Accuracy (factually wrong values)

Return JSON with exactly these keys:
{{
  "dq_issues": [
    {{
      "field": "",
      "issue_type": "consistency|completeness|accuracy|validity|uniqueness",
      "severity": "critical|warning|info",
      "confidence": 0.0,
      "description": "",
      "suggested_fix": ""
    }}
  ],
  "overall_score": 0,
  "summary": ""
}}"""

_prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


def _build_chain():
    llm = ChatOpenAI(model="gpt-4o", model_kwargs={"response_format": {"type": "json_object"}})
    return _prompt | llm | JsonOutputParser()


def _run(state: dict) -> dict:
    print("[dq-llm-agent] Running semantic DQ validation with OpenAI...")

    result = _build_chain().invoke({
        "data": json.dumps(state["preprocessed_data"], ensure_ascii=False, indent=2),
        "changelog": json.dumps(state["changelog"], ensure_ascii=False, indent=2),
    })

    issues = result.get("dq_issues", [])
    print(f"[dq-llm-agent] Done — {len(issues)} issues, score: {result.get('overall_score', 'N/A')}/100")

    return result


dq_llm_agent = RunnableLambda(_run)
