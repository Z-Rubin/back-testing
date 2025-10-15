from typing import List, Dict
import pandas as pd

from backtester.broker import Broker
from backtester.models import Candle
from backtester.portfolio import Portfolio
from backtester.strategy import StrategyBase

class BacktesterEngine:
    """
    Orchestrates strategies, broker, and portfolio over historical data.
    Supports multiple strategies and multiple symbols.
    """

    def __init__(self, strategies: List[StrategyBase], symbols: List[str], broker: Broker, portfolio: Portfolio):
        self.strategies = strategies
        self.symbols = symbols
        self.broker = broker
        self.portfolio = portfolio
        self.data: Dict[str, pd.DataFrame] = {}  # symbol -> historical OHLCV
        self.current_index = 0

    def load_data(self, symbol: str, df: pd.DataFrame):
        """
        df must have columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        self.data[symbol] = df.sort_values("timestamp").reset_index(drop=True)

    def initialize(self):
        for strategy in self.strategies:
            strategy.symbols = self.symbols
            strategy.initialize(self.data)

    def run_backtest(self):
        """
        Step through all timestamps sequentially, sending candles to strategies.
        """
        # Assume all symbols have the same number of rows and aligned timestamps
        num_steps = min(len(df) for df in self.data.values())

        for idx in range(num_steps):
            self.current_index = idx
            market_prices = {}

            # Build current candle dict per symbol
            for symbol in self.symbols:
                row = self.data[symbol].iloc[idx]
                candle = Candle(
                    timestamp=row['timestamp'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                )
                market_prices[symbol] = candle.close

                # Send candle to all strategies
                for strategy in self.strategies:
                    order = strategy.on_candle(candle, symbol)
                    self.broker.submit_order(order, market_prices)

            # Record portfolio snapshot
            self.portfolio.record_snapshot(
                timestamp=self.data[self.symbols[0]].iloc[idx]['timestamp'],
                market_prices=market_prices
            )

        # End-of-backtest hooks
        for strategy in self.strategies:
            strategy.on_end()
