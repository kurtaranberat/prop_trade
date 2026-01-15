# 🚀 IOFAE Canlı Veri Testi Kurulum Rehberi

## Gereksinimler

### 1. MetaTrader 5 Kurulumu

MT5, Windows üzerinde çalışır. Linux kullanıyorsan iki seçenek var:

#### Seçenek A: Windows Kullan (Önerilen)
- Windows PC veya VPS'te MT5 kur
- Python scriptlerini Windows'ta çalıştır

#### Seçenek B: Linux + Wine
```bash
# Wine kurulumu (Ubuntu/Debian)
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install wine64 wine32 winetricks

# MT5'i Wine ile kur
winetricks corefonts
wine mt5setup.exe
```

### 2. Broker Hesabı

Önerilen brokerlar (MT5 destekli):
- **ICMarkets** - Düşük spread, ECN
- **Pepperstone** - Hızlı execution
- **FxPro** - İyi DOM desteği
- **XM** - Demo hesap kolay

#### Demo Hesap Açma:
1. Broker sitesine git
2. Demo hesap aç (100K sanal para)
3. MT5 giriş bilgilerini al:
   - Login numarası
   - Şifre
   - Sunucu adı

### 3. Python Kurulumu

```bash
# Sanal ortam oluştur
cd /home/berat/Desktop/Berat/prop_trade/iofae_bot
python -m venv venv
source venv/bin/activate  # Linux
# veya: venv\Scripts\activate  # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

## Konfigürasyon

### config.yaml Düzenle:

```yaml
# MT5 Bağlantı Bilgileri
mt5:
  login: 12345678              # Broker'dan aldığın login
  password: "your_password"    # Broker'dan aldığın şifre
  server: "ICMarkets-Demo"     # Broker sunucu adı
  timeout: 60000

# Trading Parametreleri
trading:
  symbol: "EURUSD"             # İşlem çifti
  magic_number: 123456         
  entry_offset_pips: 7         
  stop_loss_pips: 10           
  min_score_threshold: 90      

# Risk Yönetimi
risk:
  risk_per_trade: 0.01         # %1 risk
  max_daily_loss: 0.05         # %5 günlük limit
  max_trades_per_day: 3        

# Telegram (Opsiyonel)
telegram:
  enabled: false               # Önce false bırak
  bot_token: ""
  chat_id: ""
```

## Test Adımları

### Adım 1: MT5 Bağlantı Testi

```bash
python -c "
import MetaTrader5 as mt5

# MT5'i başlat
if mt5.initialize():
    print('✅ MT5 başlatıldı')
    info = mt5.terminal_info()
    print(f'   Path: {info.path}')
    print(f'   Data: {info.data_path}')
    mt5.shutdown()
else:
    print('❌ MT5 başlatılamadı:', mt5.last_error())
"
```

### Adım 2: Hesap Bağlantı Testi

```bash
python -c "
import MetaTrader5 as mt5

mt5.initialize(
    login=12345678,
    password='your_password',
    server='ICMarkets-Demo'
)

account = mt5.account_info()
if account:
    print('✅ Hesap bağlandı')
    print(f'   Login: {account.login}')
    print(f'   Balance: ${account.balance}')
    print(f'   Server: {account.server}')
else:
    print('❌ Bağlantı hatası:', mt5.last_error())

mt5.shutdown()
"
```

### Adım 3: IOFAE Test Modu

```bash
cd /home/berat/Desktop/Berat/prop_trade/iofae_bot
python main.py --test
```

Bu komut:
- MT5'e bağlanır
- Hesap bilgilerini gösterir
- Güncel market verisini çeker
- Top 5 execution zone'u listeler
- Trade açmadan çıkar

### Adım 4: Geçmiş Veri ile Backtest

```bash
# Son 1 ay
python backtester.py --start 2025-12-01 --end 2025-12-31 --balance 100000

# Son 3 ay
python backtester.py --start 2025-10-01 --end 2025-12-31 --balance 100000

# Son 1 yıl
python backtester.py --start 2025-01-01 --end 2025-12-31 --balance 100000
```

### Adım 5: Paper Trading (Demo)

```bash
# Demo hesapta canlı trade
python main.py
```

⚠️ **ÖNEMLİ**: İlk testler DEMO hesapta yapılmalı!

## Canlı Trading Başlatma

### Güvenli Başlangıç Protokolü:

1. **Hafta 1-2**: Test modu, sinyal izleme (trade yok)
2. **Hafta 3-4**: Demo hesapta canlı trade
3. **Ay 2**: Küçük lot ile gerçek hesap (0.01 lot)
4. **Ay 3+**: Normal lot sizing

### Çalıştırma:

```bash
# Terminal'de çalıştır
python main.py

# Arka planda çalıştır (Linux)
nohup python main.py > iofae.log 2>&1 &

# Systemd servisi olarak (Linux)
sudo systemctl start iofae
```

## Sorun Giderme

### MT5 Bağlanamıyor
```
Hata: initialization failed
```
Çözüm:
1. MT5 terminal'inin açık olduğundan emin ol
2. Login/password doğru mu kontrol et
3. Sunucu adını kontrol et (demo vs live)

### Symbol Bulunamıyor
```
Hata: Symbol EURUSD not found
```
Çözüm:
1. MT5'te Market Watch'a EURUSD ekle
2. Broker'ın symbol adını kontrol et (EURUSD.a gibi)

### Permission Hatası
```
Hata: Trade is disabled
```
Çözüm:
1. MT5 → Tools → Options → Expert Advisors
2. "Allow automated trading" seçeneğini aktifle

## Telegram Bildirimleri (Opsiyonel)

### Bot Oluşturma:
1. Telegram'da @BotFather'a git
2. /newbot komutu
3. Bot adı ver
4. Token'ı al

### Chat ID Bulma:
1. @userinfobot'a mesaj at
2. Chat ID'ni al

### config.yaml:
```yaml
telegram:
  enabled: true
  bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
  chat_id: "987654321"
```

## Önerilen Workflow

```
┌─────────────────┐
│  1. MT5 Kur     │
└────────┬────────┘
         ↓
┌─────────────────┐
│  2. Demo Hesap  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  3. Config Yap  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  4. Test Çalıştır│
└────────┬────────┘
         ↓
┌─────────────────┐
│  5. Backtest    │
└────────┬────────┘
         ↓
┌─────────────────┐
│  6. Demo Trade  │  ← 2-4 hafta
└────────┬────────┘
         ↓
┌─────────────────┐
│  7. Live Trade  │  ← Dikkatli!
└─────────────────┘
```

## Destek

Sorun yaşarsan:
1. Log dosyalarını kontrol et: `logs/iofae.log`
2. MT5 Expert tab'ını kontrol et
3. config.yaml'ı tekrar kontrol et
