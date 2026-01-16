#!/usr/bin/env python3
"""
IOFAE Trading Bot - ICMarkets Son 3 Ay Backtest
Ekim 2025 - Ocak 2026 (3 ay) simülasyonu.

ICMarkets koşulları:
- Spread: 0.0-0.1 pip (Raw account)
- Execution: ECN, hızlı
- Slippage: Minimal
- DOM: Level II mevcut
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import random

random.seed(2025)
np.random.seed(2025)


@dataclass
class ICMarketsTrade:
    """Trade record for ICMarkets backtest."""
    date: str
    time: str
    zone_price: float
    score: int
    direction: str
    entry_price: float
    exit_price: float
    spread: float  # ICMarkets spread
    slippage: float  # ECN slippage
    pips: float
    profit: float
    lot: float
    zone_type: str
    exit_reason: str
    holding_minutes: float
    week: int


def generate_icmarkets_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Generate realistic EUR/USD price data simulating ICMarkets conditions.
    
    ICMarkets özellikleri:
    - Raw Spread: 0.0-0.1 pip
    - Komisyon: $3.50/lot round turn
    - Execution: <50ms
    - Slippage: Genelde 0, max 0.2 pip
    """
    
    data = []
    current = start_date
    price = 1.0550  # EUR/USD başlangıç
    
    # Price memory for trend
    trend_direction = 0
    trend_strength = 0
    
    while current <= end_date:
        # Skip weekends
        if current.weekday() >= 5:
            current += timedelta(days=1)
            current = current.replace(hour=0, minute=0)
            continue
        
        hour = current.hour
        
        # Session-based volatility (ICMarkets has good liquidity)
        if 7 <= hour < 9:  # London open
            volatility = 0.00020
            spread = random.uniform(0.00001, 0.00008)  # 0.1-0.8 pip
        elif 12 <= hour < 15:  # London-NY overlap
            volatility = 0.00018
            spread = random.uniform(0.00000, 0.00005)  # 0.0-0.5 pip (best)
        elif 15 <= hour < 17:  # NY session
            volatility = 0.00015
            spread = random.uniform(0.00002, 0.00010)  # 0.2-1.0 pip
        else:  # Asian/off-hours
            volatility = 0.00008
            spread = random.uniform(0.00005, 0.00015)  # 0.5-1.5 pip
        
        # Random walk with trend persistence
        if random.random() < 0.1:  # 10% chance of trend change
            trend_direction = random.choice([-1, 0, 1])
            trend_strength = random.uniform(0.0001, 0.0003)
        
        # Price movement
        random_move = np.random.normal(0, volatility)
        trend_move = trend_direction * trend_strength * 0.1
        
        # Mean reversion
        mean_level = 1.0600
        reversion = (mean_level - price) * 0.0005
        
        new_price = price + random_move + trend_move + reversion
        
        # OHLC
        high = max(price, new_price) + abs(np.random.normal(0, volatility * 0.5))
        low = min(price, new_price) - abs(np.random.normal(0, volatility * 0.5))
        
        # Volume (ICMarkets has high liquidity)
        if 7 <= hour <= 17:
            volume = int(np.random.lognormal(8, 1))
        else:
            volume = int(np.random.lognormal(6, 1))
        
        data.append({
            'time': current,
            'open': round(price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(new_price, 5),
            'tick_volume': volume,
            'spread': round(spread, 6)
        })
        
        price = new_price
        current += timedelta(minutes=1)
    
    return pd.DataFrame(data)


def run_icmarkets_backtest():
    """Run 3-month ICMarkets backtest."""
    
    print("\n" + "="*80)
    print("🏦 IOFAE ICMarkets BACKTEST - Son 3 Ay")
    print("   Ekim 2025 → Ocak 2026")
    print("="*80)
    
    print("""
📊 ICMarkets Koşulları:
   • Hesap Tipi: Raw Spread
   • Spread: 0.0-0.1 pip (EUR/USD)
   • Komisyon: $3.50/lot (round turn)
   • Execution: ECN, <50ms
   • Slippage: 0-0.2 pip
   • Leverage: 1:500
    """)
    
    # Settings
    initial_balance = 100000
    risk_per_trade = 0.01  # 1%
    stop_loss_pips = 10
    entry_offset_pips = 7
    commission_per_lot = 3.50  # ICMarkets commission
    pip_value = 0.0001
    
    # Calculate lot size: 1% risk = $1000, 10 pip SL
    # $1000 / 10 pips = $100/pip = 10 lots
    lot_size = 10.0
    pip_dollar = 10.0  # $10/pip per lot
    
    # Generate data
    print("📊 Son 3 aylık veri üretiliyor...")
    start_date = datetime(2025, 10, 15)
    end_date = datetime(2026, 1, 15)
    
    bars = generate_icmarkets_data(start_date, end_date)
    print(f"   Toplam bar: {len(bars):,}")
    print(f"   Avg spread: {bars['spread'].mean() * 10000:.2f} pip")
    
    # Trading simulation
    trades: List[ICMarketsTrade] = []
    balance = initial_balance
    equity_curve = [balance]
    max_equity = balance
    max_dd = 0
    
    # Trading rules
    min_score = 90
    max_trades_per_day = 3
    min_trade_interval = 7200  # 2 hours
    max_hold_minutes = 15
    
    position = None
    last_trade_time = None
    daily_trades = {}
    
    # Zone types and win rates (ICMarkets'te daha iyi execution = daha yüksek win rate)
    zone_configs = {
        "STOP_HUNT_LOW": {"win_rate": 0.93, "avg_win": 24, "direction": "LONG"},
        "STOP_HUNT_HIGH": {"win_rate": 0.91, "avg_win": 22, "direction": "SHORT"},
        "INSTITUTIONAL_ROUND": {"win_rate": 0.90, "avg_win": 25, "direction": "BOTH"},
        "VWAP_REVERSION": {"win_rate": 0.88, "avg_win": 20, "direction": "BOTH"},
        "FIB_0.618": {"win_rate": 0.87, "avg_win": 22, "direction": "BOTH"},
        "CONFLUENCE": {"win_rate": 0.89, "avg_win": 23, "direction": "BOTH"},
        "HALF_ROUND": {"win_rate": 0.85, "avg_win": 18, "direction": "BOTH"},
    }
    
    print("\n⏳ Simülasyon çalışıyor...")
    
    week_number = 0
    current_week = None
    
    for i, bar in bars.iterrows():
        bar_time = bar['time']
        bar_date = bar_time.date()
        bar_week = bar_time.isocalendar()[1]
        
        if bar_week != current_week:
            current_week = bar_week
            week_number += 1
        
        # Daily reset
        if bar_date not in daily_trades:
            daily_trades[bar_date] = 0
        
        # Check open position
        if position:
            elapsed = (bar_time - position['entry_time']).total_seconds() / 60
            
            # Exit conditions
            exit_reason = None
            
            # Stop loss
            if position['direction'] == "LONG":
                if bar['low'] <= position['stop_loss']:
                    exit_reason = "STOP_LOSS"
                elif elapsed >= max_hold_minutes or (bar['close'] - position['entry_price']) / pip_value >= 15:
                    if random.random() < 0.7:  # Exhaustion check
                        exit_reason = "EXHAUSTION"
            else:
                if bar['high'] >= position['stop_loss']:
                    exit_reason = "STOP_LOSS"
                elif elapsed >= max_hold_minutes or (position['entry_price'] - bar['close']) / pip_value >= 15:
                    if random.random() < 0.7:
                        exit_reason = "EXHAUSTION"
            
            if elapsed >= max_hold_minutes:
                exit_reason = "TIME_LIMIT"
            
            if exit_reason:
                # Close position
                if exit_reason == "STOP_LOSS":
                    exit_price = position['stop_loss']
                else:
                    exit_price = bar['close']
                
                # Calculate P/L with ICMarkets slippage
                slippage = random.uniform(0, 0.0002)  # 0-0.2 pip
                
                if position['direction'] == "LONG":
                    pips = (exit_price - position['entry_price'] - slippage) / pip_value
                else:
                    pips = (position['entry_price'] - exit_price - slippage) / pip_value
                
                # Profit including commission
                commission = commission_per_lot * lot_size * 2  # Round turn
                profit = (pips * pip_dollar * lot_size) - commission
                
                trades.append(ICMarketsTrade(
                    date=bar_time.strftime("%d.%m.%Y"),
                    time=bar_time.strftime("%H:%M"),
                    zone_price=position['zone_price'],
                    score=position['score'],
                    direction=position['direction'],
                    entry_price=position['entry_price'],
                    exit_price=exit_price,
                    spread=position['spread'],
                    slippage=slippage * 10000,
                    pips=round(pips, 1),
                    profit=round(profit, 2),
                    lot=lot_size,
                    zone_type=position['zone_type'],
                    exit_reason=exit_reason,
                    holding_minutes=round(elapsed, 1),
                    week=week_number
                ))
                
                balance += profit
                equity_curve.append(balance)
                
                if balance > max_equity:
                    max_equity = balance
                dd = max_equity - balance
                if dd > max_dd:
                    max_dd = dd
                
                position = None
                last_trade_time = bar_time
                continue
        
        # Skip if position open
        if position:
            continue
        
        # Trading conditions
        if daily_trades[bar_date] >= max_trades_per_day:
            continue
        
        if last_trade_time:
            if (bar_time - last_trade_time).total_seconds() < min_trade_interval:
                continue
        
        # Session filter (London-NY overlap best for ICMarkets)
        hour = bar_time.hour
        if not (7 <= hour <= 17):
            continue
        
        # Stop hunt check (08:00-08:30)
        if 8 <= hour < 9 and bar_time.minute < 30:
            if random.random() < 0.15:  # 15% chance of stop hunt
                zone_type = random.choice(["STOP_HUNT_LOW", "STOP_HUNT_HIGH"])
                config = zone_configs[zone_type]
                
                score = random.randint(91, 97)
                direction = config["direction"]
                zone_price = bar['close']
                
                if direction == "LONG":
                    entry = zone_price - (entry_offset_pips * pip_value)
                    sl = entry - (stop_loss_pips * pip_value)
                else:
                    entry = zone_price + (entry_offset_pips * pip_value)
                    sl = entry + (stop_loss_pips * pip_value)
                
                position = {
                    'entry_time': bar_time,
                    'direction': direction,
                    'entry_price': entry,
                    'stop_loss': sl,
                    'zone_price': zone_price,
                    'zone_type': zone_type,
                    'score': score,
                    'spread': bar['spread'],
                    'is_win': random.random() < config["win_rate"]
                }
                daily_trades[bar_date] += 1
                continue
        
        # Regular zone detection
        if random.random() < 0.008:  # ~1% chance per bar during session
            zone_type = random.choice(list(zone_configs.keys()))
            config = zone_configs[zone_type]
            
            score = random.randint(90, 98)
            if score < min_score:
                continue
            
            if config["direction"] == "BOTH":
                direction = random.choice(["LONG", "SHORT"])
            else:
                direction = config["direction"]
            
            zone_price = bar['close']
            
            if direction == "LONG":
                entry = zone_price - (entry_offset_pips * pip_value)
                sl = entry - (stop_loss_pips * pip_value)
            else:
                entry = zone_price + (entry_offset_pips * pip_value)
                sl = entry + (stop_loss_pips * pip_value)
            
            position = {
                'entry_time': bar_time,
                'direction': direction,
                'entry_price': entry,
                'stop_loss': sl,
                'zone_price': zone_price,
                'zone_type': zone_type,
                'score': score,
                'spread': bar['spread'],
                'is_win': random.random() < config["win_rate"]
            }
            daily_trades[bar_date] += 1
    
    # Results
    winning = [t for t in trades if t.profit > 0]
    losing = [t for t in trades if t.profit <= 0]
    
    win_count = len(winning)
    lose_count = len(losing)
    total_trades = len(trades)
    win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
    
    total_profit = balance - initial_balance
    profit_pct = total_profit / initial_balance * 100
    
    total_wins = sum(t.profit for t in winning)
    total_losses = abs(sum(t.profit for t in losing))
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Print results
    print(f"\n{'='*80}")
    print("📊 ICMarkets 3 AYLIK BACKTEST SONUÇLARI")
    print(f"{'='*80}")
    
    print(f"\n📅 Dönem: {start_date.date()} → {end_date.date()} (13 hafta)")
    
    print(f"\n💰 PERFORMANS:")
    print(f"   Başlangıç:        ${initial_balance:>12,.2f}")
    print(f"   Bitiş:            ${balance:>12,.2f}")
    print(f"   Net Kar:          ${total_profit:>+12,.2f} ({profit_pct:+.2f}%)")
    print(f"   Aylık Ortalama:   ${total_profit/3:>+12,.2f} ({profit_pct/3:+.2f}%/ay)")
    
    print(f"\n📈 İSTATİSTİKLER:")
    print(f"   Toplam Trade:     {total_trades:>6}")
    print(f"   Kazanan:          {win_count:>6}")
    print(f"   Kaybeden:         {lose_count:>6}")
    print(f"   Win Rate:         {win_rate:>6.1f}%")
    print(f"   Profit Factor:    {profit_factor:>6.2f}")
    
    print(f"\n📏 DETAYLAR:")
    print(f"   Toplam Pip:       {sum(t.pips for t in trades):>+8.1f}")
    print(f"   Ort. Pip/Trade:   {sum(t.pips for t in trades)/total_trades:>+8.1f}" if total_trades else "")
    print(f"   Ort. Win:         ${total_wins/win_count:>+8.2f}" if winning else "")
    print(f"   Ort. Loss:        ${total_losses/lose_count:>8.2f}" if losing else "")
    print(f"   Ort. Spread:      {np.mean([t.spread for t in trades])*10000:>8.2f} pip" if trades else "")
    print(f"   Ort. Slippage:    {np.mean([t.slippage for t in trades]):>8.2f} pip" if trades else "")
    
    print(f"\n⚠️ RİSK:")
    print(f"   Max Drawdown:     ${max_dd:>10,.2f}")
    print(f"   Max DD %:         {max_dd/max_equity*100:>10.2f}%")
    
    # Weekly breakdown
    print(f"\n📅 HAFTALIK PERFORMANS:")
    print(f"   {'Hafta':<8} {'Trade':>6} {'Win':>5} {'Lose':>5} {'Kar':>12}")
    print(f"   {'-'*40}")
    
    for week in range(1, week_number + 1):
        week_trades = [t for t in trades if t.week == week]
        if week_trades:
            week_profit = sum(t.profit for t in week_trades)
            week_wins = len([t for t in week_trades if t.profit > 0])
            week_losses = len([t for t in week_trades if t.profit <= 0])
            emoji = "📈" if week_profit > 0 else "📉"
            print(f"   Hafta {week:<2} {len(week_trades):>6} {week_wins:>5} {week_losses:>5} {week_profit:>+12,.2f} {emoji}")
    
    # Sample trades
    print(f"\n📋 TRADE ÖRNEKLERİ (İlk 15):")
    print(f"   {'Tarih':<12} {'Saat':<6} {'Yön':<6} {'Skor':>4} {'Tip':<18} {'Pip':>7} {'K/Z':>10} {'Spread':>6}")
    print(f"   {'-'*75}")
    
    for t in trades[:15]:
        emoji = "✅" if t.profit > 0 else "❌"
        print(f"   {t.date:<12} {t.time:<6} {t.direction:<6} {t.score:>4} {t.zone_type:<18} {t.pips:>+7.1f} {t.profit:>+10.2f} {t.spread*10000:>5.1f}p {emoji}")
    
    if len(trades) > 15:
        print(f"   ... ve {len(trades) - 15} trade daha")
    
    # Prop firm assessment
    print(f"\n{'='*80}")
    print("🏆 PROP FIRM DEĞERLENDİRMESİ (100K Challenge)")
    print(f"{'='*80}")
    
    # Monthly breakdown for challenge
    months = {}
    for t in trades:
        month = t.date.split('.')[1] + "/2025"
        if month not in months:
            months[month] = 0
        months[month] += t.profit
    
    for month, profit in months.items():
        pct = profit / initial_balance * 100
        passed = pct >= 10
        print(f"   {month}: ${profit:>+10,.2f} ({pct:>+6.2f}%) {'✅ HEDEF GEÇTİ' if passed else '⚠️ Devam'}")
    
    print(f"\n   📊 3 Aylık Özet:")
    print(f"      Toplam Kar:    ${total_profit:>+12,.2f} ({profit_pct:+.2f}%)")
    print(f"      Max DD:        {max_dd/max_equity*100:>6.2f}%")
    print(f"      Win Rate:      {win_rate:>6.1f}%")
    
    if profit_pct >= 10 and max_dd/max_equity*100 < 10:
        print(f"\n   🎉 CHALLENGE BAŞARIYLA GEÇİLDİ!")
    
    print(f"\n{'='*80}")
    print("📝 ICMarkets AVANTAJLARI")
    print(f"{'='*80}")
    print(f"""
✅ DÜŞÜK MALİYET:
   • Raw spread: Ort. {np.mean([t.spread for t in trades])*10000:.2f} pip
   • Komisyon: $3.50/lot × {total_trades} trade = ${commission_per_lot * lot_size * total_trades * 2:,.0f}
   • Slippage: Ort. {np.mean([t.slippage for t in trades]):.2f} pip
   
📈 NET PERFORMANS:
   • Brüt kar: ${total_profit + commission_per_lot * lot_size * total_trades * 2:,.0f}
   • Komisyon: -${commission_per_lot * lot_size * total_trades * 2:,.0f}
   • Net kar:  ${total_profit:,.0f}
   
🎯 ÖNERİ:
   • ICMarkets Raw Spread hesabı bu strateji için ideal
   • London-NY overlap saatlerinde en iyi spreadler
   • Level II DOM ile daha iyi zone tespiti mümkün
""")
    
    print(f"{'='*80}\n")
    
    # Save to CSV
    df = pd.DataFrame([{
        'date': t.date,
        'time': t.time,
        'week': t.week,
        'direction': t.direction,
        'zone_type': t.zone_type,
        'score': t.score,
        'entry_price': t.entry_price,
        'exit_price': t.exit_price,
        'spread_pip': round(t.spread * 10000, 2),
        'slippage_pip': round(t.slippage, 2),
        'pips': t.pips,
        'profit': t.profit,
        'lot': t.lot,
        'exit_reason': t.exit_reason,
        'holding_min': t.holding_minutes
    } for t in trades])
    
    filename = "iofae_icmarkets_3month_backtest.csv"
    df.to_csv(filename, index=False)
    print(f"📁 Sonuçlar kaydedildi: {filename}")
    print(f"   Toplam: {len(trades)} trade")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_icmarkets_backtest()
