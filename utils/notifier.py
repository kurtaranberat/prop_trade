"""
IOFAE Trading Bot - Telegram Notifier
Sends trading notifications to Telegram.
"""

import asyncio
from typing import Optional
from datetime import datetime
import aiohttp
from enum import Enum


class NotificationType(Enum):
    TRADE_OPEN = "trade_open"
    TRADE_CLOSE = "trade_close"
    SIGNAL = "signal"
    ERROR = "error"
    DAILY_SUMMARY = "daily_summary"
    RISK_ALERT = "risk_alert"


class TelegramNotifier:
    """Handles Telegram notifications for the trading bot."""
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        if not self.enabled:
            return True
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Telegram notification error: {e}")
            return False
    
    def send_message_sync(self, text: str, parse_mode: str = "HTML") -> bool:
        """Synchronous wrapper for sending messages."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._send_message(text, parse_mode))
    
    def notify_trade_open(
        self,
        symbol: str,
        direction: str,
        lot: float,
        entry_price: float,
        stop_loss: float,
        score: float
    ) -> bool:
        """Notify about a new trade opened."""
        text = f"""
🟢 <b>TRADE AÇILDI</b>

📊 <b>Sembol:</b> {symbol}
📈 <b>Yön:</b> {direction}
💰 <b>Lot:</b> {lot}
🎯 <b>Giriş:</b> {entry_price:.5f}
🛑 <b>Stop Loss:</b> {stop_loss:.5f}
⭐ <b>Skor:</b> {score:.1f}/100

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_trade_close(
        self,
        symbol: str,
        direction: str,
        lot: float,
        entry_price: float,
        exit_price: float,
        profit: float,
        pips: float,
        reason: str
    ) -> bool:
        """Notify about a trade closed."""
        emoji = "✅" if profit > 0 else "❌"
        profit_text = f"+${profit:.2f}" if profit > 0 else f"-${abs(profit):.2f}"
        pips_text = f"+{pips:.1f}" if pips > 0 else f"{pips:.1f}"
        
        text = f"""
{emoji} <b>TRADE KAPANDI</b>

📊 <b>Sembol:</b> {symbol}
📈 <b>Yön:</b> {direction}
💰 <b>Lot:</b> {lot}
🎯 <b>Giriş:</b> {entry_price:.5f}
🏁 <b>Çıkış:</b> {exit_price:.5f}

💵 <b>Kâr/Zarar:</b> {profit_text}
📏 <b>Pip:</b> {pips_text}
📝 <b>Sebep:</b> {reason}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_signal(
        self,
        symbol: str,
        direction: str,
        score: float,
        target_price: float
    ) -> bool:
        """Notify about a trading signal."""
        text = f"""
🔔 <b>YENİ SİNYAL</b>

📊 <b>Sembol:</b> {symbol}
📈 <b>Yön:</b> {direction}
⭐ <b>Skor:</b> {score:.1f}/100
🎯 <b>Hedef Seviye:</b> {target_price:.5f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_daily_summary(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        total_profit: float,
        total_pips: float,
        current_balance: float,
        daily_drawdown: float
    ) -> bool:
        """Send daily trading summary."""
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_emoji = "📈" if total_profit > 0 else "📉"
        
        text = f"""
📊 <b>GÜNLÜK ÖZET - {date}</b>

🔢 <b>Toplam Trade:</b> {total_trades}
✅ <b>Kazanan:</b> {winning_trades}
📊 <b>Win Rate:</b> {win_rate:.1f}%

{profit_emoji} <b>Günlük K/Z:</b> ${total_profit:.2f}
📏 <b>Toplam Pip:</b> {total_pips:.1f}

💰 <b>Bakiye:</b> ${current_balance:.2f}
📉 <b>Günlük DD:</b> {daily_drawdown:.2f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_error(self, error_message: str, module: str = "Unknown") -> bool:
        """Notify about an error."""
        text = f"""
🚨 <b>HATA</b>

📍 <b>Modül:</b> {module}
❌ <b>Hata:</b> {error_message}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_risk_alert(self, alert_type: str, message: str) -> bool:
        """Notify about a risk management alert."""
        text = f"""
⚠️ <b>RİSK UYARISI</b>

🔴 <b>Tip:</b> {alert_type}
📝 <b>Mesaj:</b> {message}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)
    
    def notify_bot_started(self, symbol: str, balance: float) -> bool:
        """Notify that the bot has started."""
        text = f"""
🚀 <b>IOFAE BOT BAŞLATILDI</b>

📊 <b>Sembol:</b> {symbol}
💰 <b>Bakiye:</b> ${balance:.2f}
⏰ <b>Başlangıç:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Sistemler aktif, trade bekleniyor...
"""
        return self.send_message_sync(text)
    
    def notify_bot_stopped(self, reason: str = "Manual stop") -> bool:
        """Notify that the bot has stopped."""
        text = f"""
🛑 <b>IOFAE BOT DURDURULDU</b>

📝 <b>Sebep:</b> {reason}
⏰ <b>Bitiş:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return self.send_message_sync(text)


# Factory function
def create_notifier(config: dict) -> Optional[TelegramNotifier]:
    """Create a notifier from config."""
    telegram_config = config.get('telegram', {})
    
    if not telegram_config.get('enabled', False):
        return None
    
    return TelegramNotifier(
        bot_token=telegram_config.get('bot_token', ''),
        chat_id=telegram_config.get('chat_id', ''),
        enabled=True
    )
