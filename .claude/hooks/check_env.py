"""
SessionStart Hook: 실행 환경 사전 점검
- Claude CLI 설치 여부
- .env 파일 존재 여부
- report/ 디렉토리 존재 여부 (없으면 자동 생성)
- ANTHROPIC_API_KEY 설정 경고 (설정되어 있으면 OAuth 대신 크레딧 소모)
"""
import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    warnings = []
    # __file__ = .claude/hooks/check_env.py → dirname x3 = project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Claude CLI 설치 확인
    if not shutil.which("claude"):
        warnings.append("⚠ Claude CLI가 설치되지 않았습니다. Stage 2B가 실행되지 않습니다.")
    else:
        # Claude CLI 버전 확인
        try:
            r = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=5
            )
            version = r.stdout.strip() or r.stderr.strip()
        except Exception:
            version = "(확인 불가)"

    # .env 파일 확인
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        warnings.append("⚠ .env 파일이 없습니다. OpenAI Stage 3A 사용 시 OPENAI_API_KEY가 필요합니다.")

    # ANTHROPIC_API_KEY 경고
    if os.environ.get("ANTHROPIC_API_KEY"):
        warnings.append(
            "⚠ ANTHROPIC_API_KEY가 환경변수에 설정되어 있습니다.\n"
            "  Stage 2B는 이 키를 subprocess에서 자동으로 제외하지만,\n"
            "  직접 Claude API를 호출하는 코드가 있다면 크레딧을 소모할 수 있습니다."
        )

    # report/ 디렉토리 자동 생성
    report_dir = os.path.join(project_root, "report")
    if not os.path.exists(report_dir):
        os.makedirs(report_dir, exist_ok=True)
        warnings.append("ℹ report/ 디렉토리를 생성했습니다.")

    # tests/output/ 디렉토리 자동 생성
    tests_out = os.path.join(project_root, "tests", "output")
    if not os.path.exists(tests_out):
        os.makedirs(tests_out, exist_ok=True)

    if warnings:
        output = {"systemMessage": "\n".join(warnings)}
    else:
        output = {}

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
