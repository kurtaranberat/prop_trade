# IOFAE VPS SETUP SCRIPT (Windows PowerShell)
# Bu scripti VPS içinde PowerShell'i yönetici olarak açıp yapıştırın.

Write-Host "🚀 IOFAE Bot Kurulumu Başlıyor..." -ForegroundColor Cyan

# 1. Python Kurulumu (Eğer yoksa)
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "📥 Python indiriliyor..." -ForegroundColor Yellow
    $url = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    $outpath = "$env:TEMP\python-setup.exe"
    Invoke-WebRequest -Uri $url -OutFile $outpath
    Write-Host "⚙️ Python kuruluyor..." -ForegroundColor Yellow
    Start-Process -FilePath $outpath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    Write-Host "✅ Python kuruldu." -ForegroundColor Green
} else {
    Write-Host "✅ Python zaten yüklü." -ForegroundColor Green
}

# 2. Gerekli Kütüphaneler
Write-Host "📦 Python kütüphaneleri yükleniyor..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install MetaTrader5 pandas numpy sqlalchemy pyyaml aiohttp

# 3. Klasör Yapısı
$botPath = "C:\IOFAE_Bot"
if (!(Test-Path $botPath)) {
    New-Item -Path $botPath -ItemType Directory
    Write-Host "✅ C:\IOFAE_Bot klasörü oluşturuldu." -ForegroundColor Green
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "🎉 KURULUM TAMAMLANDI!" -ForegroundColor Green
Write-Host "Şimdi yapmanız gerekenler:" -ForegroundColor White
Write-Host "1. MT5 Terminalini VPS'e kurun ve hesabınıza giriş yapın." -ForegroundColor White
Write-Host "2. Bot dosyalarını (main.py, config.yaml vb.) C:\IOFAE_Bot içine kopyalayın." -ForegroundColor White
Write-Host "3. config.yaml dosyasını düzenleyin." -ForegroundColor White
Write-Host "4. 'python main.py' komutu ile botu başlatın." -ForegroundColor White
Write-Host "====================================================" -ForegroundColor Cyan
