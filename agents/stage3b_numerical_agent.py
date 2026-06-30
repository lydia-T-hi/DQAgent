"""
Stage 3B: Python/DuckDB — 수치 검증 + 환각 탐지
LLM 없이 순수 Python + DuckDB로 동작합니다.
RunnableParallel에서 호출되므로 자신의 결과만 반환합니다.
"""
import duckdb
import pandas as pd
from langchain_core.runnables import RunnableLambda


def _detect_hallucinations(original: list, preprocessed: list, changelog: list, profile: dict) -> list:
    """Claude가 생성한 값이 통계적으로 허용 범위를 벗어나는지 탐지."""
    hallucinations = []

    fill_entries = [c for c in changelog if c.get("action") in ("fill", "normalize")]

    for entry in fill_entries:
        idx   = entry.get("record_index")
        field = entry.get("field")
        new_v = entry.get("new_value")

        if new_v is None or field not in profile:
            continue

        p = profile[field]
        if "avg" not in p or p.get("stddev") is None or p["stddev"] == 0:
            continue

        try:
            num = float(new_v)
            lo  = p["avg"] - 3 * p["stddev"]
            hi  = p["avg"] + 3 * p["stddev"]
            if num < lo or num > hi:
                hallucinations.append({
                    "record_index": idx,
                    "field":        field,
                    "generated_value": new_v,
                    "original_value":  entry.get("original"),
                    "reason":  f"생성값 {num} 이 3σ 범위 [{lo:.2f}, {hi:.2f}] 밖",
                    "profile_avg":    p["avg"],
                    "profile_stddev": p["stddev"],
                })
        except (TypeError, ValueError):
            pass

    return hallucinations


def _numerical_validation(original: list, preprocessed: list, profile: dict) -> list:
    """DuckDB로 전처리 후 데이터의 수치 범위 재검증."""
    if not preprocessed:
        return []

    conn   = duckdb.connect()
    result = []

    try:
        df = pd.DataFrame(preprocessed)
        conn.register("_pre", df)

        for field, p in profile.items():
            if "avg" not in p or field not in df.columns:
                continue

            col_lower = field.lower()

            # 나이 범위 재검증
            if "age" in col_lower:
                try:
                    cnt = conn.execute(
                        f'SELECT COUNT(*) FROM _pre WHERE "{field}" IS NOT NULL '
                        f'AND CAST("{field}" AS DOUBLE) NOT BETWEEN 0 AND 150'
                    ).fetchone()[0]
                    if cnt:
                        result.append({
                            "field": field, "rule": "age_range",
                            "count": cnt, "severity": "critical",
                            "detail": f"전처리 후에도 나이 범위 오류 {cnt}건",
                        })
                except Exception:
                    pass

            # 음수 금액 재검증
            if any(k in col_lower for k in ("salary", "price", "amount", "cost", "pay", "fee")):
                try:
                    cnt = conn.execute(
                        f'SELECT COUNT(*) FROM _pre WHERE "{field}" IS NOT NULL '
                        f'AND CAST("{field}" AS DOUBLE) < 0'
                    ).fetchone()[0]
                    if cnt:
                        result.append({
                            "field": field, "rule": "negative_amount",
                            "count": cnt, "severity": "critical",
                            "detail": f"전처리 후에도 음수 금액 {cnt}건",
                        })
                except Exception:
                    pass

            # 통계적 이상치 재검증 (Z-score > 3)
            if p.get("stddev") and p["stddev"] > 0:
                try:
                    cnt = conn.execute(
                        f'SELECT COUNT(*) FROM _pre WHERE "{field}" IS NOT NULL '
                        f'AND ABS(CAST("{field}" AS DOUBLE) - {p["avg"]}) / {p["stddev"]} > 3'
                    ).fetchone()[0]
                    if cnt:
                        result.append({
                            "field": field, "rule": "zscore_outlier",
                            "count": cnt, "severity": "warning",
                            "detail": f"전처리 후 Z-score > 3 이상치 {cnt}건",
                        })
                except Exception:
                    pass

    finally:
        conn.close()

    return result


def _value_drift(original: list, preprocessed: list) -> list:
    """원본 대비 전처리 후 값 변화율 분석."""
    if not original or not preprocessed or len(original) != len(preprocessed):
        return []

    drifts = []
    changed_counts: dict[str, int] = {}

    for orig, pre in zip(original, preprocessed):
        for field in orig:
            ov = orig.get(field)
            pv = pre.get(field) if pre else ov
            if str(ov) != str(pv):
                changed_counts[field] = changed_counts.get(field, 0) + 1

    total = len(original)
    for field, cnt in changed_counts.items():
        pct = round(cnt / total * 100, 1)
        if pct > 50:
            drifts.append({
                "field":    field,
                "changed":  cnt,
                "total":    total,
                "pct":      pct,
                "severity": "warning",
                "detail":   f"전처리 후 {pct}% 변경됨 — 과도한 수정 의심",
            })

    return drifts


def _run(state: dict) -> dict:
    print("[Stage3B-Numerical] 수치 검증 + 환각 탐지 시작")

    original     = state.get("original_records", [])
    preprocessed = state.get("preprocessed_data", original)
    changelog    = state.get("changelog", [])
    profile      = state.get("profile", {})

    hallucinations     = _detect_hallucinations(original, preprocessed, changelog, profile)
    numerical_violations = _numerical_validation(original, preprocessed, profile)
    drifts             = _value_drift(original, preprocessed)

    print(
        f"[Stage3B-Numerical] 완료 — "
        f"환각 {len(hallucinations)}건, "
        f"수치위반 {len(numerical_violations)}건, "
        f"드리프트 {len(drifts)}건"
    )

    return {
        "hallucinations":        hallucinations,
        "numerical_violations":  numerical_violations,
        "value_drifts":          drifts,
        "summary": {
            "hallucination_count": len(hallucinations),
            "numerical_violation_count": len(numerical_violations),
            "drift_count": len(drifts),
        },
    }


stage3b_numerical_agent = RunnableLambda(_run)
