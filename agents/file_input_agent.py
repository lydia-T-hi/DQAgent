import math
import os
import uuid
from datetime import datetime

import duckdb
import pandas as pd
from langchain_core.runnables import RunnableLambda

# 확장자 → 처리 방식 매핑
_DUCKDB_EXTS = {".csv", ".tsv", ".parquet", ".json", ".jsonl"}
_PANDAS_EXTS = {".xlsx", ".xls"}
_ALL_EXTS    = _DUCKDB_EXTS | _PANDAS_EXTS


def _reader_expr(path: str, ext: str) -> str:
    """DuckDB FROM 절에 들어갈 reader 표현식 반환 (Windows 경로 정규화 포함)"""
    safe = path.replace("\\", "/")
    return {
        ".csv":     f"read_csv_auto('{safe}')",
        ".tsv":     f"read_csv_auto('{safe}', delim='\t')",
        ".parquet": f"read_parquet('{safe}')",
        ".json":    f"read_json_auto('{safe}')",
        ".jsonl":   f"read_json_auto('{safe}')",
    }[ext]


def _fetch_batches(inputs: dict) -> dict:
    file_path   = os.path.abspath(inputs["file_path"])
    batch_size  = int(inputs.get("batch_size", 500))
    pipeline_id = inputs.get(
        "pipeline_id",
        f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
    )

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    ext         = os.path.splitext(file_path)[1].lower()
    source_file = os.path.basename(file_path)

    if ext not in _ALL_EXTS:
        raise ValueError(
            f"지원하지 않는 파일 형식: '{ext}'\n"
            f"지원 형식: {sorted(_ALL_EXTS)}"
        )

    print(f"[file-input-agent] 파일  : {source_file}  ({ext})")

    conn = duckdb.connect()
    try:
        if ext in _PANDAS_EXTS:
            # Excel → pandas → DuckDB 가상 테이블 등록
            df = pd.read_excel(file_path)
            conn.register("_tbl", df)
            expr = "_tbl"
        else:
            expr = _reader_expr(file_path, ext)

        total       = conn.execute(f"SELECT COUNT(*) FROM {expr}").fetchone()[0]
        batch_count = math.ceil(total / batch_size)

        print(f"[file-input-agent] 전체  : {total:,}건")
        print(f"[file-input-agent] 배치  : {batch_count}개 × {batch_size}건")

        batches = []
        for i in range(batch_count):
            df_batch = conn.execute(
                f"SELECT * FROM {expr} LIMIT {batch_size} OFFSET {i * batch_size}"
            ).df()

            # datetime/Timestamp → str 변환 (JSON 직렬화 호환), NaT → None
            for col in df_batch.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
                df_batch[col] = df_batch[col].dt.strftime("%Y-%m-%d").where(df_batch[col].notna(), None)

            rows = df_batch.where(pd.notnull(df_batch), None).to_dict(orient="records")
            batches.append(rows)
            print(f"[file-input-agent] [{i + 1}/{batch_count}] {len(rows)}건 추출")

    finally:
        conn.close()

    print(f"[file-input-agent] 완료  : {batch_count}개 배치 준비")

    return {
        "pipeline_id":   pipeline_id,
        "source_file":   source_file,
        "total_records": total,
        "batch_count":   batch_count,
        "batch_size":    batch_size,
        "batches":       batches,
    }


file_input_agent = RunnableLambda(_fetch_batches)
