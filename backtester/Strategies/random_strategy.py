import numpy as np
from backtester.strategy import StrategyBase
from backtester.models import Candle, Order
import uuid


class RandomStrategy(StrategyBase):
    def __init__(self, symbol: str, seed: int = 42, trade_probability: float = 0.05, max_position_size: float = 0.1):
        """
        Random trading strategy that makes random buy/sell decisions.
        
        Args:
            symbol: The trading symbol
            seed: Random seed for reproducibility
            trade_probability: Probability of making a trade on each candle (0.0 to 1.0)
            max_position_size: Maximum position size as fraction of portfolio value
        """
        super().__init__()
        self.symbol = symbol
        self.rng = np.random.default_rng(seed)
        self.trade_probability = trade_probability
        self.max_position_size = max_position_size
        self.symbols = []
        self.data = {}
        
    def initialize(self, data):
        """Initialize the strategy with historical data"""
        self.data = data
        print(f"RandomStrategy initialized for {self.symbol}")
        
    def on_candle(self, candle: Candle, symbol: str) -> Order:
        """
        Generate random trading signals.
        
        Args:
            candle: Current price candle
            symbol: Trading symbol
            
        Returns:
            Order object if trade is generated, None otherwise
        """
        if symbol != self.symbol:
            return None
            
        # Random decision to trade or not
        if self.rng.random() > self.trade_probability:
            return None
            
        # Random decision to buy or sell
        is_buy = self.rng.random() > 0.5
        
        # Random position size (between 1% and max_position_size of available cash/position)
        min_size = 0.01  # 1% minimum
        size_factor = self.rng.uniform(min_size, self.max_position_size)
        
        # For simplicity, assume we have access to some portfolio value
        # In a real implementation, this would come from the portfolio
        base_trade_size = 1000  # Base trade size in quote currency
        trade_size = base_trade_size * size_factor
        
        # Calculate quantity based on current price
        quantity = trade_size / candle.close
        
        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            is_buy=is_buy,
            price=candle.close,  # Market order at current close price
            size=quantity
        )
        
        action = "BUY" if is_buy else "SELL"
        print(f"{action} {quantity:.6f} {symbol} at {candle.close:.2f}")
        
        return order
        
    def on_fill(self, fill):
        """Handle order fill notification"""
        action = "BOUGHT" if fill.is_buy else "SOLD"
        print(f"Fill: {action} {fill.size:.6f} {fill.symbol} at {fill.price:.2f}, fee: {fill.fee:.4f}")
        
    def on_end(self):
        """Called at the end of backtest"""
        print(f"RandomStrategy backtest completed for {self.symbol}")
