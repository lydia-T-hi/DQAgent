# Skill: Preprocessor Agent (Claude)

## Role
Claude LLM(claude-sonnet-4-6)을 사용해 입력 데이터를 정제·정규화한다.
변환 이력(changelog)과 이상치(anomalies)를 기록하여 하위 에이전트에 전달한다.

## LLM
- Provider: Anthropic
- Model: claude-sonnet-4-6
- 환경변수: `ANTHROPIC_API_KEY`

## Inputs (from input-agent)
```json
{
  "validated_input": "<원본 데이터>",
  "source_file": "<파일명>",
  "validation_errors": []
}
```

## 수행 작업
1. 날짜 → ISO 8601 정규화
2. 숫자 타입 정확도 통일 (int / float)
3. 텍스트 케이싱 일관성
4. 필드명 → snake_case
5. 추론 가능한 누락값 보완
6. 의심 값 anomalies 플래그

## Outputs
```json
{
  "preprocessed_data": "<정제된 데이터>",
  "changelog": [
    {"field": "", "action": "", "before": "", "after": "", "reason": ""}
  ],
  "anomalies": [
    {"field": "", "value": "", "reason": ""}
  ],
  "source_file": "<파일명>"
}
```

## 다음 에이전트 (병렬 브로드캐스트)
→ `dq-llm-agent`  
→ `dq-code-agent`
