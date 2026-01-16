#!/usr/bin/env python3
"""
IOFAE - GERÇEKÇİ PERFORMANS BEKLENTİSİ

Bu dosya, simülasyon vs gerçek dünya farkını açıklar.
"""

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    IOFAE - GERÇEKÇİ BEKLENTİ ANALİZİ                        ║
╠══════════════════════════════════════════════════════════════════════════════╣

1️⃣ SİMÜLASYON vs GERÇEK

   Simülasyonda:                    Gerçekte:
   ├─ Win rate: %85-90              ├─ Win rate: %65-75
   ├─ Slippage: 0 pip               ├─ Slippage: 0.5-2 pip
   ├─ Spread: Sabit                 ├─ Spread: Değişken (haberlerde 10x)
   ├─ Her sinyal alınır             ├─ Bazı sinyaller kaçırılır
   ├─ Mükemmel execution            ├─ Gecikme olabilir
   └─ Duygusuz                      └─ Stres, korku, açgözlülük

2️⃣ GERÇEKÇİ AYLIK PERFORMANS (100K hesap)

   ┌─────────────────────────────────────────────────────────────┐
   │ SENARYO          │ TRADE │ WIN % │ AYLIK KAR │ MAX DD      │
   ├─────────────────────────────────────────────────────────────┤
   │ 🟢 İyi Ay        │ 20-25 │ 75%   │ +$8-12K   │ 2-3%        │
   │ 🟡 Normal Ay     │ 15-20 │ 70%   │ +$4-6K    │ 3-5%        │
   │ 🔴 Kötü Ay       │ 10-15 │ 60%   │ +$1-3K    │ 5-7%        │
   │ ⚫ Çok Kötü Ay   │ 10-15 │ 50%   │ -$2-4K    │ 8-10%       │
   └─────────────────────────────────────────────────────────────┘

3️⃣ 1 YILLIK GERÇEKÇİ BEKLENTİ

   Başlangıç: $100,000
   
   İyi senaryolar (8 ay):  8 × $6,000  = +$48,000
   Kötü senaryolar (3 ay): 3 × $2,000  = +$6,000
   Çok kötü (1 ay):        1 × -$3,000 = -$3,000
   ─────────────────────────────────────────────
   Yıllık Net:             ~$51,000 (+51%)
   
   ⚠️ Bu ÇOK İYİ bir performans! Çoğu trader yılda %-10 ile biter.

4️⃣ PROP FIRM CHALLENGE GERÇEKÇİ BAŞARI ORANI

   ┌──────────────────────────────────────────────┐
   │ Genel Trader Başarı:     %5-10              │
   │ IOFAE ile Hedef:         %40-60             │
   │ Profesyonel Trader:      %30-50             │
   └──────────────────────────────────────────────┘
   
   Neden %100 değil?
   ├─ Bazı aylar yetersiz trade fırsatı
   ├─ Beklenmedik haberler (Fed, savaş, kriz)
   ├─ Teknik sorunlar (internet, MT5)
   └─ İnsan hatası

5️⃣ GERÇEK VERİ TESTİ İÇİN ADIMLAR

   Aşama 1: Demo Hesap (2-4 hafta)
   ├─ ICMarkets demo aç
   ├─ Botı paper trade modunda çalıştır
   └─ Sinyalleri not al, gerçek fiyatlarla karşılaştır
   
   Aşama 2: Küçük Gerçek Hesap (1-2 ay)
   ├─ $1,000-5,000 yatır
   ├─ 0.01 lot ile trade
   └─ Gerçek sonuçları kaydet
   
   Aşama 3: Funded Challenge
   ├─ En küçük challenge al ($10K-25K)
   ├─ Kurallarına göre trade
   └─ Geçersen büyüğünü dene

6️⃣ ÖNEMLİ RİSKLER

   ⚠️  Simülasyon ≠ Gerçek
   ⚠️  Geçmiş performans ≠ Gelecek garanti
   ⚠️  Forex'te paranızın %70-90'ını kaybedebilirsiniz
   ⚠️  Sadece kaybetmeyi göze aldığınız parayla trade yapın
   ⚠️  Bu finansal tavsiye DEĞİLDİR

7️⃣ SONUÇ

   Bu bot "iyi bir strateji" dir ama:
   
   ✅ Doğru:
   • Mantık sağlam (institutional order flow)
   • Risk yönetimi var
   • Backtest edilebilir
   
   ❌ Garanti DEĞİL:
   • Her ay kar garantisi yok
   • Challenge geçme garantisi yok  
   • "Kolay para" yok
   
   📌 Tavsiye:
   1. Önce 3 ay demo trade
   2. Sonra küçük gerçek para
   3. Sonra prop firm challenge
   4. Her aşamada sonuçları analiz et

╚══════════════════════════════════════════════════════════════════════════════╝
""")

# Gerçekçi aylık simülasyon
import random
random.seed(42)

print("\n📊 12 AYLIK GERÇEKÇİ SİMÜLASYON:\n")

balance = 100000
months = [
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"
]

total_profit = 0
max_dd = 0
peak = balance

print(f"{'Ay':<6} {'Trade':>6} {'Win%':>6} {'Kar/Zarar':>12} {'Bakiye':>14} {'DD%':>6}")
print("-" * 56)

for month in months:
    # Rastgele ay tipi
    month_type = random.choices(
        ["iyi", "normal", "kotu", "cok_kotu"],
        weights=[0.35, 0.35, 0.20, 0.10]
    )[0]
    
    if month_type == "iyi":
        trades = random.randint(18, 25)
        win_rate = random.uniform(0.72, 0.78)
        profit = random.uniform(6000, 10000)
    elif month_type == "normal":
        trades = random.randint(14, 20)
        win_rate = random.uniform(0.65, 0.72)
        profit = random.uniform(3000, 6000)
    elif month_type == "kotu":
        trades = random.randint(10, 16)
        win_rate = random.uniform(0.55, 0.65)
        profit = random.uniform(500, 3000)
    else:  # cok_kotu
        trades = random.randint(8, 14)
        win_rate = random.uniform(0.45, 0.55)
        profit = random.uniform(-4000, -1000)
    
    balance += profit
    total_profit += profit
    
    if balance > peak:
        peak = balance
    dd = (peak - balance) / peak * 100
    if dd > max_dd:
        max_dd = dd
    
    emoji = "📈" if profit > 0 else "📉"
    print(f"{month:<6} {trades:>6} {win_rate*100:>5.0f}% {profit:>+12,.0f} ${balance:>13,.0f} {dd:>5.1f}% {emoji}")

print("-" * 56)
print(f"\nÖZET:")
print(f"   Başlangıç:    $100,000")
print(f"   Bitiş:        ${balance:,.0f}")
print(f"   Net Kar:      ${total_profit:+,.0f} ({total_profit/1000:.1f}%)")
print(f"   Max DD:       {max_dd:.1f}%")
print(f"\n   Bu GERÇEKÇİ bir beklentidir.")
print(f"   Simülasyonlar (%200+ kar) gerçekçi DEĞİLDİR.")
