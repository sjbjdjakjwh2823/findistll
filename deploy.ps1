param(
    [string]$ServerIP = "",
    [string]$User = "ubuntu"
)

$SSHKey = "C:\Users\Administrator\Downloads\ssh-key-2026-01-30.key"
$BaseDir = "C:\Users\Administrator\Desktop\preciso"

Write-Host "Preciso Oracle Cloud Deploy" -ForegroundColor Cyan
Write-Host ""

if (-not $ServerIP) {
    $ServerIP = Read-Host "Enter Oracle Server IP"
}

if (-not $ServerIP) {
    Write-Host "Error: Server IP required" -ForegroundColor Red
    exit 1
}

Write-Host "Server: $User@$ServerIP" -ForegroundColor Yellow
Write-Host "SSH Key: $SSHKey" -ForegroundColor Yellow
Write-Host ""

$files = @(
    "app\ui\index.html",
    "app\ui\debug.html",
    "app\main.py"
)

Write-Host "Uploading files..." -ForegroundColor Yellow

foreach ($file in $files) {
    $local = Join-Path $BaseDir $file
    $remote = "/opt/preciso/$($file.Replace('\', '/'))"
    
    Write-Host "  $file" -ForegroundColor Cyan
    & scp -i $SSHKey -o StrictHostKeyChecking=no $local "${User}@${ServerIP}:${remote}"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    OK" -ForegroundColor Green
    } else {
        Write-Host "    FAILED" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Restarting service..." -ForegroundColor Yellow

& ssh -i $SSHKey -o StrictHostKeyChecking=no "${User}@${ServerIP}" "sudo systemctl restart preciso"

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Service restarted" -ForegroundColor Green
} else {
    Write-Host "  Restart failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "Checking status..." -ForegroundColor Yellow
& ssh -i $SSHKey -o StrictHostKeyChecking=no "${User}@${ServerIP}" "sudo systemctl status preciso --no-pager | head -15"

Write-Host ""
Write-Host "Deploy complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Clear browser cache (Ctrl+Shift+Delete)"
Write-Host "2. Test: https://preciso-data.com/"
Write-Host "3. Test: https://preciso-data.com/debug.html"
Write-Host ""
