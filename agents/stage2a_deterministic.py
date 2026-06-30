"""
Stage 2A: 결정론적 정규화 (LLM 불필요, 밀리초 처리)

LLM 없이 Python 규칙으로 처리 가능한 DQ 이슈를 즉시 수정합니다.
  - 이름: 소문자 → Title Case
  - 이메일: 형식 오류 → null
  - 날짜: 미래 날짜 → null
  - 나이: 범위 오류 → null / null이면 birth_date에서 계산
  - 금액: 음수 → null
  - 국가코드: 명백히 잘못된 코드 → null

처리 후 Z-score > 3 이상치가 남은 레코드는 ambiguous_indices에 기록되어
Stage 2B(Claude)로 전달됩니다.
"""
import math
from datetime import date, datetime

from langchain_core.runnables import RunnableLambda

# ISO 3166-1 alpha-2 중 명백히 잘못된/더미 코드 집합
_INVALID_COUNTRY_CODES = {"ZZ", "XX", "AA", "QQ", "00", "NA", "NN", "TT"}


# ── 유틸 ──────────────────────────────────────────────────────────────────────
def _is_null(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _action_type(orig, new_val) -> str:
    if _is_null(orig) and not _is_null(new_val):
        return "fill"
    if not _is_null(orig) and _is_null(new_val):
        return "flag"
    return "normalize"


def _entry(idx, field, orig, new_val, reason) -> dict:
    return {
        "record_index": idx,
        "field":        field,
        "action":       _action_type(orig, new_val),
        "original":     orig,
        "new_value":    None if _is_null(new_val) else new_val,
        "reason":       reason,
        "stage":        "2a",
    }


# ── 필드별 처리 함수 ────────────────────────────────────────────────────────
def _proc_name(value):
    if not isinstance(value, str) or not value.strip():
        return value, None
    if value == value.lower():
        return value.title(), "소문자 이름 → Title Case 정규화"
    return value, None


def _proc_email(value):
    if _is_null(value):
        return None, None
    s = str(value).strip()
    if "@" not in s or len(s) < 5 or s.startswith("@") or s.endswith("@"):
        return None, f"이메일 형식 오류 ('{s}') → null"
    return value, None


def _proc_date(value):
    if _is_null(value):
        return None, None
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        if d > date.today():
            return None, f"미래 날짜 ({value}) → null"
    except Exception:
        pass
    return value, None


def _fill_age_from_birth(record: dict):
    birth_field = next(
        (f for f in record if any(k in f.lower() for k in ("birth", "dob", "born"))),
        None,
    )
    if not birth_field or _is_null(record.get(birth_field)):
        return None, None
    try:
        bd = datetime.strptime(str(record[birth_field])[:10], "%Y-%m-%d").date()
        today = date.today()
        if bd > today:
            return None, None
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        if 0 <= age <= 150:
            return float(age), f"{birth_field}({record[birth_field]}) 기준 나이 {age}세 계산"
    except Exception:
        pass
    return None, None


def _proc_age(value, record: dict):
    if _is_null(value):
        filled, reason = _fill_age_from_birth(record)
        return filled, reason
    try:
        age = float(value)
        if age < 0 or age > 150:
            return None, f"나이 범위 오류 ({value}, 유효: 0~150) → null"
    except Exception:
        pass
    return value, None


def _proc_amount(value):
    if _is_null(value):
        return None, None
    try:
        if float(value) < 0:
            return None, f"음수 금액 ({value}) → null"
    except Exception:
        pass
    return value, None


def _proc_country(value):
    if _is_null(value):
        return None, None
    s = str(value).strip().upper()
    if not s.isalpha() or len(s) != 2 or s in _INVALID_COUNTRY_CODES:
        return None, f"유효하지 않은 국가코드 ('{value}') → null"
    return value, None


# ── 레코드 처리 ──────────────────────────────────────────────────────────────
def _process_record(idx: int, record: dict, profile: dict) -> tuple:
    """단일 레코드 결정론적 처리.
    반환: (new_record, changelog_entries, is_ambiguous)
    """
    new_rec = dict(record)
    entries = []

    for field, value in record.items():
        flow    = field.lower()
        new_val = value
        reason  = None

        if "name" in flow and not any(k in flow for k in ("username", "domain", "file")):
            new_val, reason = _proc_name(value)

        elif any(k in flow for k in ("email", "mail")):
            new_val, reason = _proc_email(value)

        elif any(k in flow for k in ("date", "birth", "dob", "born")):
            new_val, reason = _proc_date(value)

        elif "age" in flow:
            new_val, reason = _proc_age(value, record)

        elif any(k in flow for k in ("salary", "price", "amount", "cost", "pay", "fee", "wage")):
            new_val, reason = _proc_amount(value)

        elif any(k in flow for k in ("country", "nation", "region")):
            new_val, reason = _proc_country(value)

        if reason is not None:
            new_rec[field] = None if _is_null(new_val) else new_val
            entries.append(_entry(idx, field, value, new_val, reason))

    # 모호성 판단: 처리 후에도 Z-score > 3 이상치가 남아 있는 필드
    is_ambiguous = _has_statistical_outlier(new_rec, profile)
    return new_rec, entries, is_ambiguous


def _has_statistical_outlier(record: dict, profile: dict) -> bool:
    for field, value in record.items():
        if _is_null(value):
            continue
        p = profile.get(field, {})
        if "avg" not in p or not p.get("stddev") or p["stddev"] == 0:
            continue
        try:
            z = abs(float(value) - p["avg"]) / p["stddev"]
            if z > 3:
                return True
        except Exception:
            pass
    return False


# ── 스테이지 실행 ─────────────────────────────────────────────────────────────
def _run(state: dict) -> dict:
    print("[Stage2A-Det] 결정론적 정규화 시작")

    all_records     = [r for batch in state["data"] for r in batch]
    profile         = state["profile"]

    processed       = []
    changelog: list = []
    ambiguous_idx   = []

    for i, record in enumerate(all_records):
        new_rec, entries, is_ambiguous = _process_record(i, record, profile)
        processed.append(new_rec)
        changelog.extend(entries)
        if is_ambiguous:
            ambiguous_idx.append(i)

    print(
        f"[Stage2A-Det] 완료 — 변경 {len(changelog)}건 / "
        f"이상치(2B 대상) {len(ambiguous_idx)}건"
    )

    return {
        **state,
        "original_records":  all_records,
        "preprocessed_data": processed,
        "changelog":         changelog,
        "interpretations":   [],
        "ambiguous_indices": ambiguous_idx,
    }


stage2a_deterministic = RunnableLambda(_run)
