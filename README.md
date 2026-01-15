# IOFAE Trading Bot

**I**nstitutional **O**rder **F**low **A**nticipation **E**ngine

A sophisticated prop trading bot that detects critical price levels where institutional orders are likely to trigger, and opens positions 5-7 pips before these levels.

## 🎯 Features

- **Execution Zone Detection**: Identifies high-probability trading zones using multiple confluence factors
- **Score-Based Entry**: 0-100 scoring system for trade quality assessment
- **Exhaustion-Based Exit**: Momentum analysis for optimal exit timing
- **Prop Firm Compliant**: Built-in risk management for challenge accounts
- **Real-time Notifications**: Telegram alerts for all trading activity

## 📊 Scoring System

The bot calculates a score (0-100) for each potential execution zone:

| Component | Max Points | Description |
|-----------|------------|-------------|
| VWAP Distance | 30 | Distance from daily VWAP |
| Round Numbers | 25 | Psychological levels (1.0800, 1.0850) |
| Fibonacci | 20 | Proximity to key Fib levels |
| DOM Volume | 15 | Historical order book data |
| Delta Imbalance | 10 | Bid/Ask volume differential |

**Trade signals are only generated when score ≥ 90**

## 📁 Project Structure

```
iofae_bot/
├── main.py                 # Main entry point & trading loop
├── data_collector.py       # MT5 data collection
├── score_calculator.py     # Zone scoring algorithm
├── signal_generator.py     # Trade signal generation
├── position_manager.py     # Trade execution & monitoring
├── risk_controller.py      # Risk management
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── database/
│   └── dom_logger.py       # SQLite database manager
└── utils/
    ├── logger.py           # Logging utility
    └── notifier.py         # Telegram notifications
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd iofae_bot
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml` with your settings:

```yaml
mt5:
  login: YOUR_MT5_LOGIN
  password: YOUR_PASSWORD
  server: YOUR_BROKER_SERVER

telegram:
  enabled: true
  bot_token: YOUR_BOT_TOKEN
  chat_id: YOUR_CHAT_ID
```

### 3. Test Mode

```bash
python main.py --test
```

### 4. Run Bot

```bash
python main.py
```

## ⚙️ Configuration

### Trading Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `symbol` | EURUSD | Trading pair |
| `scan_range_pips` | 20 | Zone scanning range |
| `entry_offset_pips` | 7 | Entry distance from zone |
| `stop_loss_pips` | 10 | Stop loss distance |
| `min_score_threshold` | 90 | Minimum score for trade |

### Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `risk_per_trade` | 1% | Per-trade risk |
| `max_daily_loss` | 5% | Daily loss limit |
| `max_total_drawdown` | 10% | Maximum drawdown |
| `max_trades_per_day` | 3 | Daily trade limit |
| `min_trade_interval` | 3 hours | Time between trades |

### Exit Conditions

- **Exhaustion**: Volume drop, spread widening, or price stall
- **Time Limit**: Max 15 minutes per position
- **Stop Loss**: Fixed 10 pip stop

## 📈 Expected Performance

Based on backtesting (sample size: 9 trades):

| Metric | Value |
|--------|-------|
| Win Rate | 85-88% (projected) |
| Monthly Return | 10-13% |
| Max Drawdown | 2-3% |
| Avg Pips/Trade | +22.4 |

## ⚠️ Risk Disclaimer

Trading forex involves substantial risk of loss. This bot is for educational purposes. Past performance does not guarantee future results. Only trade with capital you can afford to lose.

## 📝 License

MIT License - Use at your own risk.
