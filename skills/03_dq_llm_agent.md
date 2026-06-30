# Skill: DQ-LLM Agent (OpenAI)

## Role
GPT-4o를 사용해 전처리된 데이터의 의미론적 품질을 검증한다.
규칙으로는 잡기 어려운 도메인 지식 기반 이상치를 탐지한다.

## LLM
- Provider: OpenAI
- Model: gpt-4o
- 환경변수: `OPENAI_API_KEY`
- response_format: json_object (JSON mode 강제)

## Inputs (from preprocessor-agent, 병렬 수신)
```json
{
  "preprocessed_data": "<전처리된 데이터>",
  "changelog": [],
  "source_file": "<파일명>"
}
```

## 검증 차원
| 차원 | 설명 |
|------|------|
| consistency | 필드 간 의미적 일관성 (생년월일 ↔ 나이) |
| completeness | 필수 필드 누락 여부 |
| accuracy | 도메인 기반 사실 정확성 |
| validity | 값 형식·범위 유효성 |
| uniqueness | 중복 레코드 감지 |

## Outputs
```json
{
  "dq_llm_report": {
    "dq_issues": [
      {
        "field": "",
        "issue_type": "consistency|completeness|accuracy|validity|uniqueness",
        "severity": "critical|warning|info",
        "confidence": 0.0,
        "description": "",
        "suggested_fix": ""
      }
    ],
    "overall_score": 0,
    "summary": ""
  },
  "source_file": "<파일명>"
}
```

## 다음 에이전트
→ `report-agent`
