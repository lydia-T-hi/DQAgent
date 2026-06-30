"""
Stage 2: Claude — 의미 기반 전처리
Claude Code CLI (subprocess)를 사용합니다. Pro 구독으로 동작 (API 키/크레딧 불필요).

최적화:
  - 클린 레코드 스킵: 위반 패턴이 없는 레코드는 Claude 호출 생략
  - 청크 병렬 처리: ThreadPoolExecutor(max_workers=3)로 동시 실행
"""
import json
import math
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime


def _is_null(value) -> bool:
    """None 또는 float NaN 여부 판단 (pandas→dict 변환 시 NaN이 None이 아닌 float('nan')으로 남는 경우 처리)."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False

from langchain_core.runnables import RunnableLambda

_SYSTEM_INSTRUCTIONS = """\
당신은 데이터 품질 전처리 전문가입니다.
주어진 원본 데이터와 통계 프로파일, 규칙 위반 목록을 바탕으로 의미 기반 전처리를 수행합니다.

반드시 아래 JSON 구조로만 응답하세요 (마크다운 없이 순수 JSON만):

{
  "preprocessed_data": [ ...원본과 동일 필드를 유지한 레코드 리스트... ],
  "changelog": [
    {
      "record_index": <정수>,
      "field": "<필드명>",
      "action": "normalize|fill|flag|keep",
      "original": <원본값>,
      "new_value": <변환후값 또는 null>,
      "reason": "<한 줄 이유>"
    }
  ],
  "interpretations": [
    {
      "rule": "<rule 이름>",
      "field": "<필드명>",
      "interpretation": "<이 위반이 의미하는 것>",
      "recommendation": "fix|flag|ignore"
    }
  ]
}

주의사항:
- 레코드를 추가하거나 삭제하지 마세요. 원본 개수를 유지하세요.
- 확실하지 않은 값은 추론하지 말고 null 유지 + flag 처리하세요.
- changelog에는 실제로 변경된 경우만 기록하세요.
"""

_CHUNK_SIZE  = 10  # Claude 1회 호출당 최대 레코드 수
_MAX_WORKERS = 2   # 동시 Claude CLI 세션 수 (3→2: 병렬 경쟁으로 인한 타임아웃 완화)
_TIMEOUT     = 600 # 초 (300→600: 복잡한 레코드 처리 여유 확보)
_MAX_RETRY   = 1   # 타임아웃 시 재시도 횟수


def _needs_claude(record: dict, violated_fields: set, profile: dict) -> bool:
    """레코드가 Claude 처리 필요 여부를 판단한다.

    다음 중 하나라도 해당하면 True:
      - null 값 존재 (fill 가능성)
      - 위반 필드에 실제 오류 값 존재
      - 소문자 이름 (정규화 필요)
      - 통계적 이상치 (Z-score > 3)
    """
    for field, value in record.items():
        flow = field.lower()

        # null/NaN → fill 가능성
        if _is_null(value):
            return True

        sval = str(value)

        if field in violated_fields:
            # 이메일 오류
            if any(k in flow for k in ("email", "mail")):
                if "@" not in sval or len(sval) < 5:
                    return True

            # 미래 날짜
            if any(k in flow for k in ("date", "birth", "dob", "born")):
                try:
                    d = datetime.strptime(sval[:10], "%Y-%m-%d").date()
                    if d > date.today():
                        return True
                except Exception:
                    pass

            # 나이 범위 오류
            if "age" in flow:
                try:
                    if float(value) < 0 or float(value) > 150:
                        return True
                except Exception:
                    pass

            # 음수 금액
            if any(k in flow for k in ("salary", "price", "amount", "cost", "pay", "fee", "wage")):
                try:
                    if float(value) < 0:
                        return True
                except Exception:
                    pass

        # 소문자 이름 (정규화 필요)
        if "name" in flow and isinstance(value, str) and value.strip() and value == value.lower():
            return True

        # 통계적 이상치 (Z-score > 3)
        p = profile.get(field, {})
        if "avg" in p and p.get("stddev") and p["stddev"] > 0:
            try:
                z = abs(float(value) - p["avg"]) / p["stddev"]
                if z > 3:
                    return True
            except Exception:
                pass

    return False


def _call_claude_once(prompt: str) -> dict:
    """Claude CLI 단일 호출. 타임아웃/비정상 종료 시 예외 전파."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="dq_prompt_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(prompt)

        # ANTHROPIC_API_KEY 제거 — .env 로드 시 API 크레딧 대신 OAuth(Pro) 사용
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        with open(tmp_path, "rb") as stdin_file:
            result = subprocess.run(
                ["claude", "--print", "--output-format", "json"],
                stdin=stdin_file,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=_TIMEOUT,
                env=env,
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.returncode != 0:
        detail = result.stderr or result.stdout or "(출력 없음)"
        raise RuntimeError(f"Claude CLI 오류 (exit={result.returncode}):\n{detail}")

    try:
        cli_data = json.loads(result.stdout)
        if cli_data.get("is_error"):
            raise RuntimeError(f"Claude CLI 오류: {cli_data.get('result')}")
        response_text = cli_data.get("result", result.stdout)
    except json.JSONDecodeError:
        response_text = result.stdout

    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    return json.loads(text)


def _call_claude_cli(prompt: str) -> dict:
    """타임아웃 시 _MAX_RETRY 횟수만큼 자동 재시도."""
    for attempt in range(_MAX_RETRY + 1):
        try:
            return _call_claude_once(prompt)
        except subprocess.TimeoutExpired:
            if attempt < _MAX_RETRY:
                print(f"[Stage2] 타임아웃({_TIMEOUT}s), 재시도 중... ({attempt + 1}/{_MAX_RETRY})")
            else:
                raise RuntimeError(
                    f"Claude CLI 타임아웃: {_TIMEOUT}초 × {_MAX_RETRY + 1}회 모두 초과"
                )


def _profile_summary(profile: dict) -> str:
    lines = []
    for field, p in profile.items():
        base = f"  {field}: null={p['null_pct']}%"
        if "avg" in p:
            base += f", range=[{p['min']}, {p['max']}] avg={p['avg']}"
        lines.append(base)
    return "\n".join(lines)


def _violations_summary(violations: list) -> str:
    if not violations:
        return "  없음"
    return "\n".join(
        f"  [{v['severity'].upper()}] {v['field']}.{v['rule']}: {v['detail']}"
        + (f" 예시={v['examples'][:2]}" if v.get("examples") else "")
        for v in violations
    )


def _build_prompt(profile: dict, violations: list, records: list) -> str:
    data_section = (
        "## 통계 프로파일\n"
        + _profile_summary(profile)
        + "\n\n## 규칙 위반\n"
        + _violations_summary(violations)
        + f"\n\n## 원본 데이터 ({len(records)}건)\n"
        + json.dumps(records, ensure_ascii=False, indent=2, default=str)
        + "\n\n위 데이터를 전처리하고 결과를 JSON으로 반환하세요."
    )
    return _SYSTEM_INSTRUCTIONS + "\n\n---\n\n" + data_section


def _process_chunk(args: tuple) -> tuple:
    """청크 단위 Claude 처리 — ThreadPoolExecutor에서 병렬 호출됨."""
    chunk, orig_indices, profile, violations, label = args
    prompt = _build_prompt(profile, violations, chunk)
    result  = _call_claude_cli(prompt)

    preprocessed = result.get("preprocessed_data", chunk)

    # record_index → all_records 기준 원본 인덱스로 변환
    changelog = []
    for entry in result.get("changelog", []):
        entry   = dict(entry)
        rec_idx = entry.get("record_index")
        if rec_idx is not None and rec_idx < len(orig_indices):
            entry["record_index"] = orig_indices[rec_idx]
        changelog.append(entry)

    return preprocessed, changelog, result.get("interpretations", []), label


def _run(state: dict) -> dict:
    print("[Stage2-Claude] 의미 기반 전처리 시작 (CLI 모드)")

    all_records     = [r for batch in state["data"] for r in batch]
    total           = len(all_records)
    violations      = state["rule_violations"]
    violated_fields = {v["field"] for v in violations}
    profile         = state["profile"]

    # ── 클린 레코드 스킵 ──────────────────────────────────────────────
    needs_idx  = [
        i for i, r in enumerate(all_records)
        if _needs_claude(r, violated_fields, profile)
    ]
    skip_count = total - len(needs_idx)
    print(f"[Stage2-Claude] 전체 {total}건 중 {len(needs_idx)}건 처리 / {skip_count}건 스킵")

    preprocessed_map: dict[int, dict] = {}
    changelog_all:    list            = []
    interpretations_all: list         = []

    if needs_idx:
        to_process = [all_records[i] for i in needs_idx]

        # 청크 목록 구성
        chunks_args = []
        n_chunks    = math.ceil(len(to_process) / _CHUNK_SIZE)
        for ci in range(n_chunks):
            start       = ci * _CHUNK_SIZE
            chunk       = to_process[start : start + _CHUNK_SIZE]
            orig_idx    = needs_idx[start : start + len(chunk)]
            label       = f"{ci + 1}/{n_chunks}"
            chunks_args.append((chunk, orig_idx, profile, violations, label))

        # ── 병렬 처리 ──────────────────────────────────────────────────
        workers = min(_MAX_WORKERS, n_chunks)
        done    = 0
        print(f"[Stage2-Claude] 병렬 처리 시작 (최대 {workers}개 동시 실행)")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(_process_chunk, arg): arg for arg in chunks_args}

            for future in as_completed(future_map):
                preprocessed, changelog, interpretations, label = future.result()
                done += 1
                print(f"[Stage2-Claude] 청크 {label} 완료 ({done}/{n_chunks})")

                orig_indices = future_map[future][1]
                for j, rec in enumerate(preprocessed):
                    if j < len(orig_indices):
                        preprocessed_map[orig_indices[j]] = rec

                changelog_all.extend(changelog)

                seen = {(x["rule"], x["field"]) for x in interpretations_all}
                for interp in interpretations:
                    key = (interp.get("rule"), interp.get("field"))
                    if key not in seen:
                        interpretations_all.append(interp)
                        seen.add(key)

    # 원본 순서로 병합 (클린 레코드는 원본 그대로)
    preprocessed_all = [preprocessed_map.get(i, all_records[i]) for i in range(total)]

    print(f"[Stage2-Claude] 완료 — 변경 {len(changelog_all)}건, 해석 {len(interpretations_all)}건")

    return {
        **state,
        "original_records":  all_records,
        "preprocessed_data": preprocessed_all,
        "changelog":         changelog_all,
        "interpretations":   interpretations_all,
    }


stage2_claude_agent = RunnableLambda(_run)
