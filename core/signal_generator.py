"""
IOFAE Trading Bot - Advanced Signal Generator with Correlation Confirmation
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import List, Optional, Dict, Tuple
import MetaTrader5 as mt5

from .data_collector import MarketData
from .score_calculator import ScoreCalculator, ExecutionZone
from database.dom_logger import DOMLogger
from utils.logger import get_logger

logger = get_logger()


@dataclass
class TradeSignal:
    """Trade signal with correlation confirmation."""
    symbol: str
    timestamp: datetime
    direction: str
    zone: ExecutionZone
    entry_price: float
    stop_loss: float
    suggested_lot: float
    confidence: float
    correlation_confirmed: bool
    correlation_details: Dict
    reason: str


class SignalGenerator:
    """
    Advanced signal generator with:
    - Execution zone scanning
    - Multi-instrument correlation (EUR/USD vs DXY)
    - Session filtering
    - Stop hunt pattern detection
    """
    
    def __init__(self, config: Dict, score_calculator: ScoreCalculator, db: Optional[DOMLogger] = None):
        self.config = config
        self.score_calc = score_calculator
        self.db = db
        
        trading = config.get('trading', {})
        self.symbol = trading.get('symbol', 'EURUSD')
        self.scan_range_pips = trading.get('scan_range_pips', 20)
        self.min_score = trading.get('min_score_threshold', 90)
        self.entry_offset_pips = trading.get('entry_offset_pips', 7)
        self.stop_loss_pips = trading.get('stop_loss_pips', 10)
        
        correlation = config.get('correlation', {})
        self.correlation_enabled = correlation.get('enabled', True)
        self.dxy_symbol = correlation.get('dxy_symbol', 'USDX')  # or DX-SEP24 etc
        
        self.pip_value = 0.0001
        self._last_signal_time = None
        
        # Stop hunt detection parameters
        self.stop_hunt_start = time(8, 0)   # 08:00 GMT
        self.stop_hunt_end = time(8, 30)    # 08:30 GMT
    
    def set_pip_value(self, pip_value: float):
        self.pip_value = pip_value
        self.score_calc.set_pip_value(pip_value)
    
    def scan_and_generate(self, market_data: MarketData) -> Optional[TradeSignal]:
        """
        Scan for execution zones and generate signal with correlation confirmation.
        """
        
        # Check blackout periods (major news)
        if self._is_blackout_period():
            return None
        
        # Check if in valid trading session
        if not self._is_active_session():
            return None
        
        # Check for stop hunt pattern (special 08:00-08:30 logic)
        stop_hunt_signal = self._check_stop_hunt_pattern(market_data)
        if stop_hunt_signal:
            return stop_hunt_signal
        
        # Get best execution zone
        best_zone = self.score_calc.get_best_zone(market_data, self.min_score)
        
        if not best_zone:
            return None
        
        # Check distance to zone
        distance = abs(best_zone.price - market_data.bid)
        if distance > self.scan_range_pips * self.pip_value:
            return None
        
        # Correlation confirmation
        correlation_result = self._check_correlation(best_zone.direction, market_data)
        
        # Adjust confidence based on correlation
        adjusted_confidence = best_zone.score
        if correlation_result['confirmed']:
            adjusted_confidence += 5  # Bonus for correlation
        else:
            adjusted_confidence -= 15  # Penalty for mismatch
        
        # Final check - must still be >= 90 after adjustment
        if adjusted_confidence < self.min_score:
            logger.info(f"Signal rejected: Confidence {adjusted_confidence:.1f} after correlation adjustment")
            return None
        
        # Create signal
        signal = TradeSignal(
            symbol=self.symbol,
            timestamp=datetime.now(),
            direction=best_zone.direction,
            zone=best_zone,
            entry_price=best_zone.trigger_price,
            stop_loss=best_zone.stop_loss,
            suggested_lot=0.01,  # Will be calculated by risk controller
            confidence=adjusted_confidence,
            correlation_confirmed=correlation_result['confirmed'],
            correlation_details=correlation_result,
            reason=f"{best_zone.zone_type} | Score: {best_zone.score:.1f} | Correlation: {correlation_result['status']}"
        )
        
        logger.trade_signal(signal.symbol, signal.direction, adjusted_confidence, best_zone.price)
        
        # Save to database
        if self.db:
            self.db.save_execution_zone(
                symbol=self.symbol,
                price_level=best_zone.price,
                score=best_zone.score,
                score_breakdown=best_zone.score_breakdown
            )
        
        return signal
    
    def _check_correlation(self, direction: str, market_data: MarketData) -> Dict:
        """
        Multi-instrument correlation confirmation.
        
        EUR/USD ve DXY arasında negatif korelasyon var:
        - EUR/USD LONG → DXY düşmeli
        - EUR/USD SHORT → DXY yükselmeli
        
        Returns confirmation status and details.
        """
        if not self.correlation_enabled:
            return {'confirmed': True, 'status': 'DISABLED', 'dxy_trend': None}
        
        try:
            # Try to get DXY data
            dxy_available = mt5.symbol_select(self.dxy_symbol, True)
            
            if not dxy_available:
                # Try alternative symbols
                alternatives = ['USDX', 'DXY', 'DX-SEP24', 'DX']
                for alt in alternatives:
                    if mt5.symbol_select(alt, True):
                        self.dxy_symbol = alt
                        dxy_available = True
                        break
            
            if not dxy_available:
                logger.debug("DXY symbol not available, skipping correlation check")
                return {'confirmed': True, 'status': 'UNAVAILABLE', 'dxy_trend': None}
            
            # Get DXY 1-minute bars
            dxy_bars = mt5.copy_rates_from_pos(self.dxy_symbol, mt5.TIMEFRAME_M1, 0, 10)
            
            if dxy_bars is None or len(dxy_bars) < 5:
                return {'confirmed': True, 'status': 'NO_DATA', 'dxy_trend': None}
            
            # Calculate DXY trend
            dxy_open = dxy_bars[0]['open']
            dxy_close = dxy_bars[-1]['close']
            dxy_change = dxy_close - dxy_open
            dxy_change_pct = (dxy_change / dxy_open) * 100
            
            # Determine DXY trend
            if dxy_change > 0.001:
                dxy_trend = "UP"
            elif dxy_change < -0.001:
                dxy_trend = "DOWN"
            else:
                dxy_trend = "FLAT"
            
            # Check correlation
            # EUR/USD LONG signals should correlate with DXY DOWN
            # EUR/USD SHORT signals should correlate with DXY UP
            
            if direction == "LONG":
                if dxy_trend == "DOWN":
                    status = "CONFIRMED"
                    confirmed = True
                elif dxy_trend == "FLAT":
                    status = "NEUTRAL"
                    confirmed = True  # Neutral is acceptable
                else:
                    status = "CONFLICTING"
                    confirmed = False
            
            else:  # SHORT
                if dxy_trend == "UP":
                    status = "CONFIRMED"
                    confirmed = True
                elif dxy_trend == "FLAT":
                    status = "NEUTRAL"
                    confirmed = True
                else:
                    status = "CONFLICTING"
                    confirmed = False
            
            return {
                'confirmed': confirmed,
                'status': status,
                'dxy_trend': dxy_trend,
                'dxy_change': dxy_change,
                'dxy_change_pct': dxy_change_pct
            }
            
        except Exception as e:
            logger.warning(f"Correlation check error: {e}")
            return {'confirmed': True, 'status': 'ERROR', 'dxy_trend': None}
    
    def _check_stop_hunt_pattern(self, market_data: MarketData) -> Optional[TradeSignal]:
        """
        Algorithmic Stop Hunt Pattern Detection.
        
        08:00-08:30 GMT arası, algoritmalar retail stopları tetikler:
        - Fiyat önceki günün high/low'unu 5-10 pip kırar
        - 2-3 dakika içinde geri döner
        - Sen kırılma anında TERSINE girersin
        """
        now = datetime.now()
        current_time = now.time()
        
        # Only check during stop hunt window
        if not (self.stop_hunt_start <= current_time <= self.stop_hunt_end):
            return None
        
        try:
            # Get yesterday's high/low
            daily_bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 1, 1)
            
            if daily_bars is None or len(daily_bars) == 0:
                return None
            
            yesterday_high = daily_bars[0]['high']
            yesterday_low = daily_bars[0]['low']
            
            current_price = market_data.bid
            
            # Check for false breakout above yesterday's high
            if current_price > yesterday_high + (5 * self.pip_value):
                breakout_pips = (current_price - yesterday_high) / self.pip_value
                
                if breakout_pips <= 12:  # 5-12 pip breakout = likely stop hunt
                    logger.info(f"Stop hunt detected above yesterday high! Breakout: {breakout_pips:.1f} pips")
                    
                    # Create SHORT signal (fade the breakout)
                    zone = ExecutionZone(
                        price=yesterday_high,
                        score=92,
                        direction="SHORT",
                        score_breakdown={'stop_hunt': 92},
                        zone_type="STOP_HUNT_HIGH",
                        trigger_price=current_price,
                        stop_loss=current_price + (15 * self.pip_value),
                        confidence_level="HIGH"
                    )
                    
                    return TradeSignal(
                        symbol=self.symbol,
                        timestamp=now,
                        direction="SHORT",
                        zone=zone,
                        entry_price=current_price,
                        stop_loss=current_price + (15 * self.pip_value),
                        suggested_lot=0.01,
                        confidence=92,
                        correlation_confirmed=True,
                        correlation_details={'status': 'STOP_HUNT'},
                        reason=f"STOP_HUNT above {yesterday_high:.5f}"
                    )
            
            # Check for false breakout below yesterday's low
            elif current_price < yesterday_low - (5 * self.pip_value):
                breakout_pips = (yesterday_low - current_price) / self.pip_value
                
                if breakout_pips <= 12:
                    logger.info(f"Stop hunt detected below yesterday low! Breakout: {breakout_pips:.1f} pips")
                    
                    zone = ExecutionZone(
                        price=yesterday_low,
                        score=92,
                        direction="LONG",
                        score_breakdown={'stop_hunt': 92},
                        zone_type="STOP_HUNT_LOW",
                        trigger_price=current_price,
                        stop_loss=current_price - (15 * self.pip_value),
                        confidence_level="HIGH"
                    )
                    
                    return TradeSignal(
                        symbol=self.symbol,
                        timestamp=now,
                        direction="LONG",
                        zone=zone,
                        entry_price=current_price,
                        stop_loss=current_price - (15 * self.pip_value),
                        suggested_lot=0.01,
                        confidence=92,
                        correlation_confirmed=True,
                        correlation_details={'status': 'STOP_HUNT'},
                        reason=f"STOP_HUNT below {yesterday_low:.5f}"
                    )
            
            return None
            
        except Exception as e:
            logger.warning(f"Stop hunt check error: {e}")
            return None
    
    def _is_blackout_period(self) -> bool:
        """Check if in news blackout period."""
        blackouts = self.config.get('blackout_periods', [])
        now = datetime.now().time()
        
        for period in blackouts:
            try:
                start = datetime.strptime(period['start'], '%H:%M').time()
                end = datetime.strptime(period['end'], '%H:%M').time()
                
                if start <= now <= end:
                    logger.debug(f"Blackout: {period.get('description', 'News')}")
                    return True
            except:
                continue
        
        return False
    
    def _is_active_session(self) -> bool:
        """Check if in London-NY overlap (optimal trading session)."""
        sessions = self.config.get('sessions', {})
        
        if not sessions.get('active_sessions_only', True):
            return True
        
        now = datetime.now()
        current_hour = now.hour
        
        # London session: 07:00-16:00 UTC
        # NY session: 12:00-21:00 UTC
        # Overlap: 12:00-16:00 UTC (best time)
        
        london_start = 7
        london_end = 16
        ny_start = 12
        ny_end = 21
        
        # Check if in any active session
        in_london = london_start <= current_hour < london_end
        in_ny = ny_start <= current_hour < ny_end
        
        if in_london or in_ny:
            return True
        
        return False
    
    def get_heatmap(self, market_data: MarketData) -> Dict[float, float]:
        """
        Get execution probability heatmap for ±20 pips.
        Returns dict of {price: score}
        """
        zones = self.score_calc.scan_all_zones(market_data, self.scan_range_pips)
        return {z.price: z.score for z in zones}
    
    def get_top_zones(self, market_data: MarketData, count: int = 5) -> List[ExecutionZone]:
        """Get top N scoring zones."""
        zones = self.score_calc.scan_all_zones(market_data, self.scan_range_pips)
        return zones[:count]
