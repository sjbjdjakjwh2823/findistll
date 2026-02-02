# Cloudflare DNS 자동 설정 스크립트
# preciso-data.com을 Cloudflare Tunnel로 연결

param(
    [Parameter(Mandatory=$false)]
    [string]$CloudflareEmail,
    
    [Parameter(Mandatory=$false)]
    [string]$CloudflareApiKey
)

$TunnelId = "5a5103d3-b6cd-4702-ada9-b6558f326893"
$Domain = "preciso-data.com"
$TunnelCNAME = "$TunnelId.cfargotunnel.com"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Cloudflare DNS 설정 도구" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

if (-not $CloudflareEmail -or -not $CloudflareApiKey) {
    Write-Host "⚠️  Cloudflare API 인증 정보가 필요합니다" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "대신 수동으로 설정하세요:" -ForegroundColor White
    Write-Host ""
    Write-Host "1. Cloudflare 대시보드 접속:" -ForegroundColor Yellow
    Write-Host "   https://dash.cloudflare.com" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "2. preciso-data.com 도메인 선택" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "3. DNS → Records 메뉴로 이동" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "4. 기존 레코드 찾기 및 삭제:" -ForegroundColor Yellow
    Write-Host "   - Name: @ 또는 preciso-data.com" -ForegroundColor White
    Write-Host "   - Content: sdkfsklf-asura.hf.space (또는 IP 주소)" -ForegroundColor White
    Write-Host ""
    Write-Host "5. 새 CNAME 레코드 추가:" -ForegroundColor Yellow
    Write-Host "   Type: CNAME" -ForegroundColor White
    Write-Host "   Name: @" -ForegroundColor White
    Write-Host "   Content: $TunnelCNAME" -ForegroundColor Green
    Write-Host "   Proxy: ON (주황색 구름 아이콘)" -ForegroundColor White
    Write-Host "   TTL: Auto" -ForegroundColor White
    Write-Host ""
    Write-Host "6. 저장 후 5분 대기" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "7. 테스트:" -ForegroundColor Yellow
    Write-Host "   https://preciso-data.com/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 복사용 CNAME 값:" -ForegroundColor Yellow
    Write-Host $TunnelCNAME -ForegroundColor Green
    Write-Host ""
    
    # 클립보드에 복사
    try {
        Set-Clipboard -Value $TunnelCNAME
        Write-Host "✅ CNAME 값이 클립보드에 복사되었습니다!" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  클립보드 복사 실패" -ForegroundColor Yellow
    }
    
    exit 0
}

# API를 사용한 자동 설정 (향후 구현)
Write-Host "🔧 API를 사용한 자동 설정..." -ForegroundColor Yellow
Write-Host "Email: $CloudflareEmail" -ForegroundColor White
Write-Host ""

# Zone ID 가져오기
$headers = @{
    "X-Auth-Email" = $CloudflareEmail
    "X-Auth-Key" = $CloudflareApiKey
    "Content-Type" = "application/json"
}

try {
    $zonesResponse = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones?name=$Domain" -Headers $headers -Method Get
    
    if ($zonesResponse.success -and $zonesResponse.result.Count -gt 0) {
        $zoneId = $zonesResponse.result[0].id
        Write-Host "✅ Zone ID: $zoneId" -ForegroundColor Green
        
        # 기존 DNS 레코드 찾기
        $dnsResponse = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records?name=$Domain" -Headers $headers -Method Get
        
        if ($dnsResponse.success -and $dnsResponse.result.Count -gt 0) {
            foreach ($record in $dnsResponse.result) {
                Write-Host "🗑️  기존 레코드 삭제: $($record.type) $($record.name) → $($record.content)" -ForegroundColor Yellow
                Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records/$($record.id)" -Headers $headers -Method Delete | Out-Null
            }
        }
        
        # 새 CNAME 레코드 추가
        $newRecord = @{
            type = "CNAME"
            name = "@"
            content = $TunnelCNAME
            proxied = $true
            ttl = 1
        } | ConvertTo-Json
        
        $createResponse = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records" -Headers $headers -Method Post -Body $newRecord
        
        if ($createResponse.success) {
            Write-Host "✅ DNS 레코드 생성 완료!" -ForegroundColor Green
            Write-Host "   $Domain → $TunnelCNAME" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "⏳ DNS 전파 대기 중 (약 1-5분)..." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "테스트: https://preciso-data.com/" -ForegroundColor Cyan
        } else {
            Write-Host "❌ DNS 레코드 생성 실패" -ForegroundColor Red
            Write-Host $createResponse.errors -ForegroundColor Red
        }
    } else {
        Write-Host "❌ Zone을 찾을 수 없습니다" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ API 요청 실패: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "수동으로 설정해주세요 (위의 안내 참조)" -ForegroundColor Yellow
}
