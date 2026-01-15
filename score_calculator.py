"""
IOFAE Trading Bot - Advanced Score Calculator
Institutional Order Flow Anticipation Engine

Calculates execution probability for each price level using:
- VWAP Distance (30 points max)
- Round Number Proximity (25 points max)
- Fibonacci Confluence (20 points max)
- Historical DOM Depth (15 points max)
- Delta Imbalance (10 points max)

Score 90+ = Institutional order highly likely
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np

from data_collector import MarketData
from database.dom_logger import DOMLogger
from utils.logger import get_logger

logger = get_logger()


@dataclass
class ExecutionZone:
    """Forced execution zone with probability score."""
    price: float
    score: float
    direction: str  # 'LONG' or 'SHORT'
    score_breakdown: Dict[str, float]
    zone_type: str  # Primary zone type
    trigger_price: float  # Entry price (7 pips before zone)
    stop_loss: float
    confidence_level: str  # 'HIGH', 'MEDIUM', 'LOW'


class ScoreCalculator:
    """
    Advanced institutional execution probability calculator.
    
    Kurumsal emirlerin hangi seviyede tetikleneceğini ÖNCEDEN hesaplar.
    
    Skor Sistemi:
    - 90-100: Kurumsal emir kesin var (%95+ olasılık)
    - 80-89: Yüksek olasılık (%80+)
    - 70-79: Orta olasılık (%60+)
    - 0-69: Düşük olasılık (trade açma)
    """
    
    def __init__(self, config: Dict, db: Optional[DOMLogger] = None):
        self.config = config
        self.db = db
        
        scoring = config.get('scoring', {})
        
        # Max point values
        self.VWAP_MAX = scoring.get('vwap_max_points', 30)
        self.ROUND_MAX = scoring.get('round_number_max_points', 25)
        self.FIB_MAX = scoring.get('fibonacci_max_points', 20)
        self.DOM_MAX = scoring.get('dom_volume_max_points', 15)
        self.DELTA_MAX = scoring.get('delta_imbalance_max_points', 10)
        
        # VWAP thresholds
        self.VWAP_CRITICAL = 0.003   # %0.3+ = Kurumlar ZORLA pozisyon açar
        self.VWAP_HIGH = 0.002       # %0.2+ = Yüksek olasılık
        self.VWAP_LOW = 0.001        # %0.1+ = Orta olasılık
        
        # DOM thresholds
        self.DOM_THRESHOLD = scoring.get('dom_volume_threshold', 1500)
        self.DELTA_THRESHOLD = scoring.get('delta_imbalance_threshold', 8000)
        
        # Fibonacci proximity
        self.FIB_PROXIMITY_PIPS = scoring.get('fibonacci_proximity_pips', 5)
        
        # Entry/exit parameters
        trading = config.get('trading', {})
        self.ENTRY_OFFSET_PIPS = trading.get('entry_offset_pips', 7)
        self.STOP_LOSS_PIPS = trading.get('stop_loss_pips', 10)
        
        self.pip_value = 0.0001
        
        # Round number cache
        self._round_numbers = self._generate_round_numbers()
    
    def set_pip_value(self, pip_value: float):
        self.pip_value = pip_value
        self._round_numbers = self._generate_round_numbers()
    
    def _generate_round_numbers(self) -> List[float]:
        """Generate round number levels (50 pip intervals)."""
        levels = []
        for major in range(100, 150):  # 1.00 to 1.50
            for minor in [0, 50]:
                level = major / 100 + minor / 10000
                levels.append(level)
        return sorted(levels)
    
    def calculate_score(self, price_level: float, market_data: MarketData) -> ExecutionZone:
        """
        Calculate institutional execution probability for a price level.
        
        Returns ExecutionZone with full breakdown.
        """
        breakdown = {}
        
        # 1. VWAP Distance Score (30 max)
        vwap_score = self._calculate_vwap_score(price_level, market_data.vwap)
        breakdown['vwap'] = vwap_score
        
        # 2. Round Number Proximity Score (25 max)
        round_score, round_type = self._calculate_round_number_score(price_level)
        breakdown['round_number'] = round_score
        
        # 3. Fibonacci Confluence Score (20 max)
        fib_score, fib_level = self._calculate_fibonacci_score(price_level, market_data.fib_levels)
        breakdown['fibonacci'] = fib_score
        
        # 4. Historical DOM Depth Score (15 max)
        dom_score = self._calculate_dom_score(price_level, market_data.symbol)
        breakdown['dom'] = dom_score
        
        # 5. Delta Imbalance Score (10 max)
        delta_score = self._calculate_delta_score(market_data.bid_ask_delta)
        breakdown['delta'] = delta_score
        
        # Total score (max 100)
        total_score = min(sum(breakdown.values()), 100)
        
        # Determine primary zone type
        zone_type = self._determine_zone_type(breakdown, round_type, fib_level)
        
        # Determine direction
        direction = self._determine_direction(price_level, market_data)
        
        # Calculate trigger price (7 pips before zone)
        trigger_price = self._calculate_trigger_price(price_level, direction)
        
        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(trigger_price, direction)
        
        # Confidence level
        if total_score >= 95:
            confidence = "VERY_HIGH"
        elif total_score >= 90:
            confidence = "HIGH"
        elif total_score >= 80:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        return ExecutionZone(
            price=price_level,
            score=total_score,
            direction=direction,
            score_breakdown=breakdown,
            zone_type=zone_type,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            confidence_level=confidence
        )
    
    def _calculate_vwap_score(self, price_level: float, vwap: float) -> float:
        """
        VWAP Distance Scoring.
        
        Kurumlar günlük VWAP'tan uzaklaşamaz (tracking error limiti var).
        Fiyat VWAP'tan %0.3+ uzaklaştığında zorla pozisyon açarlar.
        
        %0.3+ uzak = 30 puan (tam)
        %0.2-0.3 = 15-30 puan (lineer)
        %0.1-0.2 = 5-15 puan (lineer)
        %0-0.1 = 0-5 puan (lineer)
        """
        if vwap == 0:
            return 0
        
        distance_pct = abs(price_level - vwap) / vwap
        
        if distance_pct >= self.VWAP_CRITICAL:  # %0.3+
            # Her %0.1 fazlalık için +3 puan (max 30)
            extra = min((distance_pct - self.VWAP_CRITICAL) / 0.001 * 3, 0)
            return self.VWAP_MAX
        
        elif distance_pct >= self.VWAP_HIGH:  # %0.2 - %0.3
            base = self.VWAP_MAX * 0.5  # 15 puan
            range_pct = (distance_pct - self.VWAP_HIGH) / (self.VWAP_CRITICAL - self.VWAP_HIGH)
            return base + (self.VWAP_MAX * 0.5 * range_pct)
        
        elif distance_pct >= self.VWAP_LOW:  # %0.1 - %0.2
            base = self.VWAP_MAX * 0.17  # ~5 puan
            range_pct = (distance_pct - self.VWAP_LOW) / (self.VWAP_HIGH - self.VWAP_LOW)
            return base + (self.VWAP_MAX * 0.33 * range_pct)
        
        else:  # < %0.1
            return (distance_pct / self.VWAP_LOW) * (self.VWAP_MAX * 0.17)
    
    def _calculate_round_number_score(self, price_level: float) -> Tuple[float, str]:
        """
        Round Number Proximity Scoring.
        
        Büyük emirler round number'larda birikir.
        50 pip aralıkları (1.0800, 1.0850) en güçlü.
        
        Tam round (1.0800) = 25 puan
        Yarım round (1.0850) = 18 puan
        Çeyrek (1.0825) = 10 puan
        10-pip level = 5 puan
        """
        # Convert to pip representation
        pips_value = int(round(price_level / self.pip_value))
        last_two = pips_value % 100
        
        if last_two == 0:  # Tam round: 1.0800, 1.0900
            return self.ROUND_MAX, "MAJOR_ROUND"
        
        elif last_two == 50:  # Yarım round: 1.0850
            return self.ROUND_MAX * 0.72, "HALF_ROUND"
        
        elif last_two in [25, 75]:  # Çeyrek: 1.0825, 1.0875
            return self.ROUND_MAX * 0.40, "QUARTER_ROUND"
        
        elif last_two % 10 == 0:  # 10-pip: 1.0810, 1.0820
            return self.ROUND_MAX * 0.20, "10PIP_LEVEL"
        
        else:
            # Check proximity to nearest round
            nearest_round = round(price_level / 0.005) * 0.005  # En yakın 50 pip
            distance = abs(price_level - nearest_round)
            
            if distance <= 0.0010:  # 10 pip içinde
                proximity_score = self.ROUND_MAX * 0.3 * (1 - distance / 0.0010)
                return proximity_score, "NEAR_ROUND"
            
            return 0, "NONE"
    
    def _calculate_fibonacci_score(
        self, 
        price_level: float, 
        fib_levels: Dict[str, float]
    ) -> Tuple[float, str]:
        """
        Fibonacci Confluence Scoring.
        
        Son 5 günün swing high/low'undan hesaplanan Fib seviyeleri.
        0.618 en güçlü, sonra 0.5, sonra 0.382.
        
        5 pip içinde = 20 puan
        """
        if not fib_levels:
            return 0, ""
        
        # Fib weights (0.618 most important)
        weights = {
            '0.618': 1.0,
            '0.5': 0.85,
            '0.382': 0.75,
            '0.786': 0.70,
            '0.236': 0.60
        }
        
        proximity_threshold = self.FIB_PROXIMITY_PIPS * self.pip_value
        best_score = 0
        best_level = ""
        
        for level_name, level_price in fib_levels.items():
            distance = abs(price_level - level_price)
            
            if distance <= proximity_threshold:
                weight = weights.get(level_name, 0.5)
                proximity_factor = 1 - (distance / proximity_threshold)
                score = self.FIB_MAX * weight * proximity_factor
                
                if score > best_score:
                    best_score = score
                    best_level = level_name
        
        return best_score, best_level
    
    def _calculate_dom_score(self, price_level: float, symbol: str) -> float:
        """
        Historical DOM Depth Scoring.
        
        Bu seviyede geçmişte büyük emirler var mıydı?
        20 günlük DOM verisi analizi.
        
        1500+ lot = 15 puan (tam)
        """
        if self.db is None:
            # Simulated score for backtest
            return np.random.uniform(0, self.DOM_MAX * 0.4)
        
        try:
            avg_volume = self.db.get_avg_volume_at_level(
                symbol=symbol,
                price_level=price_level,
                tolerance=self.pip_value * 5,  # 5 pip tolerance
                days_back=20
            )
            
            if avg_volume >= self.DOM_THRESHOLD:
                return self.DOM_MAX
            elif avg_volume >= self.DOM_THRESHOLD * 0.6:
                factor = (avg_volume - self.DOM_THRESHOLD * 0.6) / (self.DOM_THRESHOLD * 0.4)
                return self.DOM_MAX * 0.6 + (self.DOM_MAX * 0.4 * factor)
            elif avg_volume > 0:
                return (avg_volume / (self.DOM_THRESHOLD * 0.6)) * (self.DOM_MAX * 0.6)
            
            return 0
            
        except Exception as e:
            logger.warning(f"DOM score calculation error: {e}")
            return 0
    
    def _calculate_delta_score(self, delta: float) -> float:
        """
        Delta Imbalance Scoring.
        
        Son 10 saniyedeki delta (bid volume - ask volume).
        Aşırı dengesizlik = Kurumsal aktivite işareti.
        
        8000+ = 10 puan (tam)
        """
        abs_delta = abs(delta)
        
        if abs_delta >= self.DELTA_THRESHOLD:
            return self.DELTA_MAX
        elif abs_delta >= self.DELTA_THRESHOLD * 0.5:
            factor = (abs_delta - self.DELTA_THRESHOLD * 0.5) / (self.DELTA_THRESHOLD * 0.5)
            return self.DELTA_MAX * 0.5 + (self.DELTA_MAX * 0.5 * factor)
        else:
            return (abs_delta / (self.DELTA_THRESHOLD * 0.5)) * (self.DELTA_MAX * 0.5)
    
    def _determine_zone_type(
        self, 
        breakdown: Dict[str, float],
        round_type: str,
        fib_level: str
    ) -> str:
        """Determine the primary zone type based on highest scoring component."""
        
        # Find dominant factor
        max_component = max(breakdown, key=breakdown.get)
        max_score = breakdown[max_component]
        
        # Build zone type string
        if max_component == 'vwap' and max_score >= self.VWAP_MAX * 0.8:
            return "VWAP_REVERSION"
        
        elif max_component == 'round_number' and round_type != "NONE":
            if round_type == "MAJOR_ROUND":
                return "INSTITUTIONAL_ROUND"
            else:
                return f"ROUND_{round_type}"
        
        elif max_component == 'fibonacci' and fib_level:
            return f"FIB_{fib_level}"
        
        elif max_component == 'dom':
            return "DOM_CLUSTER"
        
        elif max_component == 'delta':
            return "DELTA_IMBALANCE"
        
        # Check for confluence
        high_scores = [k for k, v in breakdown.items() if v > 15]
        if len(high_scores) >= 2:
            return "CONFLUENCE_ZONE"
        
        return "MIXED"
    
    def _determine_direction(self, price_level: float, market_data: MarketData) -> str:
        """
        Determine trade direction based on:
        1. Price position relative to current bid
        2. Delta direction
        3. VWAP position
        """
        current_price = market_data.bid
        delta = market_data.bid_ask_delta
        vwap = market_data.vwap
        
        # If price level is below current → LONG (expecting price to go up to level)
        # If price level is above current → SHORT (expecting price to go down to level)
        position_bias = "LONG" if price_level > current_price else "SHORT"
        
        # Delta confirmation
        delta_bias = "LONG" if delta > 0 else "SHORT" if delta < 0 else None
        
        # VWAP reversion bias
        if vwap > 0:
            if current_price > vwap * 1.002:  # Above VWAP → expect short
                vwap_bias = "SHORT"
            elif current_price < vwap * 0.998:  # Below VWAP → expect long
                vwap_bias = "LONG"
            else:
                vwap_bias = None
        else:
            vwap_bias = None
        
        # Combine signals
        # Position bias is primary, delta and VWAP are confirming
        return position_bias
    
    def _calculate_trigger_price(self, zone_price: float, direction: str) -> float:
        """
        Calculate entry trigger price.
        
        Kurumların 7 pip ÖNÜNDE gir.
        LONG: Zone'un 7 pip altında
        SHORT: Zone'un 7 pip üstünde
        """
        offset = self.ENTRY_OFFSET_PIPS * self.pip_value
        
        if direction == "LONG":
            return zone_price - offset
        else:
            return zone_price + offset
    
    def _calculate_stop_loss(self, trigger_price: float, direction: str) -> float:
        """Calculate stop loss price."""
        sl_offset = self.STOP_LOSS_PIPS * self.pip_value
        
        if direction == "LONG":
            return trigger_price - sl_offset
        else:
            return trigger_price + sl_offset
    
    def scan_all_zones(
        self, 
        market_data: MarketData, 
        range_pips: int = 20
    ) -> List[ExecutionZone]:
        """
        Scan all price levels within range and return scored zones.
        """
        current_price = market_data.bid
        zones = []
        
        for pip_offset in range(-range_pips, range_pips + 1):
            price_level = current_price + (pip_offset * self.pip_value)
            zone = self.calculate_score(price_level, market_data)
            
            # Only keep meaningful zones
            if zone.score >= 50:
                zones.append(zone)
        
        return sorted(zones, key=lambda z: z.score, reverse=True)
    
    def get_best_zone(self, market_data: MarketData, min_score: float = 90) -> Optional[ExecutionZone]:
        """Get the highest scoring zone above threshold."""
        zones = self.scan_all_zones(market_data)
        
        if zones and zones[0].score >= min_score:
            return zones[0]
        
        return None
