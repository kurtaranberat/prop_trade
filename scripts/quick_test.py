#!/usr/bin/env python3
"""
IOFAE Quick Test - MT5 bağlantı ve veri testi.
Canlı trading yapmadan önce bu scripti çalıştır.
"""

import sys
import os

def test_mt5_import():
    """Test MT5 module import."""
    print("\n" + "="*60)
    print("🔍 IOFAE MT5 BAĞLANTI TESTİ")
    print("="*60)
    
    print("\n1️⃣ MetaTrader5 modülü kontrol ediliyor...")
    try:
        import MetaTrader5 as mt5
        print("   ✅ MetaTrader5 modülü yüklü")
        return mt5
    except ImportError:
        print("   ❌ MetaTrader5 modülü bulunamadı!")
        print("\n   Çözüm:")
        print("   pip install MetaTrader5")
        print("\n   ⚠️ NOT: MT5 sadece Windows'ta çalışır.")
        print("   Linux kullanıyorsan Wine veya Windows VPS gerekli.")
        return None

def test_mt5_initialize(mt5):
    """Test MT5 initialization."""
    print("\n2️⃣ MT5 başlatılıyor...")
    
    if mt5.initialize():
        print("   ✅ MT5 başlatıldı")
        
        terminal = mt5.terminal_info()
        if terminal:
            print(f"   📂 Path: {terminal.path}")
            print(f"   📊 Build: {terminal.build}")
            print(f"   🔌 Connected: {terminal.connected}")
        
        return True
    else:
        error = mt5.last_error()
        print(f"   ❌ MT5 başlatılamadı: {error}")
        print("\n   Olası nedenler:")
        print("   1. MT5 terminal yüklü değil")
        print("   2. MT5 terminal kapalı")
        print("   3. Windows değil (Linux/Mac)")
        return False

def test_account_connection(mt5, login, password, server):
    """Test account connection."""
    print("\n3️⃣ Hesap bağlantısı test ediliyor...")
    
    if not mt5.initialize(login=login, password=password, server=server):
        error = mt5.last_error()
        print(f"   ❌ Hesap bağlantısı başarısız: {error}")
        return False
    
    account = mt5.account_info()
    if account:
        print("   ✅ Hesap bağlandı")
        print(f"   👤 Login: {account.login}")
        print(f"   💰 Balance: ${account.balance:,.2f}")
        print(f"   📊 Equity: ${account.equity:,.2f}")
        print(f"   🏦 Server: {account.server}")
        print(f"   💱 Currency: {account.currency}")
        print(f"   📈 Leverage: 1:{account.leverage}")
        return True
    else:
        print("   ❌ Hesap bilgisi alınamadı")
        return False

def test_symbol_data(mt5, symbol="EURUSD"):
    """Test symbol data."""
    print(f"\n4️⃣ {symbol} verisi test ediliyor...")
    
    if not mt5.symbol_select(symbol, True):
        print(f"   ❌ {symbol} seçilemedi")
        print(f"   💡 Alternatif: {symbol}.a veya {symbol}m deneyin")
        return False
    
    info = mt5.symbol_info(symbol)
    if info:
        print(f"   ✅ {symbol} bilgisi alındı")
        print(f"   📊 Spread: {info.spread} points")
        print(f"   📈 Bid: {info.bid}")
        print(f"   📉 Ask: {info.ask}")
        print(f"   🔢 Digits: {info.digits}")
    
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        print(f"\n   📡 Canlı Tick:")
        print(f"      Bid: {tick.bid}")
        print(f"      Ask: {tick.ask}")
        print(f"      Time: {tick.time}")
    
    return True

def test_historical_data(mt5, symbol="EURUSD"):
    """Test historical data."""
    print(f"\n5️⃣ Geçmiş veri testi...")
    
    import pandas as pd
    from datetime import datetime, timedelta
    
    end = datetime.now()
    start = end - timedelta(days=30)
    
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, start, end)
    
    if rates is not None and len(rates) > 0:
        print(f"   ✅ Son 30 günlük veri alındı: {len(rates)} bar")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        print(f"\n   📊 Son 5 gün:")
        print(f"   {'Tarih':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10}")
        print(f"   " + "-"*54)
        for _, row in df.tail(5).iterrows():
            print(f"   {row['time'].strftime('%Y-%m-%d'):<12} {row['open']:>10.5f} {row['high']:>10.5f} {row['low']:>10.5f} {row['close']:>10.5f}")
        
        return True
    else:
        print(f"   ❌ Geçmiş veri alınamadı")
        return False

def test_iofae_import():
    """Test IOFAE module imports."""
    print("\n6️⃣ IOFAE modülleri kontrol ediliyor...")
    
    modules_ok = True
    
    try:
        import yaml
        print("   ✅ PyYAML")
    except:
        print("   ❌ PyYAML - pip install pyyaml")
        modules_ok = False
    
    try:
        import pandas
        print("   ✅ Pandas")
    except:
        print("   ❌ Pandas - pip install pandas")
        modules_ok = False
    
    try:
        import numpy
        print("   ✅ NumPy")
    except:
        print("   ❌ NumPy - pip install numpy")
        modules_ok = False
    
    try:
        import sqlalchemy
        print("   ✅ SQLAlchemy")
    except:
        print("   ❌ SQLAlchemy - pip install sqlalchemy")
        modules_ok = False
    
    try:
        import aiohttp
        print("   ✅ aiohttp")
    except:
        print("   ❌ aiohttp - pip install aiohttp")
        modules_ok = False
    
    return modules_ok

def run_full_test():
    """Run complete test suite."""
    
    from pathlib import Path
    root_dir = Path(__file__).parent.parent
    os.chdir(str(root_dir))
    
    # Load config
    config = {}
    try:
        import yaml
        config_path = root_dir / 'config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except:
        print("⚠️ config.yaml okunamadı, varsayılan değerler kullanılacak")
    
    mt5_config = config.get('mt5', {})
    login = mt5_config.get('login', 0)
    password = mt5_config.get('password', '')
    server = mt5_config.get('server', '')
    symbol = config.get('trading', {}).get('symbol', 'EURUSD')
    
    # Test imports
    test_iofae_import()
    
    # Test MT5
    mt5 = test_mt5_import()
    if mt5 is None:
        print("\n" + "="*60)
        print("❌ MT5 KURULUMU GEREKLİ")
        print("="*60)
        print("""
MT5 kurulumu için:

1. Windows'ta:
   - https://www.metatrader5.com/en/download adresinden indir
   - Kur ve broker hesabıyla giriş yap

2. Linux'ta:
   - Wine kullan veya Windows VPS al
   - pip install MetaTrader5 (sadece Windows'ta çalışır)

3. VPS Önerileri:
   - Contabo (ucuz Windows VPS)
   - DigitalOcean
   - AWS Lightsail
        """)
        return False
    
    # Test initialization
    if not test_mt5_initialize(mt5):
        mt5.shutdown()
        return False
    
    # Test account (if credentials provided)
    if login and password and server:
        if not test_account_connection(mt5, login, password, server):
            print("\n⚠️ config.yaml'daki MT5 bilgilerini kontrol et")
    else:
        print("\n⚠️ Hesap testi atlandı - config.yaml'da login bilgileri yok")
    
    # Test symbol
    test_symbol_data(mt5, symbol)
    
    # Test historical data
    test_historical_data(mt5, symbol)
    
    # Cleanup
    mt5.shutdown()
    
    print("\n" + "="*60)
    print("✅ TÜM TESTLER TAMAMLANDI")
    print("="*60)
    print("""
Sonraki adımlar:

1. config.yaml'ı broker bilgileriyle güncelle
2. Backtest çalıştır:
   python backtester.py --start 2025-12-01 --end 2025-12-31

3. Demo hesapta test:
   python main.py --test

4. Canlı demo trading:
   python main.py
    """)
    
    return True


if __name__ == "__main__":
    success = run_full_test()
    sys.exit(0 if success else 1)
