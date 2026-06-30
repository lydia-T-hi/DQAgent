import json

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

_SYSTEM = "You are a data preprocessing expert. Respond with valid JSON only — no markdown, no explanation."

_HUMAN = """Preprocess the following JSON data.

Data:
{data}

Tasks:
1. Normalize formats: dates → ISO 8601, numbers → correct types, text → consistent casing
2. Fill clearly derivable missing values
3. Standardize field names to snake_case
4. Flag suspicious values in anomalies

Return JSON with exactly these keys:
{{
  "preprocessed_data": <cleaned data>,
  "changelog": [{{"field": "", "action": "", "before": "", "after": "", "reason": ""}}],
  "anomalies": [{{"field": "", "value": "", "reason": ""}}]
}}"""

_prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])


def _build_chain():
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=8096)
    return _prompt | llm | JsonOutputParser()


def _run(state: dict) -> dict:
    print("[preprocessor-agent] Preprocessing with Claude...")
    data_str = json.dumps(state["validated_input"], ensure_ascii=False, indent=2)

    try:
        result = _build_chain().invoke({"data": data_str})
    except Exception as e:
        print(f"[preprocessor-agent] Warning: {e} — using passthrough")
        result = {
            "preprocessed_data": state["validated_input"],
            "changelog": [{"action": "passthrough", "reason": str(e)}],
            "anomalies": [],
        }

    changelog = result.get("changelog", [])
    print(f"[preprocessor-agent] Done — {len(changelog)} transformations, {len(result.get('anomalies', []))} anomalies")

    return {
        **state,
        "preprocessed_data": result.get("preprocessed_data", state["validated_input"]),
        "changelog": changelog,
        "anomalies": result.get("anomalies", []),
    }


preprocessor_agent = RunnableLambda(_run)
