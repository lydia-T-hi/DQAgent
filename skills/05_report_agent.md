# Skill: Report Agent

## Role
Agent 3(DQ-LLM)과 Agent 4(DQ-Code)의 결과를 병합하여
최종 DQ 보고서 JSON을 생성하고 report/ 폴더에 저장한다.

## Inputs (from dq-llm-agent + dq-code-agent)
- `preprocessor_msg`: 전처리 결과 및 changelog
- `llm_msg`: OpenAI DQ 검증 결과
- `code_msg`: Python 코드 검증 결과

## 병합 전략
1. LLM 이슈 목록에 `"source": "llm_validation"` 태그 추가
2. 코드 검증 실패 항목을 동일한 이슈 포맷으로 변환 (`"source": "code_validation"`)
3. 전체 이슈를 severity(critical / warning / info)로 분류
4. 중복 이슈는 description 기반으로 확인 (현재는 단순 합산)

## 출력 파일명 규칙
```
{원본파일명(확장자 제외)}_report_{YYYYMMDD}.json
```
저장 위치: `report/` 폴더 (CLI에서 `--output-dir`로 변경 가능)

## 최종 보고서 구조
```json
{
  "metadata": {
    "pipeline_id": "",
    "source_file": "",
    "generated_at": "",
    "report_version": "1.0"
  },
  "final_preprocessed_data": {},
  "preprocessing_summary": {
    "changelog": [],
    "anomalies_detected": []
  },
  "dq_validation": {
    "overall_score": 0,
    "total_issues": 0,
    "by_severity": {"critical": 0, "warning": 0, "info": 0},
    "issues": {
      "critical": [],
      "warning": [],
      "info": []
    }
  },
  "llm_validation": {
    "engine": "gpt-4o",
    "overall_score": 0,
    "summary": ""
  },
  "code_validation": {
    "engine": "python-code-snippet (claude-generated)",
    "code_snippet": "",
    "summary": {},
    "results": []
  }
}
```
