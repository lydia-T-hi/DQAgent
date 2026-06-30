# Skill: DQ-Code Agent (Python Code Snippet)

## Role
Claude가 데이터에 맞는 Python 검증 코드를 생성하고, 그 코드를 실제로 실행하여
규칙 기반 DQ 검사 및 할루시네이션을 탐지한다.

## LLM (코드 생성용)
- Provider: Anthropic
- Model: claude-sonnet-4-6
- 환경변수: `ANTHROPIC_API_KEY`

## Inputs (from preprocessor-agent, 병렬 수신)
```json
{
  "preprocessed_data": "<전처리된 데이터>",
  "source_file": "<파일명>"
}
```

## 처리 흐름
```
1. Claude에게 데이터 구조를 제공
2. Claude가 validate_data(data) Python 함수 생성
3. exec()로 함수 실행 (격리된 namespace)
4. 결과 집계 및 할루시네이션 플래그 추출
```

## 생성 코드 계약 (validate_data 반환 형식)
```python
[
  {
    "field": str,           # 검사 대상 필드명
    "rule": str,            # 검사 규칙 설명
    "passed": bool,         # 통과 여부
    "actual_value": any,    # 실제 값
    "expected": str,        # 기댓값 또는 허용 범위
    "hallucination_flag": bool  # 불가능한 값 여부
  }
]
```

## 할루시네이션 탐지 예시
- 미래 날짜가 생년월일로 사용된 경우
- 음수 나이 / 200세 이상
- 존재하지 않는 국가 코드
- 이메일 형식이지만 완전히 조작된 도메인

## Outputs
```json
{
  "dq_code_report": {
    "code_snippet": "<생성된 Python 코드>",
    "validation_results": [],
    "summary": {
      "total_checks": 0,
      "passed": 0,
      "failed": 0,
      "hallucination_flags": 0
    }
  },
  "source_file": "<파일명>"
}
```

## 다음 에이전트
→ `report-agent`
