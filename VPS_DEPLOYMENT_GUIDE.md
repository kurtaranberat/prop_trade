# 🌐 IOFAE VPS Deployment Rehberi

Bu rehber, botu bir Windows VPS üzerinde 7/24 çalışacak şekilde kurmanıza yardımcı olur.

## 1. VPS Hazırlığı
1. VPS'e RDP (Remote Desktop) ile bağlanın.
2. `vps_setup.ps1` dosyasını VPS'e kopyalayın veya içeriğini kopyalayıp PowerShell'e yapıştırın.
3. PowerShell'i **Yönetici (Administrator)** olarak çalıştırın ve scripti yürütün.

## 2. MetaTrader 5 Kurulumu
1. VPS içindeki tarayıcıdan broker'ınızın (örn: ICMarkets) MT5 terminalini indirin.
2. Kurulumu tamamlayın ve **Demo/Real** hesabınıza giriş yapın.
3. **ÖNEMLİ:** MT5 -> Tools -> Options -> Expert Advisors sekmesine gidin.
   - [x] Allow algorithmic trading
   - [x] Allow WebRequest for listed URL (Telegram bildirimleri için gereklidir)
     - `https://api.telegram.org` ekleyin.

## 3. Botun Taşınması
1. Yerel bilgisayarınızdaki `iofae_bot` klasörünü VPS'teki `C:\IOFAE_Bot` dizinine kopyalayın.
2. `config.yaml` dosyasını VPS'teki yeni MT5 login bilgilerinizle güncelleyin.

## 4. Botu Başlatma
PowerShell veya CMD açın:
```cmd
cd C:\IOFAE_Bot
python main.py
```

## 5. 7/24 İzleme İpuçları
- **Log Takibi:** `C:\IOFAE_Bot\logs\iofae.log` dosyasını takip ederek botun ne yaptığını görebilirsiniz.
- **Telegram:** Botun Telegram modülünü aktif ederseniz, VPS'e bağlanmadan telefonunuzdan anlık bildirim alabilirsiniz.
- **Auto-Restart:** VPS yeniden başlarsa botun otomatik açılması için `main.py` dosyasının bir kısayolunu Windows "Startup" klasörüne ekleyebilirsiniz.

---

### 🚀 Neden VPS?
- **Düşük Latency:** VPS'ler genelde broker sunucularına çok yakındır (Londra/NY), bu da emirlerin milisaniyeler içinde iletilmesini sağlar.
- **Stabilite:** Evdeki internet gitse bile botunuz kurumların önünde olmaya devam eder.
- **Güvenlik:** Botunuz izole bir ortamda çalışır.
