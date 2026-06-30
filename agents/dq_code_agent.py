import json
import re
import traceback

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

_HUMAN = """Generate a Python function to validate the following data for hallucinations and rule violations.

Data:
{data}

Write a function named `validate_data(data)` that:
1. Checks data types and value ranges for each field
2. Detects impossible/hallucinated values (future birth dates, negative ages, invalid country codes, etc.)
3. Validates formats (email, phone, ISO dates) where applicable
4. Checks cross-field consistency (e.g., end_date after start_date)

Each result dict must have exactly these keys:
- field: str
- rule: str
- passed: bool
- actual_value: any
- expected: str
- hallucination_flag: bool

Return ONLY valid Python code inside a ```python block."""

_prompt = ChatPromptTemplate.from_messages([("human", _HUMAN)])


def _build_chain():
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096)
    return _prompt | llm | StrOutputParser()


def _extract_code(raw: str) -> str:
    match = re.search(r"```python\s*([\s\S]*?)\s*```", raw)
    return match.group(1) if match else raw


def _exec_code(code: str, data: dict) -> list:
    namespace = {}
    try:
        exec(compile(code, "<dq_validation>", "exec"), namespace)
        fn = namespace.get("validate_data")
        if fn is None:
            raise ValueError("validate_data function not found in generated code")
        result = fn(data)
        if not isinstance(result, list):
            raise ValueError(f"validate_data must return list, got {type(result)}")
        return result
    except Exception:
        return [{
            "field": "__execution__",
            "rule": "code_execution",
            "passed": False,
            "actual_value": traceback.format_exc(),
            "expected": "successful execution",
            "hallucination_flag": False,
        }]


def _run(state: dict) -> dict:
    print("[dq-code-agent] Generating Python validation code with Claude...")

    raw = _build_chain().invoke({
        "data": json.dumps(state["preprocessed_data"], ensure_ascii=False, indent=2)
    })
    code = _extract_code(raw)
    print(f"[dq-code-agent] Code generated ({len(code)} chars) — executing...")

    results = _exec_code(code, state["preprocessed_data"])

    failed = [r for r in results if not r.get("passed")]
    hallucinations = [r for r in results if r.get("hallucination_flag")]
    print(
        f"[dq-code-agent] Done — {len(results)} checks, "
        f"{len(failed)} failed, {len(hallucinations)} hallucination flags"
    )

    return {
        "code_snippet": code,
        "validation_results": results,
        "summary": {
            "total_checks": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "hallucination_flags": len(hallucinations),
        },
    }


dq_code_agent = RunnableLambda(_run)
