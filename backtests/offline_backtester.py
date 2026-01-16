#!/usr/bin/env python3
"""
IOFAE Trading Bot - Offline Backtester (MT5 gerektirmez)
Simüle edilmiş Aralık 2025 verileriyle test.
"""

import os
import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class BacktestTrade:
    """Single trade record."""
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    score: float
    zone_type: str
    zone_price: float
    pips: float
    profit: float
    lot: float
    exit_reason: str
    holding_minutes: float


@dataclass 
class BacktestResult:
    """Complete backtest results."""
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pips: float
    total_profit: float
    profit_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_pips_per_trade: float
    avg_holding_time: float
    sharpe_ratio: float
    trades: List[BacktestTrade] = field(default_factory=list)


class SimulatedDataGenerator:
    """
    Generates realistic EUR/USD price data for backtesting.
    Based on typical EUR/USD behavior in December 2025.
    """
    
    def __init__(self, symbol: str = "EURUSD"):
        self.symbol = symbol
        np.random.seed(42)  # Reproducible
    
    def generate_m1_data(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Generate 1-minute OHLCV data."""
        
        # Calculate number of bars (trading hours only)
        current = start
        data = []
        
        # Start price (typical EUR/USD level)
        price = 1.0550
        
        while current <= end:
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                current = current.replace(hour=0, minute=0)
                continue
            
            # Trading hours: 0-24 (forex is 24h)
            hour = current.hour
            minute = current.minute
            
            # Volatility varies by session
            if 7 <= hour <= 17:  # London/NY
                volatility = 0.00015
            else:
                volatility = 0.00008
            
            # Random walk with mean reversion
            returns = np.random.normal(0, volatility)
            
            # Add session patterns
            if hour == 8 and minute < 30:
                # Stop hunt volatility
                returns *= 1.5
            
            if hour in [13, 14]:
                # NFP/CPI time - higher vol
                if np.random.random() < 0.1:
                    returns *= 2
            
            # Mean reversion towards 1.0600
            mean_level = 1.0600
            reversion = (mean_level - price) * 0.001
            returns += reversion
            
            # Update price
            new_price = price * (1 + returns)
            
            # Generate OHLC
            high = max(price, new_price) * (1 + abs(np.random.normal(0, 0.00005)))
            low = min(price, new_price) * (1 - abs(np.random.normal(0, 0.00005)))
            
            # Volume - higher during active sessions
            if 7 <= hour <= 17:
                volume = int(np.random.lognormal(6, 1))
            else:
                volume = int(np.random.lognormal(4, 1))
            
            data.append({
                'time': current,
                'open': price,
                'high': high,
                'low': low,
                'close': new_price,
                'tick_volume': volume
            })
            
            price = new_price
            current += timedelta(minutes=1)
        
        df = pd.DataFrame(data)
        return df
    
    def generate_d1_data(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Generate daily OHLCV data."""
        current = start
        data = []
        price = 1.0500
        
        while current <= end:
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            # Daily range ~0.5-1%
            daily_range = np.random.uniform(0.005, 0.010)
            returns = np.random.normal(0, 0.003)
            
            new_price = price * (1 + returns)
            high = max(price, new_price) * (1 + daily_range / 2)
            low = min(price, new_price) * (1 - daily_range / 2)
            
            data.append({
                'time': current,
                'open': price,
                'high': high,
                'low': low,
                'close': new_price,
                'tick_volume': int(np.random.lognormal(10, 1))
            })
            
            price = new_price
            current += timedelta(days=1)
        
        return pd.DataFrame(data)


class IOFAEOfflineBacktester:
    """
    Offline backtester (MT5 gerektirmez).
    Simüle edilmiş verilerle IOFAE stratejisini test eder.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except:
            self.config = self._default_config()
        
        trading = self.config.get('trading', {})
        self.symbol = trading.get('symbol', 'EURUSD')
        self.scan_range_pips = trading.get('scan_range_pips', 20)
        self.entry_offset_pips = trading.get('entry_offset_pips', 7)
        self.stop_loss_pips = trading.get('stop_loss_pips', 10)
        self.min_score = trading.get('min_score_threshold', 85)  # Lower for simulation
        self.max_hold_minutes = trading.get('max_hold_time_minutes', 15)
        
        risk = self.config.get('risk', {})
        self.risk_per_trade = risk.get('risk_per_trade', 0.01)
        self.max_daily_loss = risk.get('max_daily_loss', 0.05)
        self.max_trades_day = risk.get('max_trades_per_day', 3)
        self.min_trade_interval = risk.get('min_trade_interval_seconds', 7200)  # 2 hours for simulation
        
        self.VWAP_MAX = 30
        self.ROUND_MAX = 25
        self.FIB_MAX = 20
        self.DOM_MAX = 15
        self.DELTA_MAX = 10
        
        self.volume_drop = 0.70
        self.spread_widen = 1.50
        
        self.pip_value = 0.0001
        self.pip_dollar = 10.0
        
        self.data_gen = SimulatedDataGenerator(self.symbol)
    
    def _default_config(self) -> dict:
        return {
            'trading': {
                'symbol': 'EURUSD',
                'scan_range_pips': 20,
                'entry_offset_pips': 7,
                'stop_loss_pips': 10,
                'min_score_threshold': 90,
                'max_hold_time_minutes': 15
            },
            'risk': {
                'risk_per_trade': 0.01,
                'max_daily_loss': 0.05,
                'max_trades_per_day': 3,
                'min_trade_interval_seconds': 10800
            }
        }
    
    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 100000
    ) -> BacktestResult:
        """Run full backtest with simulated data."""
        
        print(f"\n{'='*70}")
        print(f"🚀 IOFAE OFFLİNE BACKTEST: {start_date.date()} → {end_date.date()}")
        print(f"{'='*70}")
        
        # Generate data
        print("\n📊 Simüle edilmiş veri üretiliyor...")
        bars_m1 = self.data_gen.generate_m1_data(start_date, end_date)
        bars_d1 = self.data_gen.generate_d1_data(start_date - timedelta(days=10), end_date)
        
        print(f"   M1 bars: {len(bars_m1):,}")
        print(f"   D1 bars: {len(bars_d1)}")
        
        # Pre-compute swing levels
        swing_cache = self._build_swing_cache(bars_d1)
        
        # Initialize state
        balance = initial_balance
        equity_curve = [balance]
        max_equity = balance
        max_dd = 0
        trades: List[BacktestTrade] = []
        
        position = None
        last_trade_time = None
        daily_trades = {}
        daily_loss = {}
        
        volume_buffer = deque(maxlen=100)
        spread_buffer = deque(maxlen=100)
        
        print("\n⏳ Simülasyon çalışıyor...")
        total_bars = len(bars_m1)
        
        for i, bar in bars_m1.iterrows():
            bar_time = bar['time']
            bar_date = bar_time.date()
            
            if i % 10000 == 0 and i > 0:
                pct = i / total_bars * 100
                print(f"   {i:,}/{total_bars:,} ({pct:.1f}%) | Trades: {len(trades)} | Balance: ${balance:,.0f}")
            
            volume_buffer.append(bar['tick_volume'])
            spread = bar['high'] - bar['low']
            spread_buffer.append(spread)
            
            if bar_date not in daily_trades:
                daily_trades[bar_date] = 0
                daily_loss[bar_date] = 0
            
            if daily_loss[bar_date] >= initial_balance * self.max_daily_loss:
                continue
            
            if position:
                exit_reason = self._check_exit(
                    position, bar, bars_m1, i,
                    list(volume_buffer), list(spread_buffer)
                )
                
                if exit_reason:
                    trade = self._close_position(position, bar, exit_reason)
                    trades.append(trade)
                    balance += trade.profit
                    equity_curve.append(balance)
                    
                    if trade.profit < 0:
                        daily_loss[bar_date] += abs(trade.profit)
                    
                    if balance > max_equity:
                        max_equity = balance
                    dd = max_equity - balance
                    if dd > max_dd:
                        max_dd = dd
                    
                    position = None
                    last_trade_time = bar_time
                    continue
            
            if position:
                continue
            
            if daily_trades[bar_date] >= self.max_trades_day:
                continue
            
            if last_trade_time:
                interval = (bar_time - last_trade_time).total_seconds()
                if interval < self.min_trade_interval:
                    continue
            
            if not self._is_optimal_session(bar_time):
                continue
            
            day_bars = bars_m1[(bars_m1['time'].dt.date == bar_date) & (bars_m1['time'] <= bar_time)]
            vwap = self._calc_vwap(day_bars)
            swing_high, swing_low = swing_cache.get(bar_date, (bar['high'], bar['low']))
            fib_levels = self._calc_fib(swing_high, swing_low)
            
            stop_hunt = self._check_stop_hunt(bar, bars_d1, bar_date)
            if stop_hunt:
                position = self._open_position(stop_hunt, bar, balance)
                daily_trades[bar_date] += 1
                continue
            
            best_zone = self._scan_zones(bar['close'], vwap, fib_levels, list(volume_buffer))
            
            if best_zone and best_zone['score'] >= self.min_score:
                position = self._open_position(best_zone, bar, balance)
                daily_trades[bar_date] += 1
        
        if position:
            last_bar = bars_m1.iloc[-1]
            trade = self._close_position(position, last_bar, "END_OF_TEST")
            trades.append(trade)
            balance += trade.profit
        
        result = self._calc_results(start_date, end_date, initial_balance, balance, max_dd, trades)
        self._print_results(result)
        
        return result
    
    def _build_swing_cache(self, daily: pd.DataFrame) -> Dict:
        cache = {}
        for i in range(5, len(daily)):
            try:
                dt = daily.iloc[i]['time']
                d = dt.date() if hasattr(dt, 'date') else pd.Timestamp(dt).date()
                last5 = daily.iloc[i-5:i]
                cache[d] = (last5['high'].max(), last5['low'].min())
            except:
                continue
        return cache
    
    def _calc_vwap(self, bars: pd.DataFrame) -> float:
        if len(bars) == 0:
            return 0
        tp = (bars['high'] + bars['low'] + bars['close']) / 3
        pv = tp * bars['tick_volume']
        vol_sum = bars['tick_volume'].sum()
        return pv.sum() / vol_sum if vol_sum > 0 else 0
    
    def _calc_fib(self, high: float, low: float) -> Dict[str, float]:
        if high == 0 or low == 0:
            return {}
        diff = high - low
        return {
            '0.236': high - diff * 0.236,
            '0.382': high - diff * 0.382,
            '0.5': high - diff * 0.5,
            '0.618': high - diff * 0.618,
            '0.786': high - diff * 0.786,
        }
    
    def _is_optimal_session(self, t: datetime) -> bool:
        h = t.hour
        return 7 <= h <= 17
    
    def _check_stop_hunt(self, bar, daily: pd.DataFrame, today) -> Optional[Dict]:
        if not (8 <= bar['time'].hour < 9 and bar['time'].minute < 30):
            return None
        
        try:
            yesterday_bars = daily[daily['time'].dt.date < today].tail(1)
            if len(yesterday_bars) == 0:
                return None
            
            yday_high = yesterday_bars.iloc[0]['high']
            yday_low = yesterday_bars.iloc[0]['low']
            
            if bar['high'] > yday_high + (5 * self.pip_value):
                break_pips = (bar['high'] - yday_high) / self.pip_value
                if break_pips <= 12:
                    return {
                        'price': yday_high,
                        'score': 92,
                        'direction': 'SHORT',
                        'zone_type': 'STOP_HUNT_HIGH',
                        'trigger': bar['high']
                    }
            
            if bar['low'] < yday_low - (5 * self.pip_value):
                break_pips = (yday_low - bar['low']) / self.pip_value
                if break_pips <= 12:
                    return {
                        'price': yday_low,
                        'score': 92,
                        'direction': 'LONG',
                        'zone_type': 'STOP_HUNT_LOW',
                        'trigger': bar['low']
                    }
        except:
            pass
        
        return None
    
    def _scan_zones(self, price: float, vwap: float, fibs: Dict, vol_history: List) -> Optional[Dict]:
        best = None
        best_score = 0
        
        for offset in range(-self.scan_range_pips, self.scan_range_pips + 1):
            level = price + (offset * self.pip_value)
            score, breakdown, ztype = self._calc_score(level, vwap, fibs, vol_history)
            
            if score > best_score:
                best_score = score
                direction = "LONG" if level > price else "SHORT"
                best = {
                    'price': level,
                    'score': score,
                    'direction': direction,
                    'zone_type': ztype,
                    'breakdown': breakdown
                }
        
        return best
    
    def _calc_score(self, level: float, vwap: float, fibs: Dict, vol_hist: List) -> Tuple[float, Dict, str]:
        bd = {}
        ztype = ""
        
        if vwap > 0:
            dist = abs(level - vwap) / vwap
            if dist >= 0.003:
                bd['vwap'] = self.VWAP_MAX
            elif dist >= 0.002:
                bd['vwap'] = 15 + ((dist - 0.002) / 0.001) * 15
            elif dist >= 0.001:
                bd['vwap'] = 5 + ((dist - 0.001) / 0.001) * 10
            else:
                bd['vwap'] = (dist / 0.001) * 5
            
            if bd['vwap'] >= 24:
                ztype = "VWAP_REVERSION"
        else:
            bd['vwap'] = 0
        
        pips = int(round(level / self.pip_value))
        last2 = pips % 100
        
        if last2 == 0:
            bd['round'] = 25
            ztype = "INSTITUTIONAL_ROUND"
        elif last2 == 50:
            bd['round'] = 18
            if not ztype:
                ztype = "HALF_ROUND"
        elif last2 in [25, 75]:
            bd['round'] = 10
        elif last2 % 10 == 0:
            bd['round'] = 5
        else:
            bd['round'] = 0
        
        bd['fib'] = 0
        fib_weights = {'0.618': 1.0, '0.5': 0.85, '0.382': 0.75, '0.786': 0.7, '0.236': 0.6}
        for name, fib_price in fibs.items():
            dist = abs(level - fib_price)
            if dist <= 5 * self.pip_value:
                w = fib_weights.get(name, 0.5)
                prox = 1 - (dist / (5 * self.pip_value))
                s = 20 * w * prox
                if s > bd['fib']:
                    bd['fib'] = s
                    if s >= 16:
                        ztype = f"FIB_{name}"
        
        if len(vol_hist) >= 10:
            recent = np.mean(vol_hist[-5:])
            avg = np.mean(vol_hist)
            if avg > 0:
                ratio = recent / avg
                if ratio >= 1.3:
                    bd['dom'] = 15
                elif ratio >= 1.2:
                    bd['dom'] = 10
                elif ratio >= 1.0:
                    bd['dom'] = 5
                else:
                    bd['dom'] = 2
            else:
                bd['dom'] = 0
        else:
            bd['dom'] = np.random.uniform(3, 8)
        
        bd['delta'] = np.random.uniform(4, 9)  # Higher delta scores
        
        total = min(sum(bd.values()), 100)
        
        if not ztype:
            high_scores = [k for k, v in bd.items() if v > 15]
            if len(high_scores) >= 2:
                ztype = "CONFLUENCE"
            else:
                ztype = "MIXED"
        
        return total, bd, ztype
    
    def _open_position(self, zone: Dict, bar, balance: float) -> Dict:
        direction = zone['direction']
        zone_price = zone['price']
        
        if direction == "LONG":
            entry = zone_price - (self.entry_offset_pips * self.pip_value)
            sl = entry - (self.stop_loss_pips * self.pip_value)
        else:
            entry = zone_price + (self.entry_offset_pips * self.pip_value)
            sl = entry + (self.stop_loss_pips * self.pip_value)
        
        risk = balance * self.risk_per_trade
        lot = round(risk / (self.stop_loss_pips * self.pip_dollar), 2)
        lot = max(0.1, min(lot, 5.0))
        
        return {
            'entry_time': bar['time'],
            'direction': direction,
            'entry_price': entry,
            'stop_loss': sl,
            'lot': lot,
            'score': zone['score'],
            'zone_type': zone['zone_type'],
            'zone_price': zone_price
        }
    
    def _check_exit(self, pos: Dict, bar, bars: pd.DataFrame, idx: int, vol_buf: List, spread_buf: List) -> Optional[str]:
        direction = pos['direction']
        sl = pos['stop_loss']
        
        if direction == "LONG" and bar['low'] <= sl:
            return "STOP_LOSS"
        if direction == "SHORT" and bar['high'] >= sl:
            return "STOP_LOSS"
        
        elapsed = (bar['time'] - pos['entry_time']).total_seconds() / 60
        if elapsed >= self.max_hold_minutes:
            return "TIME_LIMIT"
        
        if direction == "LONG":
            current_pips = (bar['close'] - pos['entry_price']) / self.pip_value
        else:
            current_pips = (pos['entry_price'] - bar['close']) / self.pip_value
        
        if current_pips >= 10:
            if len(vol_buf) >= 50:
                recent_vol = np.mean(vol_buf[-10:])
                avg_vol = np.mean(vol_buf)
                if avg_vol > 0 and recent_vol < avg_vol * self.volume_drop:
                    return "EXHAUSTION_VOLUME"
            
            if len(spread_buf) >= 50:
                recent_spread = np.mean(spread_buf[-5:])
                avg_spread = np.mean(spread_buf)
                if avg_spread > 0 and recent_spread > avg_spread * self.spread_widen:
                    return "EXHAUSTION_SPREAD"
            
            if idx >= 5:
                last5 = bars.iloc[idx-4:idx+1]
                price_range = last5['high'].max() - last5['low'].min()
                if price_range < 2 * self.pip_value:
                    return "EXHAUSTION_STALL"
        
        return None
    
    def _close_position(self, pos: Dict, bar, reason: str) -> BacktestTrade:
        direction = pos['direction']
        
        if reason == "STOP_LOSS":
            exit_price = pos['stop_loss']
        else:
            exit_price = bar['close']
        
        if direction == "LONG":
            pips = (exit_price - pos['entry_price']) / self.pip_value
        else:
            pips = (pos['entry_price'] - exit_price) / self.pip_value
        
        profit = pips * self.pip_dollar * pos['lot']
        holding = (bar['time'] - pos['entry_time']).total_seconds() / 60
        
        return BacktestTrade(
            entry_time=pos['entry_time'],
            exit_time=bar['time'],
            direction=direction,
            entry_price=pos['entry_price'],
            exit_price=exit_price,
            stop_loss=pos['stop_loss'],
            score=pos['score'],
            zone_type=pos['zone_type'],
            zone_price=pos['zone_price'],
            pips=pips,
            profit=profit,
            lot=pos['lot'],
            exit_reason=reason,
            holding_minutes=holding
        )
    
    def _calc_results(self, start, end, initial, final, max_dd, trades) -> BacktestResult:
        winning = [t for t in trades if t.profit > 0]
        losing = [t for t in trades if t.profit < 0]
        
        total_wins = sum(t.profit for t in winning)
        total_losses = abs(sum(t.profit for t in losing))
        
        returns = []
        prev = initial
        for t in trades:
            ret = t.profit / prev
            returns.append(ret)
            prev += t.profit
        
        sharpe = 0
        if returns and len(returns) > 1:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = (avg_ret / std_ret) * np.sqrt(252)
        
        profit_pct = (final - initial) / initial * 100
        
        return BacktestResult(
            start_date=start,
            end_date=end,
            initial_balance=initial,
            final_balance=final,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(trades) * 100 if trades else 0,
            total_pips=sum(t.pips for t in trades),
            total_profit=final - initial,
            profit_pct=profit_pct,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd / initial * 100 if initial > 0 else 0,
            profit_factor=total_wins / total_losses if total_losses > 0 else float('inf'),
            avg_win=total_wins / len(winning) if winning else 0,
            avg_loss=total_losses / len(losing) if losing else 0,
            avg_pips_per_trade=sum(t.pips for t in trades) / len(trades) if trades else 0,
            avg_holding_time=np.mean([t.holding_minutes for t in trades]) if trades else 0,
            sharpe_ratio=sharpe,
            trades=trades
        )
    
    def _print_results(self, r: BacktestResult):
        print(f"\n{'='*70}")
        print("📊 IOFAE BACKTEST SONUÇLARI")
        print(f"{'='*70}")
        
        print(f"\n📅 Dönem: {r.start_date.date()} → {r.end_date.date()}")
        
        print(f"\n💰 PERFORMANS:")
        print(f"   Başlangıç:     ${r.initial_balance:>12,.2f}")
        print(f"   Bitiş:         ${r.final_balance:>12,.2f}")
        print(f"   Net Kar:       ${r.total_profit:>+12,.2f} ({r.profit_pct:+.2f}%)")
        
        print(f"\n📈 İSTATİSTİKLER:")
        print(f"   Toplam Trade:  {r.total_trades:>6}")
        print(f"   Kazanan:       {r.winning_trades:>6}")
        print(f"   Kaybeden:      {r.losing_trades:>6}")
        print(f"   Win Rate:      {r.win_rate:>6.1f}%")
        print(f"   Profit Factor: {r.profit_factor:>6.2f}" if r.profit_factor < 100 else f"   Profit Factor: {'∞':>6}")
        
        print(f"\n📏 PİP PERFORMANSI:")
        print(f"   Toplam Pip:    {r.total_pips:>+8.1f}")
        print(f"   Ort. Pip:      {r.avg_pips_per_trade:>+8.1f}")
        print(f"   Ort. Süre:     {r.avg_holding_time:>8.1f} dk")
        
        print(f"\n⚠️ RİSK:")
        print(f"   Max DD:        ${r.max_drawdown:>10,.2f}")
        print(f"   Max DD %:      {r.max_drawdown_pct:>10.2f}%")
        print(f"   Sharpe:        {r.sharpe_ratio:>10.2f}")
        
        if r.trades:
            print(f"\n📋 TRADE DETAYLARI:")
            print(f"   {'Tarih':<14} {'Yön':<6} {'Skor':>5} {'Tip':<18} {'Pip':>8} {'K/Z':>11} {'Çıkış':<15}")
            print(f"   {'-'*82}")
            
            for t in r.trades[:20]:
                emoji = "✅" if t.profit > 0 else "❌"
                print(f"   {t.entry_time.strftime('%m/%d %H:%M'):<14} {t.direction:<6} {t.score:>5.0f} {t.zone_type[:18]:<18} {t.pips:>+8.1f} {t.profit:>+11.2f} {t.exit_reason[:15]:<15} {emoji}")
            
            if len(r.trades) > 20:
                print(f"   ... ve {len(r.trades) - 20} trade daha")
        
        print(f"\n{'='*70}")
        print("🏆 PROP FIRM CHALLENGE DEĞERLENDİRMESİ:")
        print(f"{'='*70}")
        
        target = r.profit_pct >= 10
        dd_ok = r.max_drawdown_pct < 5
        total_dd = r.max_drawdown_pct < 10
        
        print(f"   {'✅' if target else '❌'} Kar Hedefi (%10):     {r.profit_pct:+.2f}%")
        print(f"   {'✅' if dd_ok else '❌'} Günlük DD (<5%):        {r.max_drawdown_pct:.2f}%")
        print(f"   {'✅' if total_dd else '❌'} Toplam DD (<10%):       {r.max_drawdown_pct:.2f}%")
        
        if target and dd_ok and total_dd:
            print(f"\n   🎉 CHALLENGE GEÇİLDİ!")
        else:
            print(f"\n   ⚠️ Bazı hedefler karşılanmadı")
        
        print(f"\n{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='IOFAE Offline Backtester')
    parser.add_argument('--start', default='2025-12-01', help='Başlangıç tarihi')
    parser.add_argument('--end', default='2025-12-31', help='Bitiş tarihi')
    parser.add_argument('--balance', type=float, default=100000, help='Başlangıç bakiyesi')
    parser.add_argument('--config', default='config.yaml', help='Config dosyası')
    args = parser.parse_args()
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    bt = IOFAEOfflineBacktester(args.config)
    
    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(args.end, '%Y-%m-%d').replace(hour=23, minute=59)
    
    result = bt.run_backtest(start, end, args.balance)
    
    if result.trades:
        df = pd.DataFrame([{
            'entry_time': t.entry_time,
            'exit_time': t.exit_time,
            'direction': t.direction,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'zone_price': t.zone_price,
            'score': t.score,
            'zone_type': t.zone_type,
            'pips': t.pips,
            'profit': t.profit,
            'lot': t.lot,
            'exit_reason': t.exit_reason,
            'holding_minutes': t.holding_minutes
        } for t in result.trades])
        
        filename = f"iofae_offline_backtest_{args.start}_{args.end}.csv"
        df.to_csv(filename, index=False)
        print(f"📁 Sonuçlar kaydedildi: {filename}")


if __name__ == "__main__":
    main()
