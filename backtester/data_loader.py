import pandas as pd
from typing import List, Dict

class DataLoader:
    def __init__(self, base_path: str = "../data"):
        self.base_path = base_path
        self.data: Dict[str, pd.DataFrame] = {}

    def load_symbol(self, symbol: str, file_type: str = "csv") -> pd.DataFrame:
        path = f"{self.base_path}/{symbol}.{file_type}"
        if file_type == "csv":
            df = pd.read_csv(path)
        elif file_type in ("parquet", "pq"):
            df = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Ensure standard columns
        df = df.rename(columns=lambda x: x.lower())
        required_cols = ["timestamp", "open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"{symbol} file missing required OHLCV columns: {required_cols}")

        # Sort and reset index
        df = df.sort_values("timestamp").reset_index(drop=True)
        self.data[symbol] = df
        return df

    def load_symbols(self, symbols: List[str], file_type: str = "csv") -> Dict[str, pd.DataFrame]:
        return {symbol: self.load_symbol(symbol, file_type) for symbol in symbols}

    def get_data(self, symbol: str) -> pd.DataFrame:
        if symbol not in self.data:
            raise KeyError(f"No data loaded for symbol {symbol}")
        return self.data[symbol]

    def align_timestamps(self) -> pd.DataFrame:
        dfs = []
        for symbol, df in self.data.items():
            temp = df[["timestamp", "close"]].rename(columns={"close": symbol})
            temp["timestamp"] = pd.to_datetime(temp["timestamp"])
            dfs.append(temp.set_index("timestamp"))

        combined = pd.concat(dfs, axis=1).sort_index()
        combined = combined.ffill().bfill()
        return combined
