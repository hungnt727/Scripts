# Crypto VWAP Scripts

This project contains Python scripts for scanning and backtesting cryptocurrency trading strategies using VWAP, Ichimoku, and other indicators.

## Prerequisites

- Python 3.7+
- Recommended to use a virtual environment (venv)

## Installation

1.  Clone the repository or download the scripts.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Open the script files (e.g., `vwap_scanner.py`, `vwap_backtest.py`) and update the **CONFIGURATION** section with your details:

-   `COINMARKETCAP_API_KEY`: Get your API key from [CoinMarketCap Developer](https://coinmarketcap.com/api/).
-   `TELEGRAM_BOT_TOKEN`: Create a bot via [BotFather](https://t.me/BotFather) on Telegram to get a token.
-   `TELEGRAM_CHAT_ID`: The Chat ID where you want to receive alerts.

## Usage

### VWAP Scanner

Runs a continuous scanner to find valid trading setups based on the configured strategy.

```bash
python vwap_scanner.py
```

### VWAP Backtest

Backtests the strategy against historical data.

```bash
python vwap_backtest.py
```

### Bybit Funding Scanner

Monitors funding intervals on Bybit and alerts if they change/shorten.

```bash
python bybit_funding_scanner.py
```

## Strategy Overview

The main strategy combines:
-   **VWAP**: Price crosses and retests.
-   **Ichimoku Cloud**: Trend confirmation.
-   **RSI EMA**: Momentum filter.
-   **Volume**: Volume spike validation.


Create exe file:
-   **Run**: py -m PyInstaller --noconsole --onefile vwap_scanner.py

