"""
IOFAE Trading Bot - Position Manager with Advanced Exhaustion Detection
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List
import numpy as np

from signal_generator import TradeSignal
from data_collector import DataCollector
from utils.logger import get_logger

logger = get_logger()


@dataclass
class Position:
    """Active position information."""
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    profit: float
    pips: float
    entry_time: datetime
    magic: int
    zone_type: str = ""
    score: float = 0


class PositionManager:
    """
    Advanced position manager with institutional exhaustion detection.
    
    Exhaustion Detection:
    1. Volume spike sona erdi (tick volume %30 düştü)
    2. Bid-Ask spread genişledi (%50+)
    3. Fiyat durdu (5 tick'te 2 pip altı hareket)
    
    Çıkış anında pozisyonu kapat - reversal riskini elimine et.
    """
    
    def __init__(self, config: Dict, data_collector: DataCollector):
        self.config = config
        self.collector = data_collector
        
        trading = config.get('trading', {})
        self.symbol = trading.get('symbol', 'EURUSD')
        self.magic_number = trading.get('magic_number', 123456)
        self.deviation = trading.get('deviation', 10)
        self.max_hold_minutes = trading.get('max_hold_time_minutes', 15)
        
        exhaustion = config.get('exhaustion', {})
        self.volume_drop_threshold = exhaustion.get('volume_drop_threshold', 0.70)
        self.spread_widen_threshold = exhaustion.get('spread_widen_threshold', 1.50)
        self.price_stall_pips = exhaustion.get('price_stall_pips', 2)
        self.ema_period = exhaustion.get('ema_period', 50)
        
        self.pip_value = 0.0001
        self._position_entry_times: Dict[int, datetime] = {}
        self._position_meta: Dict[int, Dict] = {}  # Store zone_type, score etc
        
        # Volume/spread history for EMA
        self._volume_history = []
        self._spread_history = []
    
    def set_pip_value(self, pip_value: float):
        self.pip_value = pip_value
    
    def execute_signal(self, signal: TradeSignal, lot_size: float) -> Optional[int]:
        """Execute trade signal, returns ticket if successful."""
        
        # Use trigger price from signal (7 pips before zone)
        if signal.direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.symbol).ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(self.symbol).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": signal.stop_loss,
            "tp": 0.0,  # Dynamic exit via exhaustion
            "deviation": self.deviation,
            "magic": self.magic_number,
            "comment": f"IOFAE_{signal.zone.zone_type[:10]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else "Unknown error"
            logger.error(f"Order failed: {result.retcode if result else 'None'} - {error}")
            return None
        
        ticket = result.order
        self._position_entry_times[ticket] = datetime.now()
        self._position_meta[ticket] = {
            'zone_type': signal.zone.zone_type,
            'score': signal.zone.score,
            'confidence': signal.confidence
        }
        
        logger.trade_open(self.symbol, signal.direction, lot_size, price, signal.stop_loss)
        
        return ticket
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions for this bot."""
        positions = mt5.positions_get(symbol=self.symbol)
        
        if positions is None:
            return []
        
        result = []
        for pos in positions:
            if pos.magic != self.magic_number:
                continue
            
            direction = "LONG" if pos.type == mt5.POSITION_TYPE_BUY else "SHORT"
            current = mt5.symbol_info_tick(self.symbol)
            current_price = current.bid if direction == "LONG" else current.ask
            
            if direction == "LONG":
                pips = (current_price - pos.price_open) / self.pip_value
            else:
                pips = (pos.price_open - current_price) / self.pip_value
            
            entry_time = self._position_entry_times.get(
                pos.ticket, 
                datetime.fromtimestamp(pos.time)
            )
            
            meta = self._position_meta.get(pos.ticket, {})
            
            result.append(Position(
                ticket=pos.ticket,
                symbol=pos.symbol,
                direction=direction,
                volume=pos.volume,
                entry_price=pos.price_open,
                current_price=current_price,
                stop_loss=pos.sl,
                take_profit=pos.tp,
                profit=pos.profit,
                pips=pips,
                entry_time=entry_time,
                magic=pos.magic,
                zone_type=meta.get('zone_type', ''),
                score=meta.get('score', 0)
            ))
        
        return result
    
    def detect_exhaustion(self, position: Position) -> bool:
        """
        Kurumsal emir tükendi mi?
        
        3 ana indikatör:
        1. Volume düşüşü (%30+)
        2. Spread genişlemesi (%50+)
        3. Fiyat durağanlığı (5 tick'te < 2 pip)
        """
        
        # Update history for EMA
        current_volume = self._get_current_volume()
        current_spread = self._get_current_spread()
        
        self._volume_history.append(current_volume)
        self._spread_history.append(current_spread)
        
        # Keep only last 100 values
        self._volume_history = self._volume_history[-100:]
        self._spread_history = self._spread_history[-100:]
        
        # 1. Volume Drop Check
        volume_exhausted = self._check_volume_drop()
        
        # 2. Spread Widening Check  
        spread_exhausted = self._check_spread_widening()
        
        # 3. Price Stall Check
        price_stalled = self._check_price_stall()
        
        # Any exhaustion signal triggers exit
        if volume_exhausted:
            logger.info(f"📉 Exhaustion: Volume dropped significantly")
            return True
        
        if spread_exhausted:
            logger.info(f"📉 Exhaustion: Spread widened significantly")
            return True
        
        if price_stalled:
            logger.info(f"📉 Exhaustion: Price stalled")
            return True
        
        return False
    
    def _get_current_volume(self) -> float:
        """Get tick volume from last 10 seconds."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(seconds=10)
            
            ticks = mt5.copy_ticks_range(
                self.symbol, 
                start_time, 
                end_time, 
                mt5.COPY_TICKS_ALL
            )
            
            if ticks is None or len(ticks) == 0:
                return 0
            
            return sum(t['volume'] for t in ticks)
            
        except:
            return self.collector.get_volume_ema(10) if self.collector else 0
    
    def _get_current_spread(self) -> float:
        """Get current spread."""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick:
                return tick.ask - tick.bid
            return 0
        except:
            return 0
    
    def _check_volume_drop(self) -> bool:
        """Check if volume dropped more than threshold."""
        if len(self._volume_history) < 20:
            return False
        
        # Recent vs average
        recent = np.mean(self._volume_history[-5:])
        average = np.mean(self._volume_history[-50:]) if len(self._volume_history) >= 50 else np.mean(self._volume_history)
        
        if average > 0 and recent < average * self.volume_drop_threshold:
            return True
        
        return False
    
    def _check_spread_widening(self) -> bool:
        """Check if spread widened more than threshold."""
        if len(self._spread_history) < 20:
            return False
        
        current = self._spread_history[-1]
        average = np.mean(self._spread_history[-50:]) if len(self._spread_history) >= 50 else np.mean(self._spread_history)
        
        if average > 0 and current > average * self.spread_widen_threshold:
            return True
        
        return False
    
    def _check_price_stall(self) -> bool:
        """Check if price has stalled (< 2 pip movement in 5 ticks)."""
        try:
            recent_ticks = self.collector.get_recent_ticks(5) if self.collector else []
            
            if len(recent_ticks) < 5:
                return False
            
            prices = [t.bid for t in recent_ticks]
            price_range = max(prices) - min(prices)
            stall_threshold = self.price_stall_pips * self.pip_value
            
            if price_range < stall_threshold:
                return True
            
            return False
            
        except:
            return False
    
    def check_time_limit(self, position: Position) -> bool:
        """Check if position exceeded max hold time."""
        elapsed = datetime.now() - position.entry_time
        max_time = timedelta(minutes=self.max_hold_minutes)
        
        if elapsed >= max_time:
            logger.info(f"⏰ Time limit: {elapsed.total_seconds()/60:.1f} min")
            return True
        
        return False
    
    def close_position(self, position: Position, reason: str = "MANUAL") -> bool:
        """Close a position."""
        
        if position.direction == "LONG":
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(self.symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": position.ticket,
            "price": price,
            "deviation": self.deviation,
            "magic": self.magic_number,
            "comment": f"CLOSE_{reason[:8]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Close failed: {result.retcode if result else 'None'}")
            return False
        
        # Cleanup tracking
        self._position_entry_times.pop(position.ticket, None)
        self._position_meta.pop(position.ticket, None)
        
        logger.trade_close(self.symbol, position.profit, position.pips, reason)
        
        return True
    
    def monitor_position(self, position: Position) -> Optional[str]:
        """
        Monitor position and return close reason if should close.
        
        Returns:
            None: Keep open
            str: Close reason (EXHAUSTION, TIME_LIMIT, STOP_LOSS, etc.)
        """
        
        # 1. Check exhaustion (primary exit)
        if self.detect_exhaustion(position):
            return "EXHAUSTION"
        
        # 2. Check time limit
        if self.check_time_limit(position):
            return "TIME_LIMIT"
        
        # 3. Check if position still exists (stopped out)
        current_positions = self.get_open_positions()
        if not any(p.ticket == position.ticket for p in current_positions):
            return "STOP_LOSS"
        
        # 4. Optional: Trailing stop if in profit
        if position.pips >= 15:  # 15 pips profit
            self._trail_stop(position)
        
        return None
    
    def _trail_stop(self, position: Position):
        """Move stop to breakeven or trail."""
        new_sl = None
        
        if position.direction == "LONG":
            # Trail to entry + 5 pips
            breakeven = position.entry_price + (5 * self.pip_value)
            if position.stop_loss < breakeven:
                new_sl = breakeven
        else:
            breakeven = position.entry_price - (5 * self.pip_value)
            if position.stop_loss > breakeven:
                new_sl = breakeven
        
        if new_sl:
            self.modify_stop_loss(position, new_sl)
    
    def modify_stop_loss(self, position: Position, new_sl: float) -> bool:
        """Modify position stop loss."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.take_profit,
        }
        
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return False
        
        logger.info(f"🎯 SL moved to {new_sl:.5f}")
        return True
