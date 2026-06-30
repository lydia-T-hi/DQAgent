"""
PostToolUse Hook: 파이프라인 완료 알림
Bash에서 main.py 실행이 완료되면 최신 보고서 파일명을 알려줍니다.
"""
import glob
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        return

    command = data.get("tool_input", {}).get("command", "")

    # main.py 실행 명령이 아니면 무시
    if "main.py" not in command:
        print(json.dumps({}))
        return

    # 종료 코드 확인 (실패 시 무시)
    tool_response = data.get("tool_response", {})
    if tool_response.get("exit_code", 0) != 0:
        print(json.dumps({}))
        return

    # 최신 보고서 파일 찾기
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    report_dir   = os.path.join(project_root, "report")
    reports      = sorted(glob.glob(os.path.join(report_dir, "*.json")), reverse=True)

    if reports:
        latest = os.path.relpath(reports[0], project_root)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"최신 보고서: {latest}",
            }
        }
    else:
        output = {}

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
