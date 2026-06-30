"""
원본 ↔ 처리본 레코드 단위 비교 도구

Usage:
  python tools/compare.py <원본파일> <처리본파일>
  python tools/compare.py customer_data_quality_test_50.json tests/output/stage2_output.json
  python tools/compare.py customer_data.json report/report.json --field email
  python tools/compare.py customer_data.json stage2_output.json --action flag
  python tools/compare.py customer_data.json stage2_output.json --changed-only
"""
import argparse
import json
import math
import sys

# ── ANSI 색상 (Windows CMD 미지원 시 자동 비활성화) ──────────────────────
_USE_COLOR = sys.stdout.isatty()
_R  = "\033[0;31m"   if _USE_COLOR else ""
_G  = "\033[0;32m"   if _USE_COLOR else ""
_Y  = "\033[1;33m"   if _USE_COLOR else ""
_C  = "\033[0;36m"   if _USE_COLOR else ""
_B  = "\033[1;34m"   if _USE_COLOR else ""
_NC = "\033[0m"      if _USE_COLOR else ""

_ACTION_COLOR = {"normalize": _B, "fill": _G, "flag": _Y, "keep": _NC}


# ── 데이터 로딩 ────────────────────────────────────────────────────────────
def _load_original(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # JSONL (줄마다 JSON 객체)
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
    """(records: list, changelog: list) 반환."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # stage2_output.json 형식
    if "preprocessed_data" in data and "changelog" in data:
        return data["preprocessed_data"], data["changelog"]

    # report 형식 (changelog 없음)
    if "preprocessed_data" in data:
        return data["preprocessed_data"], []

    raise ValueError(f"알 수 없는 파일 형식: {path}")


# ── 값 유틸 ────────────────────────────────────────────────────────────────
def _is_nan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _norm(v):
    return None if _is_nan(v) else v


def _fmt(v) -> str:
    if v is None:
        return f"{_R}null{_NC}"
    if _is_nan(v):
        return f"{_R}NaN{_NC}"
    return str(v)


# ── 비교 핵심 로직 ─────────────────────────────────────────────────────────
def _diff_from_changelog(changelog: list,
                         filter_field, filter_action) -> dict:
    """changelog → {record_index: [(field, orig, new, action, reason)]}"""
    by_idx: dict = {}
    for entry in changelog:
        if entry.get("action") == "keep":
            continue
        field  = entry.get("field", "")
        action = entry.get("action", "")
        if filter_field  and field  != filter_field:
            continue
        if filter_action and action != filter_action:
            continue
        idx = entry.get("record_index", -1)
        by_idx.setdefault(idx, []).append((
            field,
            entry.get("original"),
            entry.get("new_value"),
            action,
            entry.get("reason", ""),
        ))
    return by_idx


def _diff_from_records(orig: dict, proc: dict,
                       filter_field, filter_action) -> list:
    """changelog 없을 때 값 직접 비교."""
    diffs = []
    for field in dict.fromkeys(list(orig.keys()) + list(proc.keys())):
        ov = _norm(orig.get(field))
        pv = _norm(proc.get(field))
        if ov == pv:
            continue
        if filter_field and field != filter_field:
            continue
        action = ("fill"      if ov is None else
                  "flag"      if pv is None else
                  "normalize")
        if filter_action and action != filter_action:
            continue
        diffs.append((field, ov, pv, action, ""))
    return diffs


# ── 출력 헬퍼 ──────────────────────────────────────────────────────────────
def _sep(char="─", width=70):
    print(f"  {char * width}")


def _print_header(orig_path, proc_path):
    print(f"\n{_C}{'='*72}{_NC}")
    print(f"{_C}  원본 vs 처리본 비교{_NC}")
    print(f"  원본  : {orig_path}")
    print(f"  처리본: {proc_path}")
    print(f"{_C}{'='*72}{_NC}\n")


# ── 메인 비교 함수 ─────────────────────────────────────────────────────────
def compare(original_path: str,
            processed_path: str,
            filter_field=None,
            filter_action=None,
            changed_only=False):

    orig_records             = _load_original(original_path)
    proc_records, changelog  = _load_processed(processed_path)

    total = min(len(orig_records), len(proc_records))
    if len(orig_records) != len(proc_records):
        print(f"{_Y}[경고] 레코드 수 불일치: 원본 {len(orig_records)} / 처리본 {len(proc_records)}{_NC}")

    has_changelog = bool(changelog)
    by_idx        = _diff_from_changelog(changelog, filter_field, filter_action) if has_changelog else {}

    # ── 레코드별 diff 수집 ──
    all_diffs   = []   # (rec_idx, id_val, [(field,orig,new,action,reason)])
    field_stats = {}   # field → {action: count}

    for i in range(total):
        orig = orig_records[i]
        proc = proc_records[i]

        record_diffs = (by_idx.get(i, []) if has_changelog
                        else _diff_from_records(orig, proc, filter_field, filter_action))

        for field, *_, action, _ in record_diffs:
            field_stats.setdefault(field, {})
            field_stats[field][action] = field_stats[field].get(action, 0) + 1

        if record_diffs:
            all_diffs.append((i, orig.get("id", i), record_diffs))

    # ── 요약 ──
    _print_header(original_path, processed_path)

    changed_cnt  = len(all_diffs)
    total_fields = sum(len(d[2]) for d in all_diffs)
    pct          = round(100 * changed_cnt / total) if total else 0

    print(f"  전체 레코드    : {total}건")
    print(f"  변경 레코드    : {_Y}{changed_cnt}건{_NC}  ({pct}%)")
    print(f"  총 필드 변경   : {total_fields}건")
    print(f"  changelog 출처 : {'stage2 changelog' if has_changelog else '직접 비교 (changelog 없음)'}\n")

    # ── 필드별 요약 표 ──
    print(f"{_C}[ 필드별 변경 현황 ]{_NC}")
    print(f"  {'필드':<22} {'normalize':>10} {'fill':>7} {'flag':>7}  {'합계':>5}")
    _sep()
    for field, acts in sorted(field_stats.items()):
        n  = acts.get("normalize", 0)
        fi = acts.get("fill",      0)
        fl = acts.get("flag",      0)
        print(f"  {field:<22} {n:>10} {fi:>7} {fl:>7}  {n+fi+fl:>5}")
    _sep()
    tot_n  = sum(a.get("normalize", 0) for a in field_stats.values())
    tot_fi = sum(a.get("fill",      0) for a in field_stats.values())
    tot_fl = sum(a.get("flag",      0) for a in field_stats.values())
    print(f"  {'합계':<22} {tot_n:>10} {tot_fi:>7} {tot_fl:>7}  {tot_n+tot_fi+tot_fl:>5}")

    # ── 레코드별 상세 ──
    if not all_diffs:
        print(f"\n  {_G}변경된 레코드가 없습니다.{_NC}\n")
        return

    skip_unchanged = changed_only
    print(f"\n{_C}[ 레코드별 변경 상세 ]{_NC}")
    for rec_idx, id_val, record_diffs in all_diffs:
        print(f"\n  {_Y}── Record #{rec_idx}  (id={id_val})  {len(record_diffs)}개 필드{_NC}")
        for field, ov, pv, action, reason in record_diffs:
            col = _ACTION_COLOR.get(action, _NC)
            tag = f"{col}[{action:<9}]{_NC}"
            print(f"    {tag} {field:<18}  {_fmt(ov):>30} → {_fmt(pv)}")
            if reason:
                print(f"             {_C}↳ {reason}{_NC}")

    print(f"\n{_C}{'='*72}{_NC}\n")


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="원본 ↔ 처리본 레코드 단위 비교",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("original",  help="원본 파일 (JSON/JSONL)")
    ap.add_argument("processed", help="처리본 파일 (stage2_output.json 또는 report.json)")
    ap.add_argument("--field",   help="특정 필드만 표시 (예: email)")
    ap.add_argument("--action",  choices=["normalize", "fill", "flag"],
                    help="특정 액션만 표시")
    ap.add_argument("--changed-only", action="store_true",
                    help="변경된 레코드만 표시")
    args = ap.parse_args()

    compare(args.original, args.processed,
            filter_field=args.field,
            filter_action=args.action,
            changed_only=args.changed_only)


if __name__ == "__main__":
    main()
