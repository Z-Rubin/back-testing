from typing import List, Dict
import random
from datetime import datetime

from backtester.models import Fill, Order

class Broker:
    def __init__(self, portfolio, fee_rate=0.001, slippage_pct=0.0):
        self.portfolio = portfolio
        self.fee_rate = fee_rate
        self.slippage_pct = slippage_pct
        self.fills: List[Fill] = []

    def submit_order(self, order: Order, market_prices: Dict[str, float]) -> Fill:
        if order is None:
            return None
        fill = self.execute_order(order, market_prices)
        if fill:
            self.fills.append(fill)
            self.portfolio.apply_fill(fill)
        return fill

    def execute_order(self, order: Order, market_prices: Dict[str, float]) -> Fill:
        symbol = order.symbol
        is_buy = order.is_buy
        size = order.size
        market_price = market_prices.get(symbol)

        if market_price is None:
            return None

        slippage_factor = 1 + (random.uniform(-self.slippage_pct, self.slippage_pct) if self.slippage_pct > 0 else 0)
        executed_price = market_price * slippage_factor

        fee = executed_price * size * self.fee_rate

        fill = Fill(
            order_id=order.id,
            fill_id=f"FILL_{datetime.utcnow().timestamp()}_{symbol}",
            symbol=symbol,
            timestamp=datetime.utcnow(),
            is_buy=is_buy,
            price=executed_price,
            size=size,
            fee=fee,
            fee_currency="USDT"
        )

        return fill

    def get_fills(self, symbol=None) -> List[Fill]:
        if symbol:
            return [f for f in self.fills if f.symbol == symbol]
        return self.fills
