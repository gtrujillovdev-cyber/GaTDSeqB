import os
import time
import pandas as pd

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "backtesting", "data")

_TF_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


def ensure_data_dir(data_dir: str = DEFAULT_DATA_DIR):
    os.makedirs(data_dir, exist_ok=True)


def get_cache_path(symbol: str, timeframe: str, data_dir: str = DEFAULT_DATA_DIR) -> str:
    sanitized = symbol.replace("/", "_").replace(":", "_")
    return os.path.join(data_dir, f"{sanitized}_{timeframe}.parquet")


def fetch_historical_ohlcv(symbol: str = "BTC/USDT", timeframe: str = "1h", days: int = 180) -> pd.DataFrame:
    """
    Descarga datos historicos de Binance con paginacion para superar el limite de 1000/1500 velas.
    """
    import ccxt

    exchange = ccxt.binance({"enableRateLimit": True})
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days * 24 * 60 * 60 * 1000)

    all_candles = []
    current_since = start_ms
    limit = 1000

    print(f"📥 Descargando {days} días de histórico para {symbol} [{timeframe}]...")

    retries = 0
    while True:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            if not candles:
                break

            all_candles.extend(candles)
            last_timestamp = candles[-1][0]
            retries = 0

            if last_timestamp >= now_ms - 60000 or len(candles) < limit:
                break

            current_since = last_timestamp + 1
            time.sleep(exchange.rateLimit / 1000.0)
        except Exception as e:
            retries += 1
            if retries > 3:
                raise RuntimeError(f"Fallo descargando {symbol} [{timeframe}] tras 3 reintentos: {e}") from e
            print(f"⚠️ Error temporal al descargar: {e}. Reintentando ({retries}/3)...")
            time.sleep(2)

    if not all_candles:
        raise ValueError(f"No se pudieron obtener velas para {symbol} [{timeframe}]")

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.drop_duplicates(subset=["timestamp"], inplace=True)
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"✅ Descarga completada: {len(df)} velas desde {df['datetime'].iloc[0]} hasta {df['datetime'].iloc[-1]}")
    return df


def load_dataset(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 180,
    force_refresh: bool = False,
    data_dir: str = DEFAULT_DATA_DIR,
) -> pd.DataFrame:
    """
    Carga desde cache local Parquet si cubre el rango solicitado y no esta obsoleto.
    Si falla la red, cae de forma segura al cache local existente si esta disponible.
    """
    ensure_data_dir(data_dir)
    cache_file = get_cache_path(symbol, timeframe, data_dir=data_dir)
    cached_df = None

    if os.path.exists(cache_file):
        try:
            cached_df = pd.read_parquet(cache_file)
            if not cached_df.empty and "datetime" in cached_df.columns:
                span_days = (cached_df["datetime"].iloc[-1] - cached_df["datetime"].iloc[0]).total_seconds() / 86400.0
                last_ts = cached_df["datetime"].iloc[-1].timestamp()
                tf_sec = _TF_SECONDS.get(timeframe, 3600)
                max_staleness = max(86400, tf_sec * 2)
                is_fresh = (time.time() - last_ts) <= max_staleness

                if not force_refresh and span_days >= (days * 0.9) and is_fresh:
                    print(
                        f"⚡ Cargando {len(cached_df)} velas desde cache local: "
                        f"{os.path.basename(cache_file)} ({int(span_days)} días)"
                    )
                    return cached_df
        except Exception as e:
            print(f"⚠️ Error leyendo parquet ({e}), descargando de nuevo...")
            cached_df = None

    try:
        df = fetch_historical_ohlcv(symbol, timeframe, days=days)
        try:
            df.to_parquet(cache_file, index=False)
            print(f"💾 Guardado en cache: {cache_file}")
        except Exception as e:
            print(f"⚠️ No se pudo guardar parquet: {e}")
        return df
    except Exception as e:
        if cached_df is not None and not cached_df.empty:
            print(f"⚠️ Red no disponible ({e}). Usando cache local existente: {os.path.basename(cache_file)}")
            return cached_df
        raise
