import uuid
from datetime import datetime, timedelta
from backtester.models import Candle, Order
from backtester.strategy import StrategyBase


class ShortBreakoutStrategy(StrategyBase):
    """A short breakout strategy that shorts on upward breakouts and closes after hold time"""
    def __init__(self, symbol: str, breakout_threshold: float = 0.02, lookback_period_minutes: int = 30, hold_time_minutes: int = 60, position_size: float = 0.1):
        super().__init__()
        self.breakout_threshold = breakout_threshold
        self.lookback_period_minutes = lookback_period_minutes
        self.hold_time_minutes = hold_time_minutes
        self.symbol = symbol
        self.position_size = position_size  # Fraction of portfolio to use per trade
        self.candles_in_lookback_period = []
        self.open_positions = {}  # Track open positions with entry time
        self.current_position_size = 0.0  # Track current position

    def initialize(self, data):
        self.data = data
        print(f"ShortBreakoutStrategy initialized for {self.symbol}")
        print(f"  Breakout threshold: {self.breakout_threshold*100:.1f}%")
        print(f"  Lookback period: {self.lookback_period_minutes} minutes")
        print(f"  Hold time: {self.hold_time_minutes} minutes")
        print(f"  Position size: {self.position_size*100:.1f}% of portfolio")

    def on_candle(self, candle: Candle, symbol: str) -> Order:
        if symbol != self.symbol:
            return None
            
        # Update candles in lookback period
        self.candles_in_lookback_period.append(candle)
        cutoff_time = candle.timestamp - timedelta(minutes=self.lookback_period_minutes)
        self.candles_in_lookback_period = [c for c in self.candles_in_lookback_period 
                                         if c.timestamp >= cutoff_time]

        # Priority 1: Check if we should close existing position due to hold time
        if self.current_position_size < 0:  # We have a short position
            for position_id, entry_data in list(self.open_positions.items()):
                if (candle.timestamp - entry_data['timestamp']).total_seconds() / 60 >= self.hold_time_minutes:
                    # Close this position (return immediately to handle one order at a time)
                    close_order = Order(
                        id=str(uuid.uuid4()),
                        symbol=self.symbol,
                        is_buy=True,  # Buy to close short
                        price=candle.close,
                        size=abs(entry_data['size'])
                    )
                    self.current_position_size += entry_data['size']  # Remove from tracking
                    del self.open_positions[position_id]
                    print(f"Closing short position: BUY {close_order.size:.6f} at ${candle.close:.2f} (held for {(candle.timestamp - entry_data['timestamp']).total_seconds() / 60:.1f} min)")
                    return close_order

        # Priority 2: Check for new breakout condition - only if we don't have a large position
        if (len(self.candles_in_lookback_period) >= 2 and 
            abs(self.current_position_size) < self.position_size and
            len(self.open_positions) < 3):  # Limit number of concurrent positions
            
            # Calculate lookback period high (exclude current candle from lookback)
            lookback_high = max(c.high for c in self.candles_in_lookback_period[:-1])
            
            # Upward breakout - price breaks above recent high by threshold
            if candle.close > lookback_high * (1 + self.breakout_threshold):
                # Enter short position (bet that price will fall after breakout)
                trade_size = self.position_size / 5  # Conservative size per trade (1/5th of max position)
                position_id = str(uuid.uuid4())
                
                short_order = Order(
                    id=str(uuid.uuid4()),
                    symbol=self.symbol,
                    is_buy=False,  # Sell to open short
                    price=candle.close,
                    size=trade_size
                )
                
                # Track this position
                self.open_positions[position_id] = {
                    'size': -trade_size,  # Negative for short
                    'timestamp': candle.timestamp,
                    'entry_price': candle.close
                }
                self.current_position_size -= trade_size
                
                print(f"Breakout detected! SHORT {trade_size:.6f} at ${candle.close:.2f} (breakout: {((candle.close / lookback_high - 1) * 100):.2f}%)")
                return short_order

        return None

    def on_fill(self, fill):
        """Handle order fill notification"""
        action = "BOUGHT" if fill.is_buy else "SOLD"
        print(f"Fill: {action} {fill.size:.6f} {fill.symbol} at ${fill.price:.2f}, fee: ${fill.fee:.4f}")

    def on_end(self):
        """Called at the end of backtest"""
        total_positions = len(self.open_positions)
        if total_positions > 0:
            print(f"Strategy ended with {total_positions} open positions")
        else:
            print("Strategy ended with all positions closed")
        print(f"Final tracked position size: {self.current_position_size:.6f}")