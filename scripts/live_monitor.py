#!/usr/bin/env python3
"""
IOFAE - LIVE MARKET MONITOR
Canlı piyasada kurumsal emir bölgelerini ve skorları anlık izleme aracı.
İşlem açmaz, sadece analiz eder.
"""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "core"))

import MetaTrader5 as mt5
import time
import os
import yaml
from datetime import datetime
from core.score_calculator import ScoreCalculator
from core.data_collector import DataCollector

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def run_monitor():
    # 1. Config Yükle
    config_path = root_dir / 'config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    symbol = config['trading']['symbol']
    
    # 2. MT5 Bağlantısı
    if not mt5.initialize():
        print("❌ MT5 Başlatılamadı! Lütfen MT5 Terminalinin açık olduğundan emin olun.")
        return

    print(f"✅ MT5 Bağlandı. {symbol} için canlı akış başlıyor...")
    
    # Modülleri Başlat
    collector = DataCollector(config)
    scorer = ScoreCalculator(config)
    
    try:
        while True:
            clear_screen()
            now = datetime.now().strftime("%H:%M:%S")
            
            # Canlı Veri Topla
            market_data = collector.get_market_data()
            if not market_data:
                print("⏳ Veri bekleniyor...")
                time.sleep(1)
                continue
            
            # Isı Haritası Tara (±15 pip)
            print(f"🚀 IOFAE LIVE MONITOR | {now} | {symbol}: {market_data.bid}")
            print("="*60)
            print(f"{'FİYAT':<12} {'SKOR':<8} {'BÖLGE TİPİ':<20} {'DURUM'}")
            print("-" * 60)
            
            # Mevcut fiyatın etrafındaki seviyeleri tara
            pip = 0.0001
            current_price = market_data.bid
            
            zones = []
            for i in range(-15, 16):
                level = round(current_price + (i * pip), 5)
                zone = scorer.calculate_score(level, market_data)
                if zone.score > 70: # Sadece önemli bölgeleri göster
                    zones.append(zone)
            
            # Skorlara göre sırala
            zones.sort(key=lambda x: x.score, reverse=True)
            
            for z in zones[:8]: # En iyi 8 bölgeyi göster
                status = "🔥 KRİTİK" if z.score >= 90 else "⏳ İzlemede"
                color = "\033[91m" if z.score >= 90 else "\033[93m" if z.score >= 80 else "\033[0m"
                reset = "\033[0m"
                
                print(f"{z.price:<12.5f} {color}{z.score:<8.1f}{reset} {z.zone_type:<20} {status}")

            print("-" * 60)
            print(f"📊 Market Delta: {market_data.bid_ask_delta:>8.0f}")
            print(f"📉 VWAP Mesafe:  {abs(market_data.bid - market_data.vwap)/pip:>8.1f} pip")
            print(f"📢 Son Sinyal:   {scorer.get_best_zone(market_data).zone_type if scorer.get_best_zone(market_data) else 'YOK'}")
            print("="*60)
            print("Çıkmak için Ctrl+C basın...")
            
            time.sleep(2) # 2 saniyede bir güncelle

    except KeyboardInterrupt:
        print("\n🛑 İzleme durduruldu.")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    run_monitor()
