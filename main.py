#!/usr/bin/env python3
"""
IOFAE Trading Bot - Main Entry Point
Institutional Order Flow Anticipation Engine

A prop trading bot that detects critical price levels where institutional orders 
are likely to trigger, and opens positions 5-7 pips before these levels.
"""

import os
import sys
import time
import yaml
import signal
from datetime import datetime, date
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_collector import DataCollector
from score_calculator import ScoreCalculator
from signal_generator import SignalGenerator
from position_manager import PositionManager
from risk_controller import RiskController
from database.dom_logger import DOMLogger
from utils.logger import IOFAELogger
from utils.notifier import create_notifier


class IOFAEBot:
    """
    Main IOFAE Trading Bot class.
    Coordinates all modules for automated trading.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = False
        self._current_date = None
        
        # Initialize logger
        log_config = self.config.get('logging', {})
        self.logger = IOFAELogger(
            level=log_config.get('level', 'INFO'),
            file_path=log_config.get('file_path', 'logs/iofae.log'),
            max_size_mb=log_config.get('max_size_mb', 10),
            backup_count=log_config.get('backup_count', 5),
            console_output=log_config.get('console_output', True)
        )
        
        # Initialize database
        db_config = self.config.get('database', {})
        self.db = DOMLogger(db_config.get('path', 'data/iofae_trades.db'))
        
        # Initialize notifier
        self.notifier = create_notifier(self.config)
        
        # Initialize modules (will be fully set up in initialize())
        self.collector: Optional[DataCollector] = None
        self.score_calc: Optional[ScoreCalculator] = None
        self.signal_gen: Optional[SignalGenerator] = None
        self.position_mgr: Optional[PositionManager] = None
        self.risk_ctrl: Optional[RiskController] = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Config parse error: {e}")
            sys.exit(1)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def initialize(self) -> bool:
        """Initialize all bot components."""
        self.logger.info("=" * 60)
        self.logger.info("IOFAE Trading Bot - Initializing")
        self.logger.info("=" * 60)
        
        # Initialize data collector
        self.collector = DataCollector(self.config)
        if not self.collector.initialize():
            self.logger.error("Failed to initialize data collector")
            return False
        
        pip_value = self.collector.get_pip_value()
        
        # Initialize score calculator
        self.score_calc = ScoreCalculator(self.config, self.db)
        self.score_calc.set_pip_value(pip_value)
        
        # Initialize signal generator
        self.signal_gen = SignalGenerator(self.config, self.score_calc, self.db)
        self.signal_gen.set_pip_value(pip_value)
        
        # Initialize position manager
        self.position_mgr = PositionManager(self.config, self.collector)
        self.position_mgr.set_pip_value(pip_value)
        
        # Initialize risk controller
        account = self.collector.get_account_info()
        self.risk_ctrl = RiskController(self.config, self.db, self.notifier)
        self.risk_ctrl.initialize(account.get('balance', 0))
        
        # Store current date for daily reset
        self._current_date = date.today()
        
        self.logger.info(f"Symbol: {self.config.get('trading', {}).get('symbol', 'EURUSD')}")
        self.logger.info(f"Balance: ${account.get('balance', 0):.2f}")
        self.logger.info(f"Pip value: {pip_value}")
        self.logger.info("Initialization complete")
        
        # Send startup notification
        if self.notifier:
            self.notifier.notify_bot_started(
                self.config.get('trading', {}).get('symbol', 'EURUSD'),
                account.get('balance', 0)
            )
        
        return True
    
    def run(self):
        """Main trading loop."""
        if not self.initialize():
            self.logger.error("Initialization failed. Exiting.")
            return
        
        self.running = True
        self.logger.info("Starting main trading loop...")
        
        while self.running:
            try:
                # Check for daily reset
                if date.today() != self._current_date:
                    self._daily_reset()
                
                # Check if bot is stopped due to risk
                if self.risk_ctrl.is_stopped():
                    self.logger.warning("Bot stopped due to risk limits")
                    time.sleep(60)
                    continue
                
                # Collect market data
                market_data = self.collector.collect()
                if market_data is None:
                    time.sleep(1)
                    continue
                
                # Update risk controller with current balance
                account = self.collector.get_account_info()
                self.risk_ctrl.update_balance(account.get('balance', 0))
                
                # Monitor open positions
                self._monitor_positions()
                
                # Check if we can trade
                can_trade, reason = self.risk_ctrl.can_trade()
                if not can_trade:
                    time.sleep(1)
                    continue
                
                # Check for existing positions
                positions = self.position_mgr.get_open_positions()
                if positions:
                    # Already have open position, don't look for new signals
                    time.sleep(1)
                    continue
                
                # Scan for signals
                signal = self.signal_gen.scan_and_generate(market_data)
                
                if signal:
                    self._execute_signal(signal)
                
                # Sleep before next iteration
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                if self.notifier:
                    self.notifier.notify_error(str(e), "MainLoop")
                time.sleep(5)
        
        self.shutdown()
    
    def _monitor_positions(self):
        """Monitor and manage open positions."""
        positions = self.position_mgr.get_open_positions()
        
        for position in positions:
            close_reason = self.position_mgr.monitor_position(position)
            
            if close_reason:
                # Close position
                if self.position_mgr.close_position(position, close_reason):
                    # Record in database
                    if self.db:
                        self.db.save_trade_close(
                            ticket=position.ticket,
                            exit_price=position.current_price,
                            profit=position.profit,
                            pips=position.pips,
                            exit_reason=close_reason
                        )
                    
                    # Record in risk controller
                    self.risk_ctrl.record_trade(position.profit)
                    
                    # Send notification
                    if self.notifier:
                        duration = (datetime.now() - position.entry_time).total_seconds() / 60
                        self.notifier.notify_trade_close(
                            symbol=position.symbol,
                            direction=position.direction,
                            lot=position.volume,
                            entry_price=position.entry_price,
                            exit_price=position.current_price,
                            profit=position.profit,
                            pips=position.pips,
                            reason=close_reason,
                            duration_mins=duration
                        )
    
    def _execute_signal(self, signal):
        """Execute a trade signal."""
        account = self.collector.get_account_info()
        balance = account.get('balance', 0)
        
        # Calculate position size
        stop_pips = self.config.get('trading', {}).get('stop_loss_pips', 10)
        lot_size = self.risk_ctrl.calculate_lot_size(balance, stop_pips)
        
        # Execute trade
        ticket = self.position_mgr.execute_signal(signal, lot_size)
        
        if ticket:
            # Record in database
            if self.db:
                self.db.save_trade_open(
                    ticket=ticket,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    lot_size=lot_size,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    score=signal.zone.score,
                    zone_type=signal.zone.zone_type,
                    magic_number=self.config.get('trading', {}).get('magic_number', 123456)
                )
            
            # Send notification
            if self.notifier:
                self.notifier.notify_trade_open(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    lot=lot_size,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    score=signal.zone.score,
                    zone_type=signal.zone.zone_type,
                    confluence=signal.confluence_factors
                )
    
    def _daily_reset(self):
        """Perform daily reset operations."""
        self.logger.info("Performing daily reset...")
        
        # Send daily summary
        if self.db and self.notifier:
            stats = self.db.get_today_stats()
            account = self.collector.get_account_info()
            daily_stats = self.risk_ctrl.get_daily_stats()
            
            self.notifier.notify_daily_summary(
                date=self._current_date.strftime('%Y-%m-%d'),
                total_trades=stats.get('total_trades', 0),
                winning_trades=stats.get('winning_trades', 0),
                total_profit=stats.get('total_profit', 0),
                total_pips=stats.get('total_pips', 0),
                current_balance=account.get('balance', 0),
                daily_drawdown=daily_stats.get('daily_dd_pct', 0)
            )
            
            # Save daily stats to DB
            self.db.save_daily_stats(
                date=self._current_date.strftime('%Y-%m-%d'),
                starting_balance=daily_stats.get('starting_balance', 0),
                ending_balance=account.get('balance', 0),
                total_trades=stats.get('total_trades', 0),
                winning_trades=stats.get('winning_trades', 0),
                total_profit=stats.get('total_profit', 0),
                total_pips=stats.get('total_pips', 0),
                max_drawdown=daily_stats.get('daily_dd_pct', 0)
            )
        
        # Reset risk controller
        account = self.collector.get_account_info()
        self.risk_ctrl.reset_daily(account.get('balance', 0))
        
        # Update current date
        self._current_date = date.today()
        
        # Cleanup old DOM data
        if self.db:
            dom_days = self.config.get('database', {}).get('dom_history_days', 20)
            self.db.cleanup_old_dom_data(dom_days)
    
    def stop(self):
        """Stop the bot gracefully."""
        self.running = False
    
    def shutdown(self):
        """Shutdown all components."""
        self.logger.info("Shutting down IOFAE Bot...")
        
        # Close any open positions (optional - comment out if you want to keep them)
        # positions = self.position_mgr.get_open_positions()
        # for pos in positions:
        #     self.position_mgr.close_position(pos, "SHUTDOWN")
        
        # Disconnect from MT5
        if self.collector:
            self.collector.shutdown()
        
        # Send shutdown notification
        if self.notifier:
            self.notifier.notify_bot_stopped("Manual shutdown")
        
        self.logger.info("Shutdown complete")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='IOFAE Trading Bot')
    parser.add_argument('--config', '-c', default='config.yaml', help='Config file path')
    parser.add_argument('--test', '-t', action='store_true', help='Run in test mode')
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    bot = IOFAEBot(config_path=args.config)
    
    if args.test:
        # Test mode - just initialize and print status
        if bot.initialize():
            print("\n✅ Bot initialized successfully!")
            print("\nAccount Info:")
            account = bot.collector.get_account_info()
            for key, value in account.items():
                print(f"  {key}: {value}")
            
            print("\nCollecting sample data...")
            data = bot.collector.collect()
            if data:
                print(f"  Symbol: {data.symbol}")
                print(f"  Bid: {data.bid:.5f}")
                print(f"  Ask: {data.ask:.5f}")
                print(f"  VWAP: {data.vwap:.5f}")
                print(f"  Swing High: {data.swing_high:.5f}")
                print(f"  Swing Low: {data.swing_low:.5f}")
                
                print("\nTop Execution Zones:")
                zones = bot.signal_gen.get_top_zones(data, 5)
                for i, zone in enumerate(zones, 1):
                    print(f"  {i}. Price: {zone.price:.5f} | Score: {zone.score:.1f} | Type: {zone.zone_type}")
            
            bot.shutdown()
        else:
            print("\n❌ Bot initialization failed!")
            sys.exit(1)
    else:
        # Normal run
        bot.run()


if __name__ == "__main__":
    main()
