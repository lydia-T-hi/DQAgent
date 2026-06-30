# DQ Multi-Agent Pipeline — Windows PowerShell 실행 훅
# Usage:
#   .\run_dq.ps1 sample_input.csv
#   .\run_dq.ps1 sample_input.jsonl --batch-size 100
#   .\run_dq.ps1 sample_input.csv --skip-openai

param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$FilePath,

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  DQ Multi-Agent Pipeline" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# .env 로드
$EnvFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*?)\s*$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    Write-Host "  [OK] .env 로드 완료" -ForegroundColor Green
} else {
    Write-Host "  [!] .env 파일 없음 — API 키를 환경변수로 직접 설정하세요" -ForegroundColor Yellow
}

# Python 확인
try {
    $pyVer = python --version 2>&1
    Write-Host "  [OK] $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python을 찾을 수 없습니다." -ForegroundColor Red
    exit 1
}

# 필수 패키지 확인
$checkPkg = python -c "import duckdb, pandas, langchain_core, dotenv" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] 필수 패키지가 없습니다. 아래 명령을 실행하세요:" -ForegroundColor Red
    Write-Host "    pip install -r requirements.txt"
    exit 1
}
Write-Host "  [OK] 패키지 확인 완료" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 실행
$Start = Get-Date
python main.py $FilePath @Rest
$ExitCode = $LASTEXITCODE
$Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
if ($ExitCode -eq 0) {
    Write-Host "  소요 시간: ${Elapsed}초" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] 실행 실패 (종료코드: $ExitCode)" -ForegroundColor Red
}
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

exit $ExitCode
