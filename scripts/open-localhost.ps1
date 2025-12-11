# Script untuk membuka localhost di browser
# Usage: .\open-localhost.ps1 [frontend|backend|both]

param(
    [string]$Target = "both"
)

$FrontendURL = "http://localhost:5173"
$BackendURL = "http://localhost:5000"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  COFIND - Buka Localhost" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

switch ($Target.ToLower()) {
    "frontend" {
        Write-Host "Membuka Frontend: $FrontendURL" -ForegroundColor Green
        Start-Process $FrontendURL
    }
    "backend" {
        Write-Host "Membuka Backend: $BackendURL" -ForegroundColor Green
        Start-Process $BackendURL
    }
    "both" {
        Write-Host "Membuka Frontend: $FrontendURL" -ForegroundColor Green
        Start-Process $FrontendURL
        Start-Sleep -Seconds 1
        Write-Host "Membuka Backend: $BackendURL" -ForegroundColor Green
        Start-Process $BackendURL
    }
    default {
        Write-Host "Usage: .\open-localhost.ps1 [frontend|backend|both]" -ForegroundColor Yellow
        Write-Host "Default: both" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "✓ Selesai!" -ForegroundColor Green

