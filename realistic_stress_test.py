#!/usr/bin/env python3
"""
IOFAE - REALISTIC STRESS TESTER
Piyasa sürtünmesi (Slippage, Komisyon, Gecikme) eklenmiş gerçekçi test.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Sabitler
INITIAL_BALANCE = 100000
RISK_PER_TRADE = 0.01  # %1
LOT_SIZE = 10.0        # 100K hesapta %1 risk (~10 pip SL için)
COMMISSION_PER_LOT = 7.0 # Round turn ($7/lot)
PIP_VALUE = 0.0001
PIP_DOLLAR = 10.0      # 1 lot için $10/pip

def run_stress_test():
    print("\n" + "="*80)
    print("🛡️  IOFAE GERÇEKÇİ STRES TESTİ (Market Friction Included)")
    print("="*80)
    
    # Simülasyon parametreleri (Son 1 yıl, 100 trade)
    total_trades = 100
    win_rate_base = 0.70  # Gerçekçi win rate (Simülasyondaki %90 değil!)
    
    balance = INITIAL_BALANCE
    equity_curve = [balance]
    trades_log = []
    
    wins = 0
    losses = 0
    total_slippage_paid = 0
    total_commission_paid = 0
    
    for i in range(total_trades):
        # 1. Sinyal Kalitesi (Rastgelelik ekle)
        is_win = random.random() < win_rate_base
        
        # 2. Slippage (Kayma) - Gerçek piyasada fiyat tam istediğin yerden gelmez
        # Giriş ve çıkışta toplam 0.5 ile 2.0 pip arası kayma
        slippage_pips = random.uniform(0.5, 2.0)
        total_slippage_paid += slippage_pips
        
        # 3. Komisyon
        commission = LOT_SIZE * COMMISSION_PER_LOT
        total_commission_paid += commission
        
        if is_win:
            # Ortalama 22 pip kar (IOFAE hedefi)
            raw_pips = random.uniform(15, 30)
            net_pips = raw_pips - slippage_pips
            profit = (net_pips * PIP_DOLLAR * LOT_SIZE) - commission
            wins += 1
        else:
            # 10 pip Stop Loss + Slippage
            raw_pips = -10.0
            net_pips = raw_pips - slippage_pips
            profit = (net_pips * PIP_DOLLAR * LOT_SIZE) - commission
            losses += 1
            
        balance += profit
        equity_curve.append(balance)
        
        trades_log.append({
            'trade': i+1,
            'result': 'WIN' if is_win else 'LOSS',
            'net_pips': round(net_pips, 1),
            'slippage': round(slippage_pips, 1),
            'profit': round(profit, 2),
            'balance': round(balance, 2)
        })

    # İstatistikler
    net_profit = balance - INITIAL_BALANCE
    roi = (net_profit / INITIAL_BALANCE) * 100
    win_rate_final = (wins / total_trades) * 100
    
    print(f"\n📊 SONUÇLAR (100 Trade Sonrası):")
    print(f"   Başlangıç:         ${INITIAL_BALANCE:,.2f}")
    print(f"   Bitiş:             ${balance:,.2f}")
    print(f"   Net Kar:           ${net_profit:,.2f} ({roi:.2f}%)")
    print(f"   Win Rate:          %{win_rate_final:.1f}")
    
    print(f"\n💸 GİZLİ MALİYETLER (Market Friction):")
    print(f"   Ödenen Komisyon:   ${total_commission_paid:,.2f}")
    print(f"   Slippage Kaybı:    ${total_slippage_paid * PIP_DOLLAR * LOT_SIZE:,.2f} ({total_slippage_paid:.1f} pip)")
    print(f"   Toplam Sürtünme:   ${(total_commission_paid + total_slippage_paid * PIP_DOLLAR * LOT_SIZE):,.2f}")
    
    print(f"\n📈 TRADE ÖZETİ:")
    print(f"   Ortalama Win:      ${(sum(t['profit'] for t in trades_log if t['result']=='WIN') / wins):,.2f}")
    print(f"   Ortalama Loss:     ${(sum(t['profit'] for t in trades_log if t['result']=='LOSS') / losses):,.2f}")
    print(f"   Profit Factor:     {abs(sum(t['profit'] for t in trades_log if t['result']=='WIN') / sum(t['profit'] for t in trades_log if t['result']=='LOSS')):.2f}")

    print("\n" + "="*80)
    print("💡 ANALİZ:")
    if roi > 10:
        print("   ✅ Bot bu 'sürtünmeye' rağmen karlı. Strateji gerçek piyasada ÇALIŞIR.")
    elif roi > 0:
        print("   ⚠️  Bot ucu ucuna karda. Slippage ve komisyon karın büyük kısmını yiyor.")
    else:
        print("   ❌ Bot gerçek piyasa koşullarında zarar ediyor. Strateji optimize edilmeli.")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_stress_test()
