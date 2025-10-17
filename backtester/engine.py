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
            if hasattr(strategy, 'set_portfolio'):
                strategy.set_portfolio(self.portfolio)
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
                    symbol=symbol,
                    timestamp=pd.to_datetime(row['timestamp']),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row.get('volume', 0)
                )
                market_prices[symbol] = candle.close

                # Send candle to all strategies
                for strategy in self.strategies:
                    order = strategy.on_candle(candle, symbol)
                    if order:
                        fill = self.broker.submit_order(order, market_prices)
                        if fill:
                            strategy.on_fill(fill)

            if idx == num_steps - 1:
                # Close all positions at the end of backtest
                self._close_all_positions(market_prices)

            # Record portfolio snapshot
            self.portfolio.record_snapshot(
                timestamp=self.data[self.symbols[0]].iloc[idx]['timestamp'],
                market_prices=market_prices
            )

        # End-of-backtest hooks
        for strategy in self.strategies:
            if hasattr(strategy, 'on_end'):
                strategy.on_end()

    def _close_all_positions(self, market_prices: Dict[str, float]):
        """
        Close all open positions at the end of the backtest by creating
        market orders in the opposite direction.
        """
        from backtester.models import Order
        import uuid

        for symbol, position in self.portfolio.positions.items():
            if abs(position.size) > 1e-8:
                is_buy = position.size < 0
                size = abs(position.size)
                
                closing_order = Order(
                    id=f"CLOSE_{uuid.uuid4()}",
                    symbol=symbol,
                    is_buy=is_buy,
                    price=market_prices.get(symbol, position.avg_price),
                    size=size
                )
                
                fill = self.broker.submit_order(closing_order, market_prices)
                
                if fill:
                    for strategy in self.strategies:
                        if hasattr(strategy, 'on_fill'):
                            strategy.on_fill(fill)
            
            if abs(position.size) < 1e-8:
                position.size = 0.0
                position.avg_price = 0.0
