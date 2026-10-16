import math
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from .indicators import calculate_volume_profile, detect_divergences

class BacktestEngine:
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        strategy: str = "HYB",
        initial_bank: float = 10000.0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0004,
        max_leverage: float = 50.0,
        params: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy = strategy.upper()
        self.initial_bank = initial_bank
        self.bank = initial_bank
        self.taker_fee = taker_fee
        self.max_leverage = max_leverage
        
        # Parametros configurables (con defaults calibrados)
        default_params = {
            "atr_sl_trend": 1.5,
            "atr_tp_trend": 2.5,
            "atr_sl_counter": 1.5,
            "atr_tp_counter": 2.0,
            "atr_sl_wyckoff": 1.5,
            "atr_tp_wyckoff": 2.0,
            "be_threshold_atr": 1.0,
            "scale_out_atr": 1.0,
            "scale_out_pct": 0.5,
            "trailing_atr": 2.0,
            "min_confidence": 0.55,
            "enable_scale_out": True,
            "enable_breakeven": True,
            "enable_dca_13": True,
            "enable_trailing": True,
            "enable_tp_extension": True
        }
        if params:
            default_params.update(params)
        self.params = default_params
        
        # Historial y estado
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.active_trade: Optional[Dict[str, Any]] = None

    def _get_atr_multiplier(self) -> float:
        if self.timeframe == '5m': return 2.0
        elif self.timeframe == '15m': return 1.8
        elif self.timeframe == '1h': return 1.5
        elif self.timeframe == '4h': return 1.2
        return 1.0 # 1d

    def _get_min_atr_pct(self) -> float:
        if self.timeframe == '1h': return 0.006
        elif self.timeframe == '4h': return 0.010
        return 0.015 # 1d

    def _get_base_risk(self) -> float:
        risk_matrix = {"1d": 0.15, "4h": 0.10, "1h": 0.05, "15m": 0.02, "5m": 0.01}
        return risk_matrix.get(self.timeframe, 0.05)

    def _calculate_confidence_score(self, candle, action, divergence, is_counter_trend) -> float:
        score = 0.0
        count = abs(candle.get('td_count', 0))
        if count >= 9: score += 0.30
        elif count >= 7: score += 0.15
        
        rsi = candle.get('rsi', 50.0)
        if action == "BUY":
            if divergence == 'BULLISH': score += 0.25
            elif rsi <= 30: score += 0.20
            elif rsi <= 40: score += 0.10
        else:
            if divergence == 'BEARISH': score += 0.25
            elif rsi >= 70: score += 0.20
            elif rsi >= 60: score += 0.10
            
        vol = candle.get('volume', 0.0)
        avg_vol = candle.get('volume_sma', vol)
        if avg_vol > 0:
            vol_ratio = vol / avg_vol
            if vol_ratio >= 1.5: score += 0.25
            elif vol_ratio >= 1.0: score += 0.15
            else: score += 0.05
            
        if not is_counter_trend:
            score += 0.20
        else:
            score += 0.05
            
        return round(score, 2)

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Ejecuta la simulacion barra por barra (Event-Driven)
        """
        self.bank = self.initial_bank
        self.trades = []
        self.equity_curve = []
        self.active_trade = None
        
        start_idx = max(200, 100) # Dejar margen para EMA200 y Volume Profile
        total_bars = len(df)
        
        for i in range(start_idx, total_bars):
            closed_candle = df.iloc[i-1] # Vela recien cerrada (confirmada)
            live_candle = df.iloc[i]     # Vela actual en ejecucion
            
            timestamp = live_candle['datetime']
            open_p = live_candle['open']
            high_p = live_candle['high']
            low_p = live_candle['low']
            close_p = live_candle['close']
            
            # 1. Gestion de Trade Activo
            if self.active_trade is not None:
                self._manage_active_trade(live_candle, closed_candle, df, i)
                
            # 2. Gestion de Entrada (si estamos IDLE)
            if self.active_trade is None:
                self._check_entry_signal(closed_candle, live_candle, df, i)
                
            # Registro de curva de equidad
            unrealized_pnl = 0.0
            if self.active_trade is not None:
                t = self.active_trade
                if t['action'] == "BUY":
                    unrealized_pnl = (close_p - t['entry_price']) * t['size_units']
                else:
                    unrealized_pnl = (t['entry_price'] - close_p) * t['size_units']
                    
            current_equity = self.bank + unrealized_pnl
            self.equity_curve.append({
                "timestamp": timestamp,
                "close": close_p,
                "bank": self.bank,
                "equity": current_equity,
                "in_trade": 1 if self.active_trade is not None else 0
            })
            
        return {
            "initial_bank": self.initial_bank,
            "final_bank": self.bank,
            "trades": self.trades,
            "equity_curve": pd.DataFrame(self.equity_curve)
        }

    def _check_entry_signal(self, closed_candle, live_candle, df, i):
        current_live_price = live_candle['open'] # Entramos al abrir la siguiente vela tras la señal
        signal_price = closed_candle['close']
        ema200 = closed_candle['ema_200']
        rsi = closed_candle['rsi']
        raw_atr = closed_candle['atr']
        
        if pd.isna(ema200) or pd.isna(rsi) or pd.isna(raw_atr) or raw_atr <= 0:
            return
            
        # ATR con multiplicador institucional y suelo
        atr = raw_atr * self._get_atr_multiplier()
        floor_atr = signal_price * self._get_min_atr_pct()
        atr = max(atr, floor_atr)
        
        count = closed_candle['td_count']
        
        # Wyckoff: calcular VP sobre slice previo de 100 velas
        df_vp_slice = df.iloc[max(0, i-101):i-1]
        vp = calculate_volume_profile(df_vp_slice, bins=20)
        vah = vp['vah']
        val = vp['val']
        
        div_slice = df.iloc[max(0, i-21):i-1]
        divergence = detect_divergences(div_slice, lookback=10)
        
        avg_vol = df['volume'].iloc[max(0, i-21):i-1].mean()
        volume = closed_candle['volume']
        climatic_volume = volume > (avg_vol * 1.5)
        
        candle_range = closed_candle['high'] - closed_candle['low']
        if candle_range <= 0: candle_range = 1.0
        close_pct = (closed_candle['close'] - closed_candle['low']) / candle_range
        
        wyckoff_spring = (closed_candle['low'] < val) and climatic_volume and (close_pct >= 0.5) and (divergence == 'BULLISH')
        wyckoff_upthrust = (closed_candle['high'] > vah) and climatic_volume and (close_pct <= 0.5) and (divergence == 'BEARISH')
        
        # Senales TD9 con confirmacion
        candle_2_ago = df.iloc[i-3]
        td_buy = (count <= -9) and (closed_candle['close'] > candle_2_ago['high'])
        td_sell = (count >= 9) and (closed_candle['close'] < candle_2_ago['low'])
        
        trigger_buy = False
        trigger_sell = False
        reason = ""
        
        if self.strategy in ["TD9", "HYB"]:
            if td_buy:
                trigger_buy = True
                reason = "TD9 Buy"
            elif td_sell:
                trigger_sell = True
                reason = "TD9 Sell"
                
        if self.strategy in ["WYK", "HYB"]:
            if wyckoff_spring and not trigger_buy:
                trigger_buy = True
                reason = "Wyckoff Spring"
            elif wyckoff_upthrust and not trigger_sell:
                trigger_sell = True
                reason = "Wyckoff Upthrust"
                
        if trigger_buy and rsi < 70:
            is_counter = signal_price < ema200
            conf = self._calculate_confidence_score(closed_candle, "BUY", divergence, is_counter)
            if conf >= self.params.get("min_confidence", 0.65):
                if "TD9" in reason:
                    if is_counter:
                        sl = current_live_price - (atr * self.params["atr_sl_counter"])
                        tp = current_live_price + (atr * self.params["atr_tp_counter"])
                        reason += " (Counter-Trend)"
                    else:
                        sl = current_live_price - (atr * self.params["atr_sl_trend"])
                        tp = current_live_price + (atr * self.params["atr_tp_trend"])
                        reason += " (Trend)"
                else:
                    sl = current_live_price - (atr * self.params["atr_sl_wyckoff"])
                    tp = current_live_price + (atr * self.params["atr_tp_wyckoff"])
                    reason += f" + RSI {rsi:.1f}"
                    
                conviction = 1.5 if rsi < 30 else 1.0
                final_risk = self._get_base_risk() * conviction
                self._open_trade("BUY", current_live_price, sl, tp, reason, live_candle['datetime'], final_risk, atr)
            
        elif trigger_sell and rsi > 30:
            is_counter = signal_price > ema200
            conf = self._calculate_confidence_score(closed_candle, "SELL", divergence, is_counter)
            if conf >= self.params.get("min_confidence", 0.65):
                if "TD9" in reason:
                    if is_counter:
                        sl = current_live_price + (atr * self.params["atr_sl_counter"])
                        tp = current_live_price - (atr * self.params["atr_tp_counter"])
                        reason += " (Counter-Trend)"
                    else:
                        sl = current_live_price + (atr * self.params["atr_sl_trend"])
                        tp = current_live_price - (atr * self.params["atr_tp_trend"])
                        reason += " (Trend)"
                else:
                    sl = current_live_price + (atr * self.params["atr_sl_wyckoff"])
                    tp = current_live_price - (atr * self.params["atr_tp_wyckoff"])
                    reason += f" + RSI {rsi:.1f}"
                    
                conviction = 1.5 if rsi > 70 else 1.0
                final_risk = self._get_base_risk() * conviction
                self._open_trade("SELL", current_live_price, sl, tp, reason, live_candle['datetime'], final_risk, atr)

    def _open_trade(self, action: str, price: float, sl: float, tp: float, reason: str, time_stamp, risk_pct: float, atr: float):
        risk_amount = self.bank * risk_pct
        sl_dist = abs(price - sl)
        if sl_dist <= 0: sl_dist = price * 0.001
        
        units = risk_amount / sl_dist
        pos_usd = units * price
        
        required_leverage = pos_usd / self.bank
        if required_leverage < 1.0: required_leverage = 1.0
        
        if required_leverage > self.max_leverage:
            required_leverage = self.max_leverage
            pos_usd = self.bank * self.max_leverage
            units = pos_usd / price
            actual_risk = units * sl_dist
        else:
            actual_risk = risk_amount
            
        # Deduct entry taker fee
        entry_fee = pos_usd * self.taker_fee
        self.bank -= entry_fee
        
        self.active_trade = {
            "id": len(self.trades) + 1,
            "action": action,
            "entry_time": time_stamp,
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "initial_sl": sl,
            "size_units": units,
            "size_usd": pos_usd,
            "risk_usd": actual_risk,
            "leverage": required_leverage,
            "reason": reason,
            "scaled_out": False,
            "reinforced_13": False,
            "breakeven_active": False,
            "atr_at_entry": atr,
            "entry_fee_total": entry_fee
        }

    def _manage_active_trade(self, live_candle, closed_candle, df, i):
        t = self.active_trade
        action = t['action']
        entry = t['entry_price']
        sl = t['stop_loss']
        tp = t['take_profit']
        units = t['size_units']
        atr = t['atr_at_entry']
        
        high_p = live_candle['high']
        low_p = live_candle['low']
        close_p = live_candle['close']
        time_stamp = live_candle['datetime']
        
        countdown = closed_candle['td_countdown']
        
        # 1. Refuerzo DCA "El Batallon" (TD 13)
        if self.params["enable_dca_13"] and not t['reinforced_13']:
            if (action == "BUY" and countdown == -13) or (action == "SELL" and countdown == 13):
                self._execute_dca_13(live_candle['open'], atr)
                entry = t['entry_price']
                sl = t['stop_loss']
                tp = t['take_profit']
                units = t['size_units']
                
        updated_sl = sl
        
        # 2. Breakeven Shield (+0.5 ATR)
        if self.params["enable_breakeven"]:
            be_dist = atr * self.params["be_threshold_atr"]
            if action == "BUY" and high_p >= (entry + be_dist):
                if updated_sl < entry:
                    updated_sl = entry
                    t['breakeven_active'] = True
            elif action == "SELL" and low_p <= (entry - be_dist):
                if updated_sl > entry:
                    updated_sl = entry
                    t['breakeven_active'] = True
                    
        # 3. Scale-Out Parcial (+1.0 ATR)
        if self.params["enable_scale_out"] and not t['scaled_out']:
            so_dist = atr * self.params["scale_out_atr"]
            if (action == "BUY" and high_p >= entry + so_dist) or (action == "SELL" and low_p <= entry - so_dist):
                so_price = (entry + so_dist) if action == "BUY" else (entry - so_dist)
                so_units = units * self.params["scale_out_pct"]
                
                # Calcular PnL parcial
                if action == "BUY":
                    pnl_partial = (so_price - entry) * so_units
                else:
                    pnl_partial = (entry - so_price) * so_units
                    
                so_fee = (so_price * so_units) * self.taker_fee
                net_partial_pnl = pnl_partial - so_fee
                self.bank += net_partial_pnl
                
                t['size_units'] -= so_units
                t['size_usd'] = t['size_units'] * entry
                t['scaled_out'] = True
                
                if action == "BUY" and updated_sl < entry:
                    updated_sl = entry
                elif action == "SELL" and updated_sl > entry:
                    updated_sl = entry
                    
                self.trades.append({
                    "id": f"{t['id']}_partial",
                    "action": action,
                    "type": "SCALE_OUT_50%",
                    "entry_time": t['entry_time'],
                    "exit_time": time_stamp,
                    "entry_price": entry,
                    "exit_price": so_price,
                    "pnl": net_partial_pnl,
                    "reason": "Scale-Out Táctico (+1.0 ATR)",
                    "bank": self.bank
                })
                units = t['size_units']
                
        # 4. Trailing Stop (+2.0 ATR sobre vela cerrada)
        # CORRECCION DEL BUG CRITICO DE BOT.PY:
        # Se debe comparar contra 'updated_sl', no contra el 'sl' inmutable inicial para no anular el Breakeven!
        if self.params["enable_trailing"]:
            c_closed = closed_candle['close']
            tr_dist = atr * self.params["trailing_atr"]
            if action == "BUY":
                new_sl = c_closed - tr_dist
                if new_sl > updated_sl:
                    updated_sl = new_sl
            else:
                new_sl = c_closed + tr_dist
                if new_sl < updated_sl:
                    updated_sl = new_sl
                    
        t['stop_loss'] = updated_sl
        
        # 5. Comprobacion de Cierre (Stop Loss vs Take Profit)
        # Evaluacion conservadora: Si ambos son impactados en la misma vela, asume SL primero
        closed = False
        exit_price = 0.0
        close_reason = ""
        
        if action == "BUY":
            sl_hit = low_p <= updated_sl
            tp_hit = high_p >= tp
            
            if sl_hit:
                closed = True
                exit_price = updated_sl
                close_reason = "Stop Loss" if updated_sl < entry else "Breakeven / Trailing SL"
            elif tp_hit:
                # Comprobar extension dinamica de TP
                rsi_now = live_candle['rsi']
                if self.params["enable_tp_extension"] and rsi_now >= 65:
                    # Let winners run
                    t['take_profit'] = tp + (atr * 2.5)
                    updated_sl = max(updated_sl, tp - (atr * 1.0))
                    t['stop_loss'] = updated_sl
                else:
                    closed = True
                    exit_price = tp
                    close_reason = "Take Profit"
                    
        elif action == "SELL":
            sl_hit = high_p >= updated_sl
            tp_hit = low_p <= tp
            
            if sl_hit:
                closed = True
                exit_price = updated_sl
                close_reason = "Stop Loss" if updated_sl > entry else "Breakeven / Trailing SL"
            elif tp_hit:
                rsi_now = live_candle['rsi']
                if self.params["enable_tp_extension"] and rsi_now <= 35:
                    t['take_profit'] = tp - (atr * 2.5)
                    updated_sl = min(updated_sl, tp + (atr * 1.0))
                    t['stop_loss'] = updated_sl
                else:
                    closed = True
                    exit_price = tp
                    close_reason = "Take Profit"
                    
        if closed:
            if action == "BUY":
                gross_pnl = (exit_price - entry) * units
            else:
                gross_pnl = (entry - exit_price) * units
                
            exit_fee = (exit_price * units) * self.taker_fee
            net_pnl = gross_pnl - exit_fee
            self.bank += net_pnl
            
            self.trades.append({
                "id": t['id'],
                "action": action,
                "type": "FULL_EXIT",
                "entry_time": t['entry_time'],
                "exit_time": time_stamp,
                "entry_price": entry,
                "exit_price": exit_price,
                "pnl": net_pnl,
                "reason": close_reason,
                "model": t['reason'],
                "bank": self.bank
            })
            self.active_trade = None

    def _execute_dca_13(self, price: float, atr: float):
        t = self.active_trade
        action = t['action']
        
        # Recuperar riesgo base y anadir el 65% ("El Batallon")
        full_target = t['risk_usd'] / 0.35
        added_risk_usd = full_target * 0.65
        
        if action == "BUY":
            new_sl = price - (atr * 2.0)
            new_tp_offset = atr * 2.5
        else:
            new_sl = price + (atr * 2.0)
            new_tp_offset = - (atr * 2.5)
            
        sl_pct = abs(price - new_sl) / price
        if sl_pct < 0.001: sl_pct = 0.001
        
        added_usd = added_risk_usd / sl_pct
        max_allowed = self.bank * self.max_leverage
        if added_usd > max_allowed: added_usd = max_allowed
        added_units = added_usd / price
        
        old_units = t['size_units']
        old_usd = t['size_usd']
        
        new_units = old_units + added_units
        new_usd = old_usd + added_usd
        avg_entry = new_usd / new_units
        
        # Deduct taker fee on DCA reinforcement
        fee = added_usd * self.taker_fee
        self.bank -= fee
        
        t['size_units'] = new_units
        t['size_usd'] = new_usd
        t['entry_price'] = avg_entry
        t['stop_loss'] = new_sl
        t['take_profit'] = avg_entry + new_tp_offset
        t['reinforced_13'] = True
