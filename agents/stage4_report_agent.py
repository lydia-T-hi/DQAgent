"""
Stage 4: Report Agent — 합의 기반 최종 판단
3개 소스(DuckDB규칙, OpenAI판단, Python수치)를 합산해 최종 DQ 보고서를 생성합니다.
"""
import json
import os
from datetime import datetime

from langchain_core.runnables import RunnableLambda

_WEIGHT = {"duckdb": 0.40, "openai": 0.35, "numerical": 0.25}


def _severity_score(sev: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(sev, 0)


def _consensus_label(sources_flagged: int, severities: list, source_types: set) -> str:
    """개선된 합의 로직:
    - DuckDB critical 위반은 단독으로도 critical (규칙 기반 = 결정론적 증거)
    - 2개 이상 소스가 플래그 → critical
    - 단일 소스 warning/info는 소스 유형에 따라 판단
    """
    has_critical = "critical" in severities
    # DuckDB 규칙은 결정론적 → critical이면 즉시 critical
    if has_critical and "duckdb" in source_types:
        return "critical"
    # 다중 소스 합의
    if sources_flagged >= 2:
        return "critical"
    # 단일 소스
    if sources_flagged == 1:
        if has_critical:
            return "critical"
        return "warning"
    return "pass"


def _build_consensus(state: dict) -> list:
    stage3a = state.get("stage3a", {})
    stage3b = state.get("stage3b", {})

    findings = []

    # DuckDB 규칙 위반
    for v in state.get("rule_violations", []):
        findings.append({
            "source":    "duckdb",
            "field":     v["field"],
            "rule":      v["rule"],
            "severity":  v["severity"],
            "count":     v["count"],
            "detail":    v["detail"],
            "examples":  v.get("examples", []),
        })

    # OpenAI 판단
    for issue in stage3a.get("issues", []):
        findings.append({
            "source":    "openai",
            "field":     issue.get("field"),
            "rule":      issue.get("issue_type"),
            "severity":  issue.get("severity"),
            "count":     None,
            "detail":    issue.get("description"),
            "confidence": issue.get("confidence"),
        })

    # Python/DuckDB 수치 검증
    for v in stage3b.get("numerical_violations", []):
        findings.append({
            "source":   "numerical",
            "field":    v["field"],
            "rule":     v["rule"],
            "severity": v["severity"],
            "count":    v["count"],
            "detail":   v["detail"],
        })
    for h in stage3b.get("hallucinations", []):
        findings.append({
            "source":   "numerical",
            "field":    h["field"],
            "rule":     "hallucination",
            "severity": "critical",
            "count":    1,
            "detail":   h["reason"],
        })

    # 필드별 합의 계산
    field_map: dict[str, dict] = {}
    for f in findings:
        key = f.get("field") or "__global__"
        if key not in field_map:
            field_map[key] = {"sources": set(), "severities": [], "findings": []}
        field_map[key]["sources"].add(f["source"])
        field_map[key]["severities"].append(f["severity"])
        field_map[key]["findings"].append(f)

    consensus = []
    for field, info in field_map.items():
        src_cnt = len(info["sources"])
        label   = _consensus_label(src_cnt, info["severities"], info["sources"])
        consensus.append({
            "field":           field,
            "consensus_level": label,
            "sources_flagged": sorted(info["sources"]),
            "source_count":    src_cnt,
            "findings":        info["findings"],
        })

    consensus.sort(key=lambda x: -x["source_count"])
    return consensus


def _compute_scores(state: dict) -> dict:
    stage3a = state.get("stage3a", {})
    stage3b = state.get("stage3b", {})

    total = state.get("total_records", 1) or 1
    rule_violations = state.get("rule_violations", [])

    # DuckDB 점수: critical 위반 레코드 비율 기반
    crit_records = sum(v["count"] for v in rule_violations if v["severity"] == "critical")
    duckdb_score = max(0, round(100 - (crit_records / total) * 100))

    # OpenAI 점수: 직접 제공 (None이면 skip-openai 모드)
    openai_score = stage3a.get("overall_score")

    # 수치 점수: 환각 + 위반 건수 기반
    num_issues = (
        stage3b.get("summary", {}).get("hallucination_count", 0)
        + stage3b.get("summary", {}).get("numerical_violation_count", 0)
    )
    numerical_score = max(0, round(100 - (num_issues / total) * 100))

    # skip-openai 시 가중치 재분배 (DuckDB 60% / 수치 40%)
    if openai_score is None:
        weighted = round(duckdb_score * 0.60 + numerical_score * 0.40)
    else:
        weighted = round(
            duckdb_score      * _WEIGHT["duckdb"]
            + openai_score    * _WEIGHT["openai"]
            + numerical_score * _WEIGHT["numerical"]
        )

    return {
        "duckdb_rules":  duckdb_score,
        "openai_judge":  openai_score,
        "numerical":     numerical_score,
        "weighted_final": weighted,
    }


def _run(state: dict) -> dict:
    print("[Stage4-Report] 합의 보고서 생성 중...")

    source_file = state.get("source_file", "unknown")
    date_str    = datetime.now().strftime("%Y%m%d")
    out_dir     = "report"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{os.path.splitext(source_file)[0]}_report_{date_str}.json")

    consensus = _build_consensus(state)
    scores    = _compute_scores(state)

    stage3a = state.get("stage3a", {})
    stage3b = state.get("stage3b", {})

    critical_items = [c for c in consensus if c["consensus_level"] == "critical"]
    warning_items  = [c for c in consensus if c["consensus_level"] == "warning"]
    pass_count     = sum(1 for c in consensus if c["consensus_level"] == "pass")

    grade = "A" if scores["weighted_final"] >= 90 else \
            "B" if scores["weighted_final"] >= 75 else \
            "C" if scores["weighted_final"] >= 60 else "D"

    report = {
        "metadata": {
            "pipeline_id":  state.get("pipeline_id"),
            "source_file":  source_file,
            "generated_at": datetime.now().isoformat(),
            "total_records": state.get("total_records"),
        },
        "grade": grade,
        "scores": scores,
        "consensus_summary": {
            "critical_fields": len(critical_items),
            "warning_fields":  len(warning_items),
            "pass_fields":     pass_count,
            "total_findings":  sum(len(c["findings"]) for c in consensus),
        },
        "consensus": consensus,
        "stage1_rule_summary": state.get("rule_summary", {}),
        "stage2_changelog_count": len(state.get("changelog", [])),
        "stage3a_summary": {
            "overall_score": stage3a.get("overall_score"),
            "issue_count":   len(stage3a.get("issues", [])),
            "summary":       stage3a.get("summary", ""),
        },
        "stage3b_summary":   stage3b.get("summary", {}),
        "rule_violations":   state.get("rule_violations", []),
        "changelog":         state.get("changelog", []),
        "preprocessed_data": state.get("preprocessed_data", []),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    score = scores["weighted_final"]
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
    print(f"[Stage4-Report] 완료 — 최종 DQ 점수: {score}/100 ({grade}등급)")
    print(f"[Stage4-Report] 보고서 저장: {out_path}")

    return {
        "output_path": out_path,
        "scores":      scores,
        "grade":       grade,
        "consensus_summary": report["consensus_summary"],
    }


stage4_report_agent = RunnableLambda(_run)
