"""
DuckDB SQL로 원본 ↔ 처리본을 조건별로 비교하는 도구

등록 테이블:
  original   — 원본 레코드
  processed  — 처리 완료 레코드
  changelog  — 변경 이력 (stage2_output.json 사용 시)

Usage:
  python tools/compare_duckdb.py <원본> <처리본>           # 메뉴 표시
  python tools/compare_duckdb.py <원본> <처리본> --all     # 전체 쿼리 실행
  python tools/compare_duckdb.py <원본> <처리본> --query 3 # 특정 쿼리 번호
  python tools/compare_duckdb.py <원본> <처리본> --sql "SELECT ..."
"""
import argparse
import json
import math
import sys

import duckdb
import pandas as pd


# ── 데이터 로딩 ────────────────────────────────────────────────────────────
def _load_original(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    raw = json.loads(text)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for val in raw.values():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val
    return [raw]


def _load_processed(path: str) -> tuple:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "preprocessed_data" in data and "changelog" in data:
        return data["preprocessed_data"], data["changelog"]
    if "preprocessed_data" in data:
        return data["preprocessed_data"], []
    raise ValueError(f"알 수 없는 파일 형식: {path}")


def _nan_to_none(records: list) -> list:
    """float NaN → None 변환 (DuckDB NULL 매핑)."""
    def fix(v):
        return None if (isinstance(v, float) and math.isnan(v)) else v
    return [{k: fix(v) for k, v in r.items()} for r in records]


def _build_conn(original_path: str, processed_path: str) -> tuple:
    """DuckDB 연결 생성 + 테이블 등록. (conn, has_changelog) 반환."""
    conn = duckdb.connect()

    orig_records            = _nan_to_none(_load_original(original_path))
    proc_records, changelog = _load_processed(processed_path)
    proc_records            = _nan_to_none(proc_records)

    conn.register("original",  pd.DataFrame(orig_records))
    conn.register("processed", pd.DataFrame(proc_records))

    has_cl = bool(changelog)
    if has_cl:
        cl_rows = []
        for e in changelog:
            cl_rows.append({
                "record_index": e.get("record_index"),
                "field":        e.get("field"),
                "action":       e.get("action"),
                "original_val": str(e.get("original")) if e.get("original") is not None else None,
                "new_val":      str(e.get("new_value")) if e.get("new_value") is not None else None,
                "reason":       e.get("reason", ""),
            })
        conn.register("changelog", pd.DataFrame(cl_rows))

    return conn, has_cl


# ── 프리셋 쿼리 ────────────────────────────────────────────────────────────
_QUERIES_CL = {   # changelog 있을 때
    1: ("전체 요약",
        """
        SELECT
            (SELECT COUNT(*) FROM original)                            AS 원본_레코드수,
            (SELECT COUNT(*) FROM processed)                           AS 처리본_레코드수,
            (SELECT COUNT(DISTINCT record_index) FROM changelog
             WHERE action != 'keep')                                   AS 변경된_레코드수,
            (SELECT COUNT(*) FROM changelog WHERE action != 'keep')    AS 총_변경_건수
        """),

    2: ("필드별 변경 건수",
        """
        SELECT
            field         AS 필드,
            action        AS 액션,
            COUNT(*)      AS 건수
        FROM changelog
        WHERE action != 'keep'
        GROUP BY field, action
        ORDER BY COUNT(*) DESC, field
        """),

    3: ("액션 유형 분포",
        """
        SELECT
            action                                                      AS 액션,
            COUNT(*)                                                    AS 건수,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) || '%'  AS 비율
        FROM changelog
        WHERE action != 'keep'
        GROUP BY action
        ORDER BY 건수 DESC
        """),

    4: ("NULL 처리된 값 (flag)",
        """
        SELECT
            record_index  AS 레코드,
            field         AS 필드,
            original_val  AS 원본값,
            reason        AS 이유
        FROM changelog
        WHERE action = 'flag' AND new_val IS NULL
        ORDER BY record_index, field
        """),

    5: ("채워진 값 (fill)",
        """
        SELECT
            record_index  AS 레코드,
            field         AS 필드,
            new_val       AS 채워진값,
            reason        AS 이유
        FROM changelog
        WHERE action = 'fill'
        ORDER BY record_index, field
        """),

    6: ("정규화된 값 (normalize)",
        """
        SELECT
            record_index  AS 레코드,
            field         AS 필드,
            original_val  AS 원본값,
            new_val       AS 변환값,
            reason        AS 이유
        FROM changelog
        WHERE action = 'normalize'
        ORDER BY record_index, field
        """),

    7: ("레코드별 변경 건수 TOP 10",
        """
        SELECT
            record_index                        AS 레코드,
            COUNT(*)                            AS 변경건수,
            STRING_AGG(field, ', '
                ORDER BY field)                 AS 변경된_필드
        FROM changelog
        WHERE action != 'keep'
        GROUP BY record_index
        ORDER BY 변경건수 DESC
        LIMIT 10
        """),

    8: ("변경 없는 레코드 (클린)",
        """
        SELECT * EXCLUDE (_row_idx)
        FROM (
            SELECT *, ROW_NUMBER() OVER () - 1 AS _row_idx FROM original
        ) o
        WHERE _row_idx NOT IN (
            SELECT DISTINCT record_index FROM changelog WHERE action != 'keep'
        )
        ORDER BY _row_idx
        """),
}

# changelog 없을 때: original vs processed 직접 비교
_QUERIES_DIRECT = {
    1: ("전체 요약",
        """
        SELECT
            (SELECT COUNT(*) FROM original)   AS 원본_레코드수,
            (SELECT COUNT(*) FROM processed)  AS 처리본_레코드수
        """),

    2: ("처리본 전체",
        "SELECT * FROM processed"),

    3: ("원본 전체",
        "SELECT * FROM original"),
}


# ── 출력 ───────────────────────────────────────────────────────────────────
def _print_df(df: pd.DataFrame, title: str):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")
    if df.empty:
        print("  (결과 없음)")
    else:
        print(df.to_string(index=False))
    print()


def _run_query(conn: duckdb.DuckDBPyConnection, sql: str, title: str):
    try:
        df = conn.execute(sql).df()
        _print_df(df, title)
    except Exception as e:
        print(f"\n  [오류] {e}\n")


# ── 메인 ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="DuckDB로 원본 ↔ 처리본 SQL 비교",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("original",  help="원본 파일 (JSON/JSONL)")
    ap.add_argument("processed", help="처리본 파일 (stage2_output.json 또는 report.json)")
    ap.add_argument("--all",     action="store_true", help="전체 프리셋 쿼리 실행")
    ap.add_argument("--query",   type=int, metavar="N", help="프리셋 쿼리 번호 실행")
    ap.add_argument("--sql",     help="직접 SQL 입력 (테이블: original, processed, changelog)")
    args = ap.parse_args()

    print(f"\n  원본    : {args.original}")
    print(f"  처리본  : {args.processed}")

    conn, has_cl = _build_conn(args.original, args.processed)
    queries      = _QUERIES_CL if has_cl else _QUERIES_DIRECT
    src_note     = "changelog 기반" if has_cl else "직접 비교 (changelog 없음)"
    print(f"  모드    : {src_note}\n")

    # 직접 SQL
    if args.sql:
        _run_query(conn, args.sql, f"사용자 정의 SQL")
        return

    # 특정 쿼리 번호
    if args.query:
        if args.query not in queries:
            print(f"  [오류] 없는 쿼리 번호: {args.query}  (1~{max(queries)})")
            sys.exit(1)
        title, sql = queries[args.query]
        _run_query(conn, sql, f"Q{args.query}. {title}")
        return

    # --all: 전체 실행
    if args.all:
        for num, (title, sql) in queries.items():
            _run_query(conn, sql, f"Q{num}. {title}")
        return

    # 메뉴 표시
    print("  사용 가능한 쿼리:")
    for num, (title, _) in queries.items():
        print(f"    [{num}] {title}")
    print()
    print("  실행 예시:")
    print(f"    python tools/compare_duckdb.py {args.original} {args.processed} --all")
    print(f"    python tools/compare_duckdb.py {args.original} {args.processed} --query 2")
    print(f"    python tools/compare_duckdb.py {args.original} {args.processed} --sql \"SELECT field, COUNT(*) FROM changelog GROUP BY field\"")

    conn.close()


if __name__ == "__main__":
    main()
