"""
PreToolUse Hook: ANTHROPIC_API_KEY 노출 방지
Bash 명령어에 ANTHROPIC_API_KEY가 포함되어 있으면 차단합니다.

이 프로젝트에서 Stage 2B는 Claude CLI를 OAuth로 호출합니다.
subprocess env에서 ANTHROPIC_API_KEY를 의도적으로 제거하는데,
Bash 명령으로 직접 노출하면 크레딧이 소모되거나 키가 로그에 기록됩니다.
"""
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


_DANGER_PATTERNS = [
    "ANTHROPIC_API_KEY=sk-",
    "ANTHROPIC_API_KEY =",
    "--api-key sk-ant",
]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        return

    command = data.get("tool_input", {}).get("command", "")

    for pattern in _DANGER_PATTERNS:
        if pattern in command:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        f"ANTHROPIC_API_KEY가 명령어에 직접 포함되어 있습니다.\n"
                        f"이 프로젝트는 Claude CLI OAuth를 사용합니다.\n"
                        f"키를 명령어에 포함하면 크레딧이 소모될 수 있습니다.\n"
                        f"의도한 명령이 맞다면 허용(Allow)을 선택하세요."
                    ),
                }
            }
            print(json.dumps(output, ensure_ascii=False))
            return

    print(json.dumps({}))


if __name__ == "__main__":
    main()
