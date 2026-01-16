#!/usr/bin/env python3
"""
IOFAE - SAFETY MANAGER
Prop Firm kurallarını korumak için geliştirilmiş güvenlik modülü.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import yaml
import logging

class SafetyManager:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.max_daily_loss_pct = self.config['risk'].get('max_daily_loss', 0.04)
        self.news_blackout_minutes = 30
        self.logger = logging.getLogger("SafetyManager")

    def check_daily_drawdown(self):
        """Günlük kayıp sınırına ulaşıldı mı kontrol eder."""
        account_info = mt5.account_info()
        if account_info is None:
            return False

        initial_balance = account_info.balance
        current_equity = account_info.equity
        
        # Günlük başlangıç bakiyesini (veya dünkü kapanışı) baz alarak hesapla
        # Not: Gerçek bir sistemde bu değer veritabanından çekilmelidir.
        daily_loss = (initial_balance - current_equity) / initial_balance
        
        if daily_loss >= self.max_daily_loss_pct:
            self.logger.warning(f"🚨 KRİTİK: Günlük kayıp sınırı (%{daily_loss*100:.2f}) aşıldı! Trading durduruluyor.")
            return False
        return True

    def is_news_time(self):
        """
        Önemli haber saatlerini kontrol eder. 
        Not: Bu fonksiyon manuel bir liste veya bir API üzerinden beslenebilir.
        """
        # Örnek: Bugünün önemli haber saatleri (UTC)
        # Gerçek uygulamada bir API'den çekilmelidir.
        high_impact_news = [
            "15:30", # US CPI / NFP
            "21:00", # FOMC
        ]
        
        now_utc = datetime.utcnow()
        current_time = now_utc.strftime("%H:%M")
        
        for news_time in high_impact_news:
            news_dt = datetime.strptime(news_time, "%H:%M")
            news_dt = now_utc.replace(hour=news_dt.hour, minute=news_dt.minute)
            
            # Haberden 30 dk önce ve 30 dk sonra işlem yapma
            if abs((now_utc - news_dt).total_seconds()) < (self.news_blackout_minutes * 60):
                self.logger.info(f"⏳ Haber Koruması: {news_time} haberi nedeniyle trading askıda.")
                return True
        return False

    def can_trade(self):
        """Tüm güvenlik kontrollerini yapar."""
        if not self.check_daily_drawdown():
            return False
        
        if self.is_news_time():
            return False
            
        return True
