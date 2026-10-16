import os
import time
import datetime
import ccxt
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def get_cache_path(symbol: str, timeframe: str) -> str:
    sanitized = symbol.replace("/", "_").replace(":", "_")
    return os.path.join(DATA_DIR, f"{sanitized}_{timeframe}.parquet")

def fetch_historical_ohlcv(symbol: str = "BTC/USDT", timeframe: str = "1h", days: int = 180) -> pd.DataFrame:
    """
    Descarga datos historicos de Binance con paginacion para superar el limite de 1000/1500 velas.
    """
    exchange = ccxt.binance({'enableRateLimit': True})
    
    # Calcular timestamp de inicio (milisegundos)
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_since = start_ms
    limit = 1000
    
    print(f"📥 Descargando {days} días de histórico para {symbol} [{timeframe}]...")
    
    while True:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            if not candles:
                break
                
            all_candles.extend(candles)
            last_timestamp = candles[-1][0]
            
            # Si la ultima vela descargada es muy cercana a la actual, hemos terminado
            if last_timestamp >= now_ms - 60000 or len(candles) < limit:
                break
                
            # Avanzar el timestamp para la siguiente pagina
            current_since = last_timestamp + 1
            time.sleep(exchange.rateLimit / 1000.0) # Respetar rate limits
        except Exception as e:
            print(f"⚠️ Error temporal al descargar: {e}. Reintentando...")
            time.sleep(2)
            continue
            
    if not all_candles:
        raise ValueError(f"No se pudieron obtener velas para {symbol} [{timeframe}]")
        
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    # Eliminar posibles duplicados en timestamps por paginacion
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.sort_values(by='timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # Convertir a datetime UTC
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    print(f"✅ Descarga completada: {len(df)} velas desde {df['datetime'].iloc[0]} hasta {df['datetime'].iloc[-1]}")
    return df

def load_dataset(symbol: str = "BTC/USDT", timeframe: str = "1h", days: int = 180, force_refresh: bool = False) -> pd.DataFrame:
    """
    Carga desde cache local en formato Parquet si existe, o descarga y guarda en cache.
    """
    ensure_data_dir()
    cache_file = get_cache_path(symbol, timeframe)
    
    if os.path.exists(cache_file) and not force_refresh:
        try:
            df = pd.read_parquet(cache_file)
            # Verificar si cubre al menos los dias solicitados
            span_days = (df['datetime'].iloc[-1] - df['datetime'].iloc[0]).days
            if span_days >= days * 0.9: # 90% de tolerancia
                print(f"⚡ Cargando {len(df)} velas desde cache local: {os.path.basename(cache_file)} ({span_days} días)")
                return df
            else:
                print(f"🔄 Cache local insuficiente ({span_days} días < {days} requeridos). Actualizando...")
        except Exception as e:
            print(f"⚠️ Error leyendo parquet ({e}), descargando de nuevo...")
            
    df = fetch_historical_ohlcv(symbol, timeframe, days=days)
    try:
        df.to_parquet(cache_file, index=False)
        print(f"💾 Guardado en cache: {cache_file}")
    except Exception as e:
        print(f"⚠️ No se pudo guardar parquet: {e}")
        
    return df
