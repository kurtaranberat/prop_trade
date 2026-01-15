"""
IOFAE Trading Bot - Data Collector Module
Collects real-time market data from MetaTrader 5.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from collections import deque

from utils.logger import get_logger

logger = get_logger()


@dataclass
class MarketTick:
    """Single market tick data."""
    time: datetime
    bid: float
    ask: float
    spread: float
    last: float
    volume: float
    flags: int = 0


@dataclass
class MarketData:
    """Comprehensive market data snapshot."""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    spread: float
    spread_points: int
    last_price: float
    tick_volume: float
    
    open: float = 0
    high: float = 0
    low: float = 0
    close: float = 0
    volume: float = 0
    vwap: float = 0
    bid_ask_delta: float = 0
    
    dom_bids: List[Tuple[float, float]] = field(default_factory=list)
    dom_asks: List[Tuple[float, float]] = field(default_factory=list)
    
    swing_high: float = 0
    swing_low: float = 0
    fib_levels: Dict[str, float] = field(default_factory=dict)


class DataCollector:
    """Collects and processes market data from MetaTrader 5."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.symbol = config.get('trading', {}).get('symbol', 'EURUSD')
        self.connected = False
        
        self._tick_buffer = deque(maxlen=10000)
        self._volume_buffer = deque(maxlen=100)
        self._spread_buffer = deque(maxlen=100)
        self._delta_buffer = deque(maxlen=50)
        
        self._symbol_info = None
        self._pip_value = 0.0001
    
    def initialize(self) -> bool:
        """Initialize connection to MetaTrader 5."""
        mt5_config = self.config.get('mt5', {})
        
        if not mt5.initialize(
            login=mt5_config.get('login'),
            password=mt5_config.get('password'),
            server=mt5_config.get('server'),
            timeout=mt5_config.get('timeout', 60000),
            path=mt5_config.get('portable_path')
        ):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        if not mt5.symbol_select(self.symbol, True):
            logger.error(f"Symbol {self.symbol} not found")
            return False
        
        self._symbol_info = mt5.symbol_info(self.symbol)
        if self._symbol_info is None:
            logger.error(f"Could not get symbol info")
            return False
        
        self._pip_value = self._symbol_info.point * 10 if self._symbol_info.digits == 5 else self._symbol_info.point
        self.connected = True
        logger.info(f"MT5 connected. Account: {mt5.account_info().login}")
        return True
    
    def shutdown(self):
        mt5.shutdown()
        self.connected = False
    
    def get_account_info(self) -> Dict[str, Any]:
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            'login': info.login, 'balance': info.balance, 'equity': info.equity,
            'margin': info.margin, 'free_margin': info.margin_free, 'leverage': info.leverage,
            'profit': info.profit, 'currency': info.currency
        }
    
    def collect(self) -> Optional[MarketData]:
        if not self.connected:
            return None
        
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return None
            
            spread = tick.ask - tick.bid
            spread_points = int(spread / self._symbol_info.point)
            
            self._tick_buffer.append(MarketTick(
                time=datetime.fromtimestamp(tick.time), bid=tick.bid, ask=tick.ask,
                spread=spread, last=tick.last, volume=tick.volume, flags=tick.flags
            ))
            
            self._volume_buffer.append(tick.volume)
            self._spread_buffer.append(spread)
            
            bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, 1)
            ohlcv = bars[0] if bars is not None and len(bars) > 0 else None
            
            vwap = self._calculate_vwap()
            bid_ask_delta = self._calculate_delta()
            self._delta_buffer.append(bid_ask_delta)
            swing_high, swing_low = self._get_swing_levels()
            fib_levels = self._calculate_fibonacci(swing_high, swing_low)
            dom_bids, dom_asks = self._get_dom_data()
            
            return MarketData(
                symbol=self.symbol, timestamp=datetime.now(), bid=tick.bid, ask=tick.ask,
                spread=spread, spread_points=spread_points, last_price=tick.last if tick.last > 0 else tick.bid,
                tick_volume=tick.volume, open=ohlcv['open'] if ohlcv else 0, high=ohlcv['high'] if ohlcv else 0,
                low=ohlcv['low'] if ohlcv else 0, close=ohlcv['close'] if ohlcv else tick.bid,
                volume=ohlcv['tick_volume'] if ohlcv else 0, vwap=vwap, bid_ask_delta=bid_ask_delta,
                dom_bids=dom_bids, dom_asks=dom_asks, swing_high=swing_high, swing_low=swing_low, fib_levels=fib_levels
            )
        except Exception as e:
            logger.error(f"Error collecting data: {e}")
            return None
    
    def _calculate_vwap(self) -> float:
        try:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            bars = mt5.copy_rates_range(self.symbol, mt5.TIMEFRAME_M1, today_start, now)
            if bars is None or len(bars) == 0:
                return 0
            df = pd.DataFrame(bars)
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            df['pv'] = df['typical_price'] * df['tick_volume']
            return df['pv'].sum() / df['tick_volume'].sum() if df['tick_volume'].sum() > 0 else 0
        except:
            return 0
    
    def _calculate_delta(self) -> float:
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(seconds=10)
            ticks = mt5.copy_ticks_range(self.symbol, start_time, end_time, mt5.COPY_TICKS_ALL)
            if ticks is None or len(ticks) == 0:
                return 0
            df = pd.DataFrame(ticks)
            bid_vol = sum(row['volume'] for _, row in df.iterrows() if row['flags'] & 4)
            ask_vol = sum(row['volume'] for _, row in df.iterrows() if row['flags'] & 2)
            return bid_vol - ask_vol
        except:
            return 0
    
    def _get_swing_levels(self) -> Tuple[float, float]:
        try:
            bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 0, 5)
            if bars is None or len(bars) == 0:
                return 0, 0
            df = pd.DataFrame(bars)
            return df['high'].max(), df['low'].min()
        except:
            return 0, 0
    
    def _calculate_fibonacci(self, swing_high: float, swing_low: float) -> Dict[str, float]:
        if swing_high == 0 or swing_low == 0:
            return {}
        diff = swing_high - swing_low
        return {
            '0.236': swing_high - diff * 0.236, '0.382': swing_high - diff * 0.382,
            '0.5': swing_high - diff * 0.5, '0.618': swing_high - diff * 0.618,
            '0.786': swing_high - diff * 0.786
        }
    
    def _get_dom_data(self) -> Tuple[List, List]:
        try:
            book = mt5.market_book_get(self.symbol)
            if book is None:
                return [], []
            bids, asks = [], []
            for entry in book[:20]:
                if entry.type == mt5.BOOK_TYPE_SELL:
                    asks.append((entry.price, entry.volume))
                else:
                    bids.append((entry.price, entry.volume))
            return bids, asks
        except:
            return [], []
    
    def get_pip_value(self) -> float:
        return self._pip_value
    
    def get_point(self) -> float:
        return self._symbol_info.point if self._symbol_info else 0.00001
    
    def get_volume_ema(self, period: int = 50) -> float:
        if len(self._volume_buffer) < 2:
            return 0
        return np.mean(list(self._volume_buffer)[-period:])
    
    def get_spread_ema(self, period: int = 50) -> float:
        if len(self._spread_buffer) < 2:
            return 0
        return np.mean(list(self._spread_buffer)[-period:])
    
    def get_recent_ticks(self, count: int = 5) -> List[MarketTick]:
        return list(self._tick_buffer)[-count:]
    
    def get_historical_bars(self, timeframe=None, count: int = 100):
        if timeframe is None:
            timeframe = mt5.TIMEFRAME_M1
        bars = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if bars is None:
            return None
        df = pd.DataFrame(bars)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
