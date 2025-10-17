from dataclasses import dataclass, field
from typing import Dict, List
from decimal import Decimal

from backtester.models import Fill

@dataclass
class Position:
    symbol: str
    size: float = 0.0             # positive for long, negative for short
    avg_price: float = 0.0        # average entry price
    realized_pnl: float = 0.0     # total realized PnL from this position

@dataclass
class PortfolioSnapshot:
    timestamp: any
    cash: float
    equity: float
    positions: Dict[str, Position]

class Portfolio:
    def __init__(self, initial_cash: float = 100_000.0):
        self.cash: float = initial_cash
        self.positions: Dict[str, Position] = {}   # keyed by symbol
        self.history: List[PortfolioSnapshot] = []

    def apply_fill(self, fill: Fill):
        symbol = fill.symbol
        is_buy = fill.is_buy
        size = fill.size
        price = fill.price
        fee = fill.fee

        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)

        pos = self.positions[symbol]

        signed_size = size if is_buy else -size
        original_signed_size = signed_size  # Store original for cash calculation

        if pos.size * signed_size < 0:
            closed_size = min(abs(pos.size), abs(signed_size))
            pnl = closed_size * (price - pos.avg_price) * (1 if pos.size > 0 else -1)
            pos.realized_pnl += pnl
            
            if pos.size > 0:
                pos.size -= closed_size  # Close long position
            else:
                pos.size += closed_size  # Close short position
            
            if signed_size > 0:
                signed_size -= closed_size
            else:
                signed_size += closed_size
            
            if abs(pos.size) < 1e-10:
                pos.size = 0.0
                pos.avg_price = 0.0

        # If there's still trade size remaining after closing, open new position
        if abs(signed_size) > 1e-10:
            if pos.size == 0:
                pos.size = signed_size
                pos.avg_price = price
            else:
                total_cost = pos.avg_price * abs(pos.size) + price * abs(signed_size)
                pos.size += signed_size
                if pos.size != 0:
                    pos.avg_price = total_cost / abs(pos.size)
                else:
                    pos.avg_price = 0.0

        # Handle floating-point precision issues - if position is very small, set to zero
        if abs(pos.size) < 1e-10:
            pos.size = 0.0
            pos.avg_price = 0.0

        # Use original signed_size for cash calculation, not the modified version
        cash_change = -original_signed_size * price - fee
        self.cash += cash_change


    def equity(self, market_prices: Dict[str, float]) -> float:
        eq = self.cash
        for symbol, pos in self.positions.items():
            eq += pos.size * market_prices.get(symbol, pos.avg_price)
        return eq


    def record_snapshot(self, timestamp, market_prices: Dict[str, float]):
        snap = PortfolioSnapshot(
            timestamp=timestamp,
            cash=self.cash,
            equity=self.equity(market_prices),
            positions={s: Position(**vars(p)) for s, p in self.positions.items()}
        )
        self.history.append(snap)


    def get_position(self, symbol):
        return self.positions.get(symbol, Position(symbol))
