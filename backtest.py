import ccxt
import pandas as pd
import sys

exchange = ccxt.binance()

def run_simulation(timeframe='1d', risk_percent=0.50):
    SYMBOL = 'BTC/USDT'
    LIMIT = 1000
    INITIAL_CAPITAL = 10000.0
    
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe, limit=LIMIT)
    except Exception as e:
        return {"error": str(e)}
        
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    capital = INITIAL_CAPITAL
    active_trade = None
    trades = []
    
    buy_count = 0
    sell_count = 0
    
    for i in range(4, len(df)):
        c = df['close'].iloc[i]
        c4 = df['close'].iloc[i-4]
        
        if c < c4: buy_count += 1
        else: buy_count = 0
        if c > c4: sell_count += 1
        else: sell_count = 0
            
        if active_trade is not None:
            if active_trade['type'] == 'buy':
                if df['low'].iloc[i] <= active_trade['sl']:
                    pnl = (active_trade['sl'] - active_trade['entry']) * active_trade['amount']
                    capital += pnl
                    trades.append({'type': 'BUY_SL', 'pnl': pnl, 'capital': capital})
                    active_trade = None
                elif df['high'].iloc[i] >= active_trade['tp']:
                    pnl = (active_trade['tp'] - active_trade['entry']) * active_trade['amount']
                    capital += pnl
                    trades.append({'type': 'BUY_TP', 'pnl': pnl, 'capital': capital})
                    active_trade = None
                    
            elif active_trade['type'] == 'sell':
                if df['high'].iloc[i] >= active_trade['sl']:
                    pnl = (active_trade['entry'] - active_trade['sl']) * active_trade['amount']
                    capital += pnl
                    trades.append({'type': 'SELL_SL', 'pnl': pnl, 'capital': capital})
                    active_trade = None
                elif df['low'].iloc[i] <= active_trade['tp']:
                    pnl = (active_trade['entry'] - active_trade['tp']) * active_trade['amount']
                    capital += pnl
                    trades.append({'type': 'SELL_TP', 'pnl': pnl, 'capital': capital})
                    active_trade = None
        
        if active_trade is None:
            if buy_count >= 9:
                perf = (df['low'].iloc[i] <= df['low'].iloc[i-2] and df['low'].iloc[i] <= df['low'].iloc[i-3]) or \
                       (df['low'].iloc[i-1] <= df['low'].iloc[i-2] and df['low'].iloc[i-1] <= df['low'].iloc[i-3])
                if perf and c > df['ema200'].iloc[i]: 
                    invest = capital * risk_percent
                    size = invest / c
                    ll = min(df['low'].iloc[i-8:i+1])
                    sl = ll * 0.999
                    tp = c + ((c - sl) * 1.5)
                    active_trade = {'type': 'buy', 'amount': size, 'entry': c, 'sl': sl, 'tp': tp}
                    
            elif sell_count >= 9:
                perf = (df['high'].iloc[i] >= df['high'].iloc[i-2] and df['high'].iloc[i] >= df['high'].iloc[i-3]) or \
                       (df['high'].iloc[i-1] >= df['high'].iloc[i-2] and df['high'].iloc[i-1] >= df['high'].iloc[i-3])
                if perf and c < df['ema200'].iloc[i]: 
                    invest = capital * risk_percent
                    size = invest / c
                    hh = max(df['high'].iloc[i-8:i+1])
                    sl = hh * 1.001
                    tp = c - ((sl - c) * 1.5)
                    active_trade = {'type': 'sell', 'amount': size, 'entry': c, 'sl': sl, 'tp': tp}

    wins = len([t for t in trades if 'TP' in t['type']])
    losses = len([t for t in trades if 'SL' in t['type']])
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0.0
    net_profit = capital - INITIAL_CAPITAL
    
    return {
        "success": True,
        "initial_capital": INITIAL_CAPITAL,
        "final_capital": capital,
        "net_profit": net_profit,
        "net_profit_pct": (net_profit/INITIAL_CAPITAL) * 100,
        "total_trades": total,
        "win_rate": win_rate
    }

if __name__ == '__main__':
    from termcolor import colored
    tf = sys.argv[1] if len(sys.argv) > 1 else '1h'
    if "1d" in tf or "1w" in tf: risk = 0.50
    elif "4h" in tf: risk = 0.25
    else: risk = 0.10
    
    res = run_simulation(tf, risk)
    if "error" in res:
        print("Error:", res["error"])
        sys.exit(1)
        
    print("\n" + "="*40)
    print(f"📊 RESULTADOS DEL BACKTEST ({tf})")
    print("="*40)
    print(f"Capital Inicial: ${res['initial_capital']}")
    print(colored(f"Capital Final:   ${res['final_capital']:.2f}", 'green' if res['net_profit']>0 else 'red'))
    print(colored(f"Beneficio Neto:  ${res['net_profit']:.2f} ({res['net_profit_pct']:.2f}%)", 'green' if res['net_profit']>0 else 'red'))
    print(f"Total Trades:    {res['total_trades']}")
    print(f"Win Rate:        {res['win_rate']:.1f}%")
    print("="*40)
