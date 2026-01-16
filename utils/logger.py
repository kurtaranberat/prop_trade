"""
IOFAE Trading Bot - Logger Utility
Handles all logging operations with file rotation and console output.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class IOFAELogger:
    """Custom logger for IOFAE Trading Bot."""
    
    _instance: Optional['IOFAELogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        name: str = "IOFAE",
        level: str = "INFO",
        file_path: str = "logs/iofae.log",
        max_size_mb: int = 10,
        backup_count: int = 5,
        console_output: bool = True
    ):
        if self._logger is not None:
            return
            
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper()))
        self._logger.handlers = []
        
        # Create logs directory if not exists
        log_dir = os.path.dirname(file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, level.upper()))
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)
    
    @property
    def logger(self) -> logging.Logger:
        return self._logger
    
    def debug(self, message: str):
        self._logger.debug(message)
    
    def info(self, message: str):
        self._logger.info(message)
    
    def warning(self, message: str):
        self._logger.warning(message)
    
    def error(self, message: str):
        self._logger.error(message)
    
    def critical(self, message: str):
        self._logger.critical(message)
    
    def trade_signal(self, symbol: str, direction: str, score: float, price: float):
        """Log a trade signal with special formatting."""
        msg = f"📊 SIGNAL | {symbol} | {direction} | Score: {score:.1f} | Price: {price:.5f}"
        self._logger.info(msg)
    
    def trade_open(self, symbol: str, direction: str, lot: float, entry: float, sl: float, zone_type: str = "", score: float = 0):
        """Log a trade opened with detailed context."""
        msg = f"🟢 OPEN | {symbol} | {direction} | Lot: {lot} | Entry: {entry:.5f} | SL: {sl:.5f} | Zone: {zone_type} | Score: {score:.1f}"
        self._logger.info(msg)
    
    def trade_close(self, symbol: str, profit: float, pips: float, reason: str, duration_mins: float = 0):
        """Log a trade closed with detailed metrics."""
        emoji = "✅" if profit > 0 else "❌"
        msg = f"{emoji} CLOSE | {symbol} | P/L: ${profit:.2f} | Pips: {pips:.1f} | Duration: {duration_mins:.1f}m | Reason: {reason}"
        self._logger.info(msg)
    
    def risk_alert(self, message: str):
        """Log a risk management alert."""
        msg = f"⚠️ RISK ALERT | {message}"
        self._logger.warning(msg)


def get_logger() -> IOFAELogger:
    """Get the singleton logger instance."""
    return IOFAELogger()


# Module level logger for convenience
logger = IOFAELogger()
