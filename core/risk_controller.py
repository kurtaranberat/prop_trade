"""
IOFAE Trading Bot - Risk Controller Module
Manages risk limits and position sizing for prop firm compliance.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple
import MetaTrader5 as mt5

from database.dom_logger import DOMLogger
from utils.logger import get_logger
from utils.notifier import TelegramNotifier

logger = get_logger()


class RiskController:
    """
    Enforces risk management rules for prop firm compliance.
    
    Rules:
    - Max 1% risk per trade
    - Max 5% daily loss
    - Max 10% total drawdown
    - Max 3 trades per day
    - Min 3 hours between trades
    """
    
    def __init__(
        self, 
        config: Dict, 
        db: Optional[DOMLogger] = None,
        notifier: Optional[TelegramNotifier] = None
    ):
        self.config = config
        self.db = db
        self.notifier = notifier
        
        risk = config.get('risk', {})
        self.risk_per_trade = risk.get('risk_per_trade', 0.01)
        self.max_daily_loss = risk.get('max_daily_loss', 0.05)
        self.max_total_dd = risk.get('max_total_drawdown', 0.10)
        self.max_trades_day = risk.get('max_trades_per_day', 3)
        self.min_trade_interval = risk.get('min_trade_interval_seconds', 10800)
        
        prop = config.get('prop_firm', {})
        self.profit_target = prop.get('profit_target', 0.10)
        self.challenge_days = prop.get('challenge_days', 30)
        
        self.pip_value = 0.0001
        self.pip_dollar_value = 10.0  # Per standard lot for EUR/USD
        
        self._starting_balance = 0
        self._highest_balance = 0
        self._today_starting = 0
        self._today_loss = 0
        self._today_trades = 0
        self._last_trade_time: Optional[datetime] = None
        self._bot_stopped = False
    
    def initialize(self, balance: float):
        """Initialize risk controller with account balance."""
        self._starting_balance = balance
        self._highest_balance = balance
        self._today_starting = balance
        self._today_loss = 0
        self._today_trades = 0
        
        # Get today's trades from DB
        if self.db:
            stats = self.db.get_today_stats()
            self._today_trades = stats.get('total_trades', 0)
            self._today_loss = abs(min(0, stats.get('total_profit', 0)))
            
            last_trade_time = self.db.get_last_trade_time()
            if last_trade_time and last_trade_time.date() == date.today():
                self._last_trade_time = last_trade_time
        
        logger.info(f"Risk controller initialized. Balance: ${balance:.2f}")
    
    def update_balance(self, current_balance: float):
        """Update balance tracking."""
        # Track highest balance
        if current_balance > self._highest_balance:
            self._highest_balance = current_balance
        
        # Track daily loss
        if current_balance < self._today_starting:
            self._today_loss = self._today_starting - current_balance
    
    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed based on all risk rules."""
        
        if self._bot_stopped:
            return False, "Bot is stopped due to risk limits"
        
        # Check daily loss limit
        if not self._check_daily_loss():
            msg = f"Daily loss limit reached: ${self._today_loss:.2f}"
            logger.risk_alert(msg)
            if self.notifier:
                self.notifier.notify_risk_alert("DAILY_LOSS", msg)
            return False, msg
        
        # Check total drawdown
        if not self._check_total_drawdown():
            msg = f"Total drawdown limit reached"
            logger.risk_alert(msg)
            if self.notifier:
                self.notifier.notify_risk_alert("MAX_DRAWDOWN", msg)
            self._bot_stopped = True
            return False, msg
        
        # Check daily trade count
        if not self._check_trade_count():
            msg = f"Max trades per day reached: {self._today_trades}"
            logger.info(msg)
            return False, msg
        
        # Check trade interval
        if not self._check_trade_interval():
            remaining = self._get_interval_remaining()
            msg = f"Trade interval not met. Wait {remaining} minutes"
            logger.info(msg)
            return False, msg
        
        return True, "OK"
    
    def _check_daily_loss(self) -> bool:
        """Check if within daily loss limit."""
        max_loss = self._today_starting * self.max_daily_loss
        return self._today_loss < max_loss
    
    def _check_total_drawdown(self) -> bool:
        """Check if within total drawdown limit."""
        # Calculate drawdown from starting balance
        current = self._today_starting - self._today_loss
        dd_pct = (self._starting_balance - current) / self._starting_balance
        return dd_pct < self.max_total_dd
    
    def _check_trade_count(self) -> bool:
        """Check if under max trades per day."""
        return self._today_trades < self.max_trades_day
    
    def _check_trade_interval(self) -> bool:
        """Check if enough time passed since last trade."""
        if self._last_trade_time is None:
            return True
        
        elapsed = (datetime.now() - self._last_trade_time).total_seconds()
        return elapsed >= self.min_trade_interval
    
    def _get_interval_remaining(self) -> int:
        """Get minutes remaining until next trade allowed."""
        if self._last_trade_time is None:
            return 0
        
        elapsed = (datetime.now() - self._last_trade_time).total_seconds()
        remaining = self.min_trade_interval - elapsed
        return max(0, int(remaining / 60))
    
    def calculate_lot_size(self, balance: float, stop_loss_pips: float) -> float:
        """
        Calculate position size based on risk percentage.
        
        Formula: Lot = (Balance × Risk%) / (SL_pips × Pip_value)
        """
        risk_amount = balance * self.risk_per_trade
        lot_size = risk_amount / (stop_loss_pips * self.pip_dollar_value)
        
        # Round to 2 decimal places
        lot_size = round(lot_size, 2)
        
        # Apply min/max limits
        lot_size = max(0.01, min(lot_size, 100.0))
        
        logger.info(f"Calculated lot: {lot_size} (Risk: ${risk_amount:.2f}, SL: {stop_loss_pips} pips)")
        
        return lot_size
    
    def record_trade(self, profit: float = 0):
        """Record a trade for daily tracking."""
        self._today_trades += 1
        self._last_trade_time = datetime.now()
        
        if profit < 0:
            self._today_loss += abs(profit)
        
        logger.info(f"Trade recorded. Today: {self._today_trades} trades, Loss: ${self._today_loss:.2f}")
    
    def get_daily_stats(self) -> Dict:
        """Get current daily statistics."""
        current_balance = self._today_starting - self._today_loss
        daily_dd_pct = (self._today_loss / self._today_starting * 100) if self._today_starting > 0 else 0
        
        return {
            'starting_balance': self._today_starting,
            'current_balance': current_balance,
            'daily_loss': self._today_loss,
            'daily_dd_pct': daily_dd_pct,
            'trades_today': self._today_trades,
            'trades_remaining': self.max_trades_day - self._today_trades,
            'can_trade': self.can_trade()[0]
        }
    
    def get_challenge_progress(self) -> Dict:
        """Get prop firm challenge progress."""
        current = self._today_starting - self._today_loss
        profit_pct = (current - self._starting_balance) / self._starting_balance
        dd_pct = (self._highest_balance - current) / self._highest_balance if self._highest_balance > 0 else 0
        
        return {
            'starting_balance': self._starting_balance,
            'current_balance': current,
            'profit_pct': profit_pct * 100,
            'target_pct': self.profit_target * 100,
            'max_dd_pct': dd_pct * 100,
            'allowed_dd_pct': self.max_total_dd * 100,
            'on_track': profit_pct >= 0 and dd_pct < self.max_total_dd
        }
    
    def reset_daily(self, new_balance: float):
        """Reset daily tracking (call at start of each day)."""
        self._today_starting = new_balance
        self._today_loss = 0
        self._today_trades = 0
        
        logger.info(f"Daily reset. New starting balance: ${new_balance:.2f}")
    
    def stop_bot(self, reason: str = "Risk limit"):
        """Stop the bot due to risk limits."""
        self._bot_stopped = True
        logger.critical(f"Bot stopped: {reason}")
        
        if self.notifier:
            self.notifier.notify_bot_stopped(reason)
    
    def is_stopped(self) -> bool:
        """Check if bot is stopped."""
        return self._bot_stopped
