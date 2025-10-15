from backtester.models import Candle, Fill, Order


class StrategyBase:
    def __init__(self):
        pass
    def initialize(self):
        pass
    def on_candle(self, candle: Candle) -> list[Order]:
        # Implement strategy logic here
        pass
    def on_fill(self, fill: Fill):
        pass