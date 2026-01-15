"""
IOFAE Trading Bot - DOM Logger & Database
Handles DOM snapshots, trade history, and execution zone data storage.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import func


Base = declarative_base()


class DOMSnapshot(Base):
    """Level II DOM data snapshots."""
    __tablename__ = 'dom_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    price_level = Column(Float, nullable=False, index=True)
    bid_volume = Column(Float, default=0)
    ask_volume = Column(Float, default=0)
    total_volume = Column(Float, default=0)
    level_index = Column(Integer)  # DOM level 1-20


class TradeHistory(Base):
    """Trade history records."""
    __tablename__ = 'trade_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket = Column(Integer, unique=True, index=True)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)  # BUY, SELL
    lot_size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=True)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    profit = Column(Float, default=0)
    pips = Column(Float, default=0)
    score = Column(Float)
    zone_type = Column(String(50))  # VWAP, ROUND_NUMBER, FIBONACCI
    exit_reason = Column(String(50))  # EXHAUSTION, TIME_LIMIT, STOP_LOSS, MANUAL
    magic_number = Column(Integer)
    status = Column(String(20), default='OPEN')  # OPEN, CLOSED


class ExecutionZoneHistory(Base):
    """Historical execution zones and their outcomes."""
    __tablename__ = 'execution_zones'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price_level = Column(Float, nullable=False)
    score = Column(Float, nullable=False)
    vwap_score = Column(Float, default=0)
    round_number_score = Column(Float, default=0)
    fibonacci_score = Column(Float, default=0)
    dom_score = Column(Float, default=0)
    delta_score = Column(Float, default=0)
    was_triggered = Column(Boolean, default=False)
    outcome_pips = Column(Float, nullable=True)


class DailyStats(Base):
    """Daily trading statistics."""
    __tablename__ = 'daily_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True)  # YYYY-MM-DD
    starting_balance = Column(Float)
    ending_balance = Column(Float)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_profit = Column(Float, default=0)
    total_pips = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    win_rate = Column(Float, default=0)


class DOMLogger:
    """Database manager for IOFAE Trading Bot."""
    
    def __init__(self, db_path: str = "data/iofae_trades.db"):
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()
    
    # =========================================================================
    # DOM Snapshot Methods
    # =========================================================================
    
    def save_dom_snapshot(
        self,
        symbol: str,
        price_level: float,
        bid_volume: float,
        ask_volume: float,
        level_index: int = 0
    ):
        """Save a single DOM level snapshot."""
        session = self.get_session()
        try:
            snapshot = DOMSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                price_level=price_level,
                bid_volume=bid_volume,
                ask_volume=ask_volume,
                total_volume=bid_volume + ask_volume,
                level_index=level_index
            )
            session.add(snapshot)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def save_dom_bulk(self, symbol: str, dom_data: List[Dict]):
        """Save multiple DOM levels at once."""
        session = self.get_session()
        try:
            timestamp = datetime.now()
            for level in dom_data:
                snapshot = DOMSnapshot(
                    symbol=symbol,
                    timestamp=timestamp,
                    price_level=level.get('price', 0),
                    bid_volume=level.get('bid_volume', 0),
                    ask_volume=level.get('ask_volume', 0),
                    total_volume=level.get('bid_volume', 0) + level.get('ask_volume', 0),
                    level_index=level.get('level', 0)
                )
                session.add(snapshot)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_avg_volume_at_level(
        self,
        symbol: str,
        price_level: float,
        tolerance: float = 0.0005,
        days_back: int = 20
    ) -> float:
        """Get average volume at a specific price level over the past N days."""
        session = self.get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            result = session.query(func.avg(DOMSnapshot.total_volume)).filter(
                DOMSnapshot.symbol == symbol,
                DOMSnapshot.timestamp >= cutoff_date,
                DOMSnapshot.price_level >= price_level - tolerance,
                DOMSnapshot.price_level <= price_level + tolerance
            ).scalar()
            return result or 0.0
        finally:
            session.close()
    
    def cleanup_old_dom_data(self, days_to_keep: int = 20):
        """Remove DOM data older than specified days."""
        session = self.get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            session.query(DOMSnapshot).filter(
                DOMSnapshot.timestamp < cutoff_date
            ).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # =========================================================================
    # Trade History Methods
    # =========================================================================
    
    def save_trade_open(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        lot_size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float = 0,
        score: float = 0,
        zone_type: str = "",
        magic_number: int = 0
    ):
        """Save a new trade opening."""
        session = self.get_session()
        try:
            trade = TradeHistory(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=datetime.now(),
                score=score,
                zone_type=zone_type,
                magic_number=magic_number,
                status='OPEN'
            )
            session.add(trade)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def save_trade_close(
        self,
        ticket: int,
        exit_price: float,
        profit: float,
        pips: float,
        exit_reason: str
    ):
        """Update a trade with closing information."""
        session = self.get_session()
        try:
            trade = session.query(TradeHistory).filter_by(ticket=ticket).first()
            if trade:
                trade.exit_price = exit_price
                trade.exit_time = datetime.now()
                trade.profit = profit
                trade.pips = pips
                trade.exit_reason = exit_reason
                trade.status = 'CLOSED'
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_today_trades(self) -> List[TradeHistory]:
        """Get all trades from today."""
        session = self.get_session()
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            trades = session.query(TradeHistory).filter(
                TradeHistory.entry_time >= today_start
            ).all()
            return trades
        finally:
            session.close()
    
    def get_today_stats(self) -> Dict[str, Any]:
        """Get today's trading statistics."""
        trades = self.get_today_trades()
        
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_profit': 0,
                'total_pips': 0,
                'win_rate': 0
            }
        
        closed_trades = [t for t in trades if t.status == 'CLOSED']
        winning = [t for t in closed_trades if t.profit > 0]
        losing = [t for t in closed_trades if t.profit < 0]
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'total_profit': sum(t.profit for t in closed_trades),
            'total_pips': sum(t.pips for t in closed_trades),
            'win_rate': len(winning) / len(closed_trades) * 100 if closed_trades else 0
        }
    
    def get_last_trade_time(self) -> Optional[datetime]:
        """Get the timestamp of the last trade."""
        session = self.get_session()
        try:
            trade = session.query(TradeHistory).order_by(
                TradeHistory.entry_time.desc()
            ).first()
            return trade.entry_time if trade else None
        finally:
            session.close()
    
    # =========================================================================
    # Execution Zone Methods
    # =========================================================================
    
    def save_execution_zone(
        self,
        symbol: str,
        price_level: float,
        score: float,
        score_breakdown: Dict[str, float],
        was_triggered: bool = False,
        outcome_pips: float = None
    ):
        """Save an execution zone record."""
        session = self.get_session()
        try:
            zone = ExecutionZoneHistory(
                symbol=symbol,
                timestamp=datetime.now(),
                price_level=price_level,
                score=score,
                vwap_score=score_breakdown.get('vwap', 0),
                round_number_score=score_breakdown.get('round_number', 0),
                fibonacci_score=score_breakdown.get('fibonacci', 0),
                dom_score=score_breakdown.get('dom', 0),
                delta_score=score_breakdown.get('delta', 0),
                was_triggered=was_triggered,
                outcome_pips=outcome_pips
            )
            session.add(zone)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # =========================================================================
    # Daily Stats Methods
    # =========================================================================
    
    def save_daily_stats(
        self,
        date: str,
        starting_balance: float,
        ending_balance: float,
        total_trades: int,
        winning_trades: int,
        total_profit: float,
        total_pips: float,
        max_drawdown: float
    ):
        """Save or update daily statistics."""
        session = self.get_session()
        try:
            stats = session.query(DailyStats).filter_by(date=date).first()
            if stats:
                stats.ending_balance = ending_balance
                stats.total_trades = total_trades
                stats.winning_trades = winning_trades
                stats.losing_trades = total_trades - winning_trades
                stats.total_profit = total_profit
                stats.total_pips = total_pips
                stats.max_drawdown = max_drawdown
                stats.win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
            else:
                stats = DailyStats(
                    date=date,
                    starting_balance=starting_balance,
                    ending_balance=ending_balance,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=total_trades - winning_trades,
                    total_profit=total_profit,
                    total_pips=total_pips,
                    max_drawdown=max_drawdown,
                    win_rate=winning_trades / total_trades * 100 if total_trades > 0 else 0
                )
                session.add(stats)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_challenge_stats(self, start_date: str) -> Dict[str, Any]:
        """Get cumulative stats since challenge start."""
        session = self.get_session()
        try:
            stats = session.query(DailyStats).filter(
                DailyStats.date >= start_date
            ).all()
            
            if not stats:
                return {
                    'total_days': 0,
                    'trading_days': 0,
                    'total_profit': 0,
                    'max_drawdown': 0
                }
            
            return {
                'total_days': len(stats),
                'trading_days': len([s for s in stats if s.total_trades > 0]),
                'total_profit': sum(s.total_profit for s in stats),
                'max_drawdown': max(s.max_drawdown for s in stats)
            }
        finally:
            session.close()
