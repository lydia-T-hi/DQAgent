"""
PostToolUse Hook: Python 문법 검사
Write|Edit 후 .py 파일에 대해 py_compile을 실행합니다.
문법 오류가 있으면 systemMessage로 경고합니다.
"""
import json
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({}))
        return

    file_path = (
        data.get("tool_input", {}).get("file_path")
        or data.get("tool_response", {}).get("filePath")
        or ""
    )

    if not file_path.endswith(".py"):
        print(json.dumps({}))
        return

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", file_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        error_msg = (result.stderr or result.stdout or "알 수 없는 오류").strip()
        output = {
            "systemMessage": f"[문법 오류] {file_path}\n{error_msg}",
        }
    else:
        output = {}

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
