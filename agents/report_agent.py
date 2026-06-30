import json
import os
from datetime import datetime

from langchain_core.runnables import RunnableLambda


def _run(state: dict) -> dict:
    print("[report-agent] Merging results and generating final report...")

    source_file = state["source_file"]
    base_name = os.path.splitext(source_file)[0]
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = state.get("output_dir", "report")
    output_path = os.path.join(output_dir, f"{base_name}_report_{date_str}.json")
    os.makedirs(output_dir, exist_ok=True)

    dq_llm = state["dq_results"]["llm"]
    dq_code = state["dq_results"]["code"]

    # LLM 이슈에 출처 태그 추가
    llm_issues = dq_llm.get("dq_issues", [])
    for issue in llm_issues:
        issue.setdefault("source", "llm_validation")

    # 코드 검증 실패 항목 → 통합 이슈 포맷 변환
    code_issues = [
        {
            "field": r.get("field", "unknown"),
            "issue_type": "hallucination" if r.get("hallucination_flag") else "validity",
            "severity": "critical" if r.get("hallucination_flag") else "warning",
            "confidence": 0.95,
            "description": (
                f"Rule '{r.get('rule')}' failed. "
                f"Value: {r.get('actual_value')} | Expected: {r.get('expected')}"
            ),
            "suggested_fix": None,
            "source": "code_validation",
        }
        for r in dq_code.get("validation_results", [])
        if not r.get("passed")
    ]

    all_issues = llm_issues + code_issues
    by_severity = {
        "critical": [i for i in all_issues if i.get("severity") == "critical"],
        "warning":  [i for i in all_issues if i.get("severity") == "warning"],
        "info":     [i for i in all_issues if i.get("severity") == "info"],
    }

    report = {
        "metadata": {
            "pipeline_id": state["pipeline_id"],
            "source_file": source_file,
            "generated_at": datetime.now().isoformat(),
            "report_version": "1.0",
        },
        "final_preprocessed_data": state["preprocessed_data"],
        "preprocessing_summary": {
            "changelog": state.get("changelog", []),
            "anomalies_detected": state.get("anomalies", []),
        },
        "dq_validation": {
            "overall_score": dq_llm.get("overall_score", 0),
            "total_issues": len(all_issues),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "issues": by_severity,
        },
        "llm_validation": {
            "engine": "gpt-4o",
            "overall_score": dq_llm.get("overall_score", 0),
            "summary": dq_llm.get("summary", ""),
        },
        "code_validation": {
            "engine": "python-code-snippet (claude-generated)",
            "code_snippet": dq_code.get("code_snippet", ""),
            "summary": dq_code.get("summary", {}),
            "results": dq_code.get("validation_results", []),
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    c, w, i = by_severity["critical"], by_severity["warning"], by_severity["info"]
    print(
        f"[report-agent] Saved → {output_path} | "
        f"{len(c)} critical, {len(w)} warnings, {len(i)} info"
    )

    return {"output_path": output_path, "report": report}


report_agent = RunnableLambda(_run)
