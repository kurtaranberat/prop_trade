# IOFAE - Windows Development Environment Setup
# Bu script Python, Git ve VS Code kurulumlarını otomatik olarak yapar.

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "🚀 Windows Geliştirici Ortamı Kurulumu Başlıyor..." -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Winget Kontrolü
if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "❌ winget bulunamadı. Lütfen Windows'unuzun güncel olduğundan emin olun." -ForegroundColor Red
    exit
}

function Install-App {
    param (
        [string]$AppName,
        [string]$PackageId
    )
    
    Write-Host "🔍 $AppName kontrol ediliyor..." -ForegroundColor Yellow
    $check = winget list --id $PackageId -e
    
    if ($check -match $PackageId) {
        Write-Host "✅ $AppName zaten yüklü." -ForegroundColor Green
    } else {
        Write-Host "📥 $AppName kuruluyor..." -ForegroundColor Yellow
        winget install --id $PackageId -e --silent --accept-source-agreements --accept-package-agreements
        Write-Host "✅ $AppName başarıyla kuruldu." -ForegroundColor Green
    }
}

# 2. Uygulamaları Kur
# Python 3.10 (Stabil ve MT5 ile uyumlu)
Install-App "Python 3.10" "Python.Python.3.10"

# Git
Install-App "Git" "Git.Git"

# VS Code
Install-App "Visual Studio Code" "Microsoft.VisualStudioCode"

# 3. Python Kütüphanelerini Kur (Bot için gerekli)
Write-Host "`n📦 Bot için gerekli Python kütüphaneleri yükleniyor..." -ForegroundColor Yellow
Start-Sleep -Seconds 2 # PATH'in güncellenmesi için kısa bir bekleme
& python -m pip install --upgrade pip
& pip install MetaTrader5 pandas numpy sqlalchemy pyyaml aiohttp python-telegram-bot

# 4. VS Code Eklentileri (Opsiyonel ama önerilir)
Write-Host "🔌 VS Code Python eklentisi kuruluyor..." -ForegroundColor Yellow
& code --install-extension ms-python.python --force

Write-Host "`n====================================================" -ForegroundColor Cyan
Write-Host "🎉 TÜM KURULUMLAR TAMAMLANDI!" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Önemli Notlar:" -ForegroundColor White
Write-Host "1. Değişikliklerin (PATH) tam uygulanması için PowerShell'i kapatıp açın." -ForegroundColor White
Write-Host "2. 'python --version' ve 'git --version' komutları ile kontrol edebilirsiniz." -ForegroundColor White
Write-Host "3. VS Code'u başlatmak için terminale 'code .' yazabilirsiniz." -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Cyan
