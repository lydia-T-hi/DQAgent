# Skill: Input Agent

## Role
JSON 파일을 수신하고 기본 구조 검증을 수행한다.

## Inputs
| 파라미터 | 타입 | 설명 |
|----------|------|------|
| input_path | str | 검증할 JSON 파일의 경로 |
| pipeline_id | str | Orchestrator가 부여한 파이프라인 ID |

## Outputs
```json
{
  "validated_input": "<원본 데이터 그대로>",
  "source_file": "<파일명 (basename)>",
  "validation_errors": ["<오류 메시지 목록, 없으면 빈 배열>"]
}
```

## 검증 항목
- 파일 존재 여부
- JSON 파싱 가능 여부 (JSONDecodeError 감지)
- 루트 요소가 object 또는 array인지 확인
- 배열인 경우 빈 배열 여부 경고

## 상태 코드
| status | 의미 |
|--------|------|
| success | 검증 통과 |
| warning | 파싱은 됐지만 구조 경고 있음 |
| error | 파일 없음 또는 파싱 불가 (파이프라인 중단) |

## 다음 에이전트
→ `preprocessor-agent`
