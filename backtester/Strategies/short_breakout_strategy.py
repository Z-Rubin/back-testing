import uuid
from datetime import datetime, timedelta
from backtester.models import Candle, Order
from backtester.portfolio import Portfolio
from backtester.strategy import StrategyBase


class ShortBreakoutStrategy(StrategyBase):
    """A short breakout strategy that shorts on upward breakouts and closes after hold time"""
    def __init__(self, symbol: str, breakout_threshold: float = 0.02, lookback_period_minutes: int = 30, hold_time_minutes: int = 60, portfolio_percentage: float = 10.0, stop_loss_percentage: float = 10.0):
        super().__init__()
        self.breakout_threshold = breakout_threshold
        self.lookback_period_minutes = lookback_period_minutes
        self.hold_time_minutes = hold_time_minutes
        self.symbol = symbol
        self.portfolio_percentage = portfolio_percentage  # Percentage of portfolio to use for total position (e.g., 10.0 for 10%)
        self.stop_loss_percentage = stop_loss_percentage  # Stop loss as percentage of position (e.g., 10.0 for 10% loss)
        self.position_size = portfolio_percentage / 100.0  # Convert to fraction for internal use
        self.candles_in_lookback_period = []
        self.open_positions = {}  # Track open positions with entry time
        self.portfolio: Portfolio = None  # Will be set by the engine

    def initialize(self, data):
        self.data = data
        print(f"ShortBreakoutStrategy initialized for {self.symbol}")
        print(f"  Breakout threshold: {self.breakout_threshold*100:.1f}%")
        print(f"  Lookback period: {self.lookback_period_minutes} minutes")
        print(f"  Hold time: {self.hold_time_minutes} minutes")
        print(f"  Portfolio percentage: {self.portfolio_percentage:.1f}% of total portfolio")
        print(f"  Stop loss: {self.stop_loss_percentage:.1f}% of position")

    def set_portfolio(self, portfolio):
        """Set the portfolio reference so strategy can query current positions"""
        self.portfolio = portfolio
        
    def get_trade_size(self, current_price: float) -> float:
        """Calculate trade size based on portfolio percentage and current equity"""
        if not self.portfolio:
            return self.position_size  # Fallback to fraction if no portfolio reference
        
        # Create market prices dict with current price for this symbol
        market_prices = {self.symbol: current_price}
        current_equity = self.portfolio.equity(market_prices)
        target_dollar_amount = current_equity * (self.portfolio_percentage / 100.0)
        trade_size = target_dollar_amount / current_price
        return trade_size
    
    def get_current_position_size(self):
        """Get current position size from portfolio"""
        if self.portfolio:
            return self.portfolio.get_position(self.symbol).size
        return 0.0

    def on_candle(self, candle: Candle, symbol: str) -> Order:
        if symbol != self.symbol:
            return None
            
        # Update candles in lookback period
        self.candles_in_lookback_period.append(candle)
        cutoff_time = candle.timestamp - timedelta(minutes=self.lookback_period_minutes)
        self.candles_in_lookback_period = [c for c in self.candles_in_lookback_period 
                                         if c.timestamp >= cutoff_time]

        current_position = self.get_current_position_size()
        
        # Priority 1: Check stop-loss condition (highest priority)
        if current_position < 0:  # We have a short position
            for position_id, entry_data in list(self.open_positions.items()):
                entry_price = entry_data['entry_price']
                # For shorts, loss occurs when price goes UP from entry
                # Stop loss triggers when price is above entry by stop_loss_percentage
                stop_loss_price = entry_price * (1 + self.stop_loss_percentage / 100.0)
                
                if candle.close >= stop_loss_price:
                    # Close position due to stop loss
                    close_order = Order(
                        id=str(uuid.uuid4()),
                        symbol=self.symbol,
                        is_buy=True,  # Buy to close short
                        price=candle.close,
                        size=abs(current_position)
                    )
                    entry_data['closing_order_id'] = close_order.id
                    loss_pct = ((candle.close / entry_price - 1) * 100)
                    print(f"STOP LOSS triggered! Submitting close order: BUY {close_order.size:.6f} at ${candle.close:.2f} (loss: {loss_pct:.2f}%)")
                    return close_order

        # Priority 2: Check if we should close existing position due to hold time
        if current_position < 0:  # We have a short position
            for position_id, entry_data in list(self.open_positions.items()):
                if (candle.timestamp - entry_data['timestamp']).total_seconds() / 60 >= self.hold_time_minutes:
                    # Close this position (return immediately to handle one order at a time)
                    close_order = Order(
                        id=str(uuid.uuid4()),
                        symbol=self.symbol,
                        is_buy=True,  # Buy to close short
                        price=candle.close,
                        size=abs(current_position)  # Close the actual portfolio position
                    )
                    # Mark position for closing
                    entry_data['closing_order_id'] = close_order.id
                    print(f"Submitting close order: BUY {close_order.size:.6f} at ${candle.close:.2f} (held for {(candle.timestamp - entry_data['timestamp']).total_seconds() / 60:.1f} min)")
                    return close_order

        # Priority 3: Check for new breakout condition - only if we have NO open position
        if (len(self.candles_in_lookback_period) >= 2 and 
            abs(current_position) < 1e-8 and  # Effectively no position (changed from checking against max_position_size)
            len(self.open_positions) == 0):  # No tracked positions (changed from < 3 to == 0)
            
            # Calculate lookback period high (exclude current candle from lookback)
            lookback_high = max(c.high for c in self.candles_in_lookback_period[:-1])
            
            # Upward breakout - price breaks above recent high by threshold
            if candle.close > lookback_high * (1 + self.breakout_threshold):
                # Enter short position (bet that price will fall after breakout)
                trade_size = self.get_trade_size(candle.close)
                position_id = str(uuid.uuid4())
                
                short_order = Order(
                    id=str(uuid.uuid4()),
                    symbol=self.symbol,
                    is_buy=False,  # Sell to open short
                    price=candle.close,
                    size=trade_size
                )
                
                # Track this position for time-based closing
                self.open_positions[position_id] = {
                    'timestamp': candle.timestamp,
                    'entry_price': candle.close,
                    'order_id': short_order.id
                }
                
                print(f"Breakout detected! Submitting SHORT order for {trade_size:.6f} at ${candle.close:.2f} (breakout: {((candle.close / lookback_high - 1) * 100):.2f}%)")
                return short_order

        return None

    def on_fill(self, fill):
        """Handle order fill notification"""
        action = "BOUGHT" if fill.is_buy else "SOLD"
        print(f"Fill: {action} {fill.size:.6f} {fill.symbol} at ${fill.price:.2f}, fee: ${fill.fee:.4f}")
        
        # Update position tracking for time-based closes
        for position_id, entry_data in list(self.open_positions.items()):
            # Check if this is an opening order
            if entry_data.get('order_id') == fill.order_id:
                entry_data['entry_price'] = fill.price  # Use actual fill price
                break
            # Check if this is a closing order
            elif entry_data.get('closing_order_id') == fill.order_id:
                print(f"Closed position: filled {fill.size:.6f} at ${fill.price:.2f}")
                del self.open_positions[position_id]
                break

    def on_end(self):
        """Called at the end of backtest"""
        total_positions = len(self.open_positions)
        if total_positions > 0:
            print(f"Strategy ended with {total_positions} open time-tracked positions")
        else:
            print("Strategy ended with all time-tracked positions closed")
        
        final_position = self.get_current_position_size()
        if abs(final_position) < 1e-8:  # Close to zero (accounting for floating point precision)
            print(f"Portfolio position: {final_position:.6f} (effectively closed)")
        else:
            print(f"Portfolio position: {final_position:.6f} (will be closed by engine)")