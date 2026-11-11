import os
from data_manager import (
    ensure_data_dir,
    fetch_historical_funding,
    fetch_historical_ohlcv,
    get_cache_path as _root_get_cache_path,
    load_dataset as _root_load_dataset,
    load_funding_dataset as _root_load_funding_dataset,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def get_cache_path(symbol: str, timeframe: str) -> str:
    return _root_get_cache_path(symbol, timeframe, data_dir=DATA_DIR)


def load_dataset(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 180,
    force_refresh: bool = False,
):
    return _root_load_dataset(
        symbol=symbol,
        timeframe=timeframe,
        days=days,
        force_refresh=force_refresh,
        data_dir=DATA_DIR,
    )


def load_funding_dataset(
    symbol: str = "BTC/USDT",
    days: int = 1460,
    force_refresh: bool = False,
):
    return _root_load_funding_dataset(
        symbol=symbol,
        days=days,
        force_refresh=force_refresh,
        data_dir=DATA_DIR,
    )


__all__ = [
    "DATA_DIR",
    "ensure_data_dir",
    "get_cache_path",
    "fetch_historical_ohlcv",
    "fetch_historical_funding",
    "load_dataset",
    "load_funding_dataset",
]
