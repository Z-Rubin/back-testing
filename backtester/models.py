# Imports
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(slots=True)
class Candle:
    symbol: str
    timestamp: datetime # starting time of the candle UTC
    open: np.float64
    high: np.float64
    low: np.float64
    close: np.float64 | None = None
    volume: np.float64 | None = None

@dataclass(slots=True)
class Order:
    id: str
    symbol: str
    is_buy: bool
    price: float
    size: float


@dataclass(slots=True)
class Fill:
    order_id: str
    fill_id: str
    symbol: str
    is_buy: bool
    price: float
    size: float
    fee: float
    fee_currency: str
    timestamp: datetime