# Preciso Oracle Cloud 자동 배포 스크립트
# 수정된 파일을 Oracle Ubuntu 서버에 배포

param(
    [Parameter(Mandatory=$false)]
    [string]$ServerIP = "",
    
    [Parameter(Mandatory=$false)]
    [string]$SSHUser = "ubuntu"
)

$ErrorActionPreference = "Stop"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Preciso Oracle Cloud 배포" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# SSH 키 경로
$SSHKey = "C:\Users\Administrator\Downloads\ssh-key-2026-01-30.key"

if (-not (Test-Path $SSHKey)) {
    Write-Host "❌ SSH 키를 찾을 수 없습니다: $SSHKey" -ForegroundColor Red
    exit 1
}

# 서버 IP 입력
if (-not $ServerIP) {
    Write-Host "Oracle 서버 IP 주소를 입력하세요:" -ForegroundColor Yellow
    Write-Host "(Oracle Cloud Console → Compute → Instances에서 확인)" -ForegroundColor Gray
    $ServerIP = Read-Host "Server IP"
}

if (-not $ServerIP) {
    Write-Host "❌ 서버 IP가 필요합니다" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 배포 정보:" -ForegroundColor Yellow
Write-Host "  Server: ${SSHUser}@${ServerIP}" -ForegroundColor White
Write-Host "  SSH Key: $SSHKey" -ForegroundColor White
Write-Host ""

# 배포할 파일 목록
$files = @(
    @{Local="app\ui\index.html"; Remote="/opt/preciso/app/ui/index.html"},
    @{Local="app\ui\debug.html"; Remote="/opt/preciso/app/ui/debug.html"},
    @{Local="app\main.py"; Remote="/opt/preciso/app/main.py"}
)

$baseDir = "C:\Users\Administrator\Desktop\preciso"

# 파일 존재 확인
Write-Host "🔍 파일 확인 중..." -ForegroundColor Yellow
foreach ($file in $files) {
    $localPath = Join-Path $baseDir $file.Local
    if (-not (Test-Path $localPath)) {
        Write-Host "❌ 파일 없음: $localPath" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ $($file.Local)" -ForegroundColor Green
}

Write-Host ""
Write-Host "🚀 배포 시작..." -ForegroundColor Yellow
Write-Host ""

# 파일 업로드
foreach ($file in $files) {
    $localPath = Join-Path $baseDir $file.Local
    $remotePath = $file.Remote
    
    Write-Host "📤 업로드: $($file.Local)" -ForegroundColor Cyan
    
    try {
        & scp -i $SSHKey -o StrictHostKeyChecking=no $localPath "${SSHUser}@${ServerIP}:${remotePath}"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ 성공" -ForegroundColor Green
        } else {
            Write-Host "   ❌ 실패 (exit code: $LASTEXITCODE)" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "   ❌ 실패: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "🔄 Preciso 서비스 재시작 중..." -ForegroundColor Yellow

try {
    & ssh -i $SSHKey -o StrictHostKeyChecking=no "${SSHUser}@${ServerIP}" "sudo systemctl restart preciso"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 서비스 재시작 완료" -ForegroundColor Green
    } else {
        Write-Host "⚠️  서비스 재시작 실패 (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  서비스 재시작 실패: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📊 서비스 상태 확인 중..." -ForegroundColor Yellow
Write-Host ""

try {
    & ssh -i $SSHKey -o StrictHostKeyChecking=no "${SSHUser}@${ServerIP}" "sudo systemctl status preciso --no-pager -l | head -20"
} catch {
    Write-Host "⚠️  상태 확인 실패" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "✅ 배포 완료!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "1. 브라우저 캐시 클리어 (Ctrl+Shift+Delete)" -ForegroundColor White
Write-Host "2. 테스트: https://preciso-data.com/" -ForegroundColor Cyan
Write-Host "3. 테스트: https://preciso-data.com/debug.html" -ForegroundColor Cyan
Write-Host "4. F12 → Console에서 에러 확인" -ForegroundColor White
Write-Host ""
Write-Host "로그 확인:" -ForegroundColor Yellow
$logCmd = "ssh -i $SSHKey ${SSHUser}@${ServerIP} 'sudo journalctl -u preciso -f'"
Write-Host "  $logCmd" -ForegroundColor Gray
Write-Host ""
