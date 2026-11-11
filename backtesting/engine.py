from typing import Any, Dict, List, Optional
import pandas as pd

from core.indicators import calculate_volume_profile, detect_divergences
from core.strategy import (
    MIN_CONFIDENCE,
    calculate_confidence_score,
    check_td_signal,
    check_wyckoff_signal,
    compute_conviction_boost,
    compute_conviction_multiplier,
    compute_entry_levels,
    compute_weekly_context,
    evaluate_orthogonal_signal,
    get_base_risk,
    get_scaled_atr,
    load_fleet_params,
    normalize_symbol,
)

_SL_COOLDOWN_SECS = {
    "5m": 900,
    "15m": 2700,
    "1h": 10800,
    "4h": 43200,
    "1d": 259200,
    "1w": 1209600,
}

_TF_BAR_SECONDS = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}


class BacktestEngine:
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "4h",
        strategy: str = "HYB",
        initial_bank: float = 10000.0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0004,
        slippage_bps: float = 5.0,
        funding_rate_8h: float = 0.0001,
        max_leverage: float = 50.0,
        params: Optional[Dict[str, Any]] = None,
        fleet_file: str = "fleet_optimized.json",
    ):
        self.symbol = symbol
        self.clean_symbol = normalize_symbol(symbol)
        self.timeframe = timeframe
        self.strategy = strategy.upper()
        self.initial_bank = float(initial_bank)
        self.bank = float(initial_bank)
        self.maker_fee = float(maker_fee)
        self.taker_fee = float(taker_fee)
        self.slippage_rate = float(slippage_bps) / 10000.0
        self.funding_rate_8h = float(funding_rate_8h)
        self.max_leverage = float(max_leverage)

        loaded_params = load_fleet_params(
            symbol=self.clean_symbol,
            timeframe=self.timeframe,
            strategy=self.strategy,
            fleet_file=fleet_file,
        )
        loaded_params.setdefault("trailing_atr", 2.0)
        loaded_params.setdefault("min_confidence", MIN_CONFIDENCE)
        loaded_params.setdefault("enable_breakeven", True)
        loaded_params.setdefault("enable_dca_13", True)
        loaded_params.setdefault("enable_trailing", True)

        if params:
            loaded_params.update(params)
        self.params = loaded_params

        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.active_trade: Optional[Dict[str, Any]] = None
        self._last_sl_ts: Optional[float] = None
        self._next_trade_seq: int = 1

    def _apply_slippage(self, price: float, side: str) -> float:
        """Aplica slippage adverso segun direccion de la orden (BUY paga mas, SELL recibe menos)."""
        if side == "BUY":
            return price * (1.0 + self.slippage_rate)
        return price * (1.0 - self.slippage_rate)

    def _get_atr_multiplier(self) -> float:
        from core.strategy import get_atr_multiplier
        return get_atr_multiplier(self.timeframe)

    def _get_min_atr_pct(self) -> float:
        from core.strategy import get_min_atr_pct
        return get_min_atr_pct(self.timeframe)

    def _get_base_risk(self) -> float:
        return get_base_risk(self.clean_symbol, self.timeframe)

    def _calculate_confidence_score(
        self,
        candle,
        action: str,
        divergence: Optional[str],
        is_counter_trend: bool,
        fng_index: int = 50,
        funding_rate: float = 0.0,
        weekly_context: Optional[Dict[str, Any]] = None,
    ) -> float:
        return calculate_confidence_score(
            candle=candle,
            action=action,
            divergence=divergence,
            is_counter_trend=is_counter_trend,
            fng_index=fng_index,
            funding_rate=funding_rate,
            weekly_context=weekly_context,
        )

    def _get_weekly_context_at(self, weekly_df: Optional[pd.DataFrame], current_dt) -> Optional[Dict[str, Any]]:
        if weekly_df is None or weekly_df.empty or "datetime" not in weekly_df.columns:
            return None
        hist = weekly_df[weekly_df["datetime"] <= current_dt]
        if len(hist) < 5:
            return None
        return compute_weekly_context(hist)

    @staticmethod
    def precompute_bar_context(
        df: pd.DataFrame,
        weekly_df: Optional[pd.DataFrame] = None,
        start_idx: int = 30,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Precalcula Volume Profile, Divergencias RSI, avg_vol y contexto semanal 1W
        una sola vez por barra para acelerar Grid Search en ~40x.
        """
        ctx: Dict[int, Dict[str, Any]] = {}
        total_bars = len(df)
        has_weekly = weekly_df is not None and not weekly_df.empty and "datetime" in weekly_df.columns
        for i in range(start_idx, total_bars):
            closed_candle = df.iloc[i - 1]
            vp = calculate_volume_profile(df.iloc[max(0, i - 301) : i - 1], bins=20)
            div = detect_divergences(df.iloc[max(0, i - 31) : i], lookback=20)
            avg_vol = float(df["volume"].iloc[max(0, i - 21) : i - 1].mean())
            w_ctx = None
            if has_weekly:
                hist = weekly_df[weekly_df["datetime"] <= closed_candle["datetime"]]
                if len(hist) >= 5:
                    w_ctx = compute_weekly_context(hist)
            ctx[i] = {
                "vah": vp["vah"],
                "val": vp["val"],
                "divergence": div,
                "avg_vol": avg_vol,
                "weekly_ctx": w_ctx,
            }
        return ctx

    def run(
        self,
        df: pd.DataFrame,
        weekly_df: Optional[pd.DataFrame] = None,
        eval_start_idx: Optional[int] = None,
        precomputed_context: Optional[Dict[int, Dict[str, Any]]] = None,
        funding_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la simulacion barra por barra (Event-Driven) con paridad 1:1 con bot.py.
        Soporta funding_df historico real via merge_asof.
        """
        self.bank = self.initial_bank
        self.trades = []
        self.equity_curve = []
        self.active_trade = None
        self._last_sl_ts = None
        self._next_trade_seq = 1

        if funding_df is not None and not funding_df.empty and "datetime" in df.columns and "datetime" in funding_df.columns:
            work_df = pd.merge_asof(
                df.sort_values("datetime"),
                funding_df[["datetime", "fundingRate"]].sort_values("datetime"),
                on="datetime",
                direction="backward",
            )
            work_df["funding_rate"] = work_df["fundingRate"].fillna(self.funding_rate_8h)
        else:
            work_df = df
            if "funding_rate" not in work_df.columns:
                work_df = work_df.copy()
                work_df["funding_rate"] = self.funding_rate_8h

        total_bars = len(work_df)
        if eval_start_idx is not None:
            start_idx = max(30, int(eval_start_idx))
        elif total_bars > 250:
            start_idx = 200
        else:
            start_idx = min(50, max(25, total_bars // 4))

        if total_bars <= start_idx:
            return {
                "initial_bank": self.initial_bank,
                "final_bank": self.bank,
                "trades": [],
                "equity_curve": pd.DataFrame(),
            }

        for i in range(start_idx, total_bars):
            closed_candle = work_df.iloc[i - 1]
            live_candle = work_df.iloc[i]
            timestamp = live_candle["datetime"]
            close_p = float(live_candle["close"])

            bar_ctx = precomputed_context.get(i) if precomputed_context else None
            weekly_ctx = bar_ctx["weekly_ctx"] if bar_ctx else self._get_weekly_context_at(weekly_df, closed_candle["datetime"])

            # 1. Gestion de Trade Activo
            if self.active_trade is not None:
                self._manage_active_trade(live_candle, closed_candle, work_df, i, weekly_ctx)

            # 2. Gestion de Entrada (si estamos IDLE y aun hay capital)
            if self.active_trade is None and self.bank > 10.0:
                self._check_entry_signal(closed_candle, live_candle, work_df, i, weekly_ctx, bar_ctx=bar_ctx)

            # 3. Curva de equidad (mark-to-market)
            unrealized_pnl = 0.0
            if self.active_trade is not None:
                t = self.active_trade
                if t["action"] == "BUY":
                    unrealized_pnl = (close_p - t["entry_price"]) * t["size_units"]
                else:
                    unrealized_pnl = (t["entry_price"] - close_p) * t["size_units"]

            current_equity = max(0.0, self.bank + unrealized_pnl)
            self.equity_curve.append(
                {
                    "timestamp": timestamp,
                    "close": close_p,
                    "bank": self.bank,
                    "equity": current_equity,
                    "in_trade": 1 if self.active_trade is not None else 0,
                }
            )

        return {
            "initial_bank": self.initial_bank,
            "final_bank": self.bank,
            "trades": self.trades,
            "equity_curve": pd.DataFrame(self.equity_curve),
        }

    def _check_entry_signal(self, closed_candle, live_candle, df, i, weekly_ctx=None, bar_ctx=None):
        # Cooldown post-SL
        if self._last_sl_ts is not None:
            cooldown = _SL_COOLDOWN_SECS.get(self.timeframe, 43200)
            bar_ts = pd.Timestamp(live_candle["datetime"]).timestamp()
            if (bar_ts - self._last_sl_ts) < cooldown:
                return

        raw_open_price = float(live_candle["open"])
        signal_price = float(closed_candle["close"])
        ema200 = float(closed_candle["ema_200"])
        rsi = float(closed_candle["rsi"])
        raw_atr = float(closed_candle["atr"])

        if pd.isna(ema200) or pd.isna(rsi) or pd.isna(raw_atr) or raw_atr <= 0:
            return

        atr = get_scaled_atr(raw_atr, signal_price, self.timeframe)
        adx_val = float(closed_candle.get("adx", 0.0))
        funding_val = float(closed_candle.get("funding_rate", self.funding_rate_8h))

        # --- MODOS ORTOGONALES DE INVESTIGACION (CAPA 0 / CAPA 1 / CAPA 2) ---
        if self.strategy in ("TD9_L0", "TD9_MR", "MR", "TREND_DC", "TREND_EMA", "FUND_SQUEEZE", "REGIME_DUAL", "DUAL"):
            self._check_research_entry(closed_candle, live_candle, df, i, atr, adx_val, funding_val)
            return

        if bar_ctx is not None:
            vah = bar_ctx["vah"]
            val = bar_ctx["val"]
            divergence = bar_ctx["divergence"]
            avg_vol = bar_ctx["avg_vol"]
        else:
            df_vp_slice = df.iloc[max(0, i - 301) : i - 1]
            vp = calculate_volume_profile(df_vp_slice, bins=20)
            vah, val = vp["vah"], vp["val"]

            div_slice = df.iloc[max(0, i - 31) : i]
            divergence = detect_divergences(div_slice, lookback=20)

            avg_vol = float(df["volume"].iloc[max(0, i - 21) : i - 1].mean())
        candle_2_ago = df.iloc[i - 3]

        td_buy, td_sell = check_td_signal(closed_candle, candle_2_ago)
        wyckoff_spring, wyckoff_upthrust = check_wyckoff_signal(closed_candle, vah, val, avg_vol)

        trigger_buy = False
        trigger_sell = False
        reason = ""

        if self.strategy in ("TD9", "HYB"):
            if td_buy:
                trigger_buy = True
                reason = "TD9 Buy"
            elif td_sell:
                trigger_sell = True
                reason = "TD9 Sell"

        if self.strategy in ("WYK", "HYB"):
            if wyckoff_spring and not trigger_buy:
                trigger_buy = True
                reason = "Wyckoff Spring"
            elif wyckoff_upthrust and not trigger_sell:
                trigger_sell = True
                reason = "Wyckoff Upthrust"

        req_conf = 0.70 if self.clean_symbol == "HYPE" else float(self.params.get("min_confidence", MIN_CONFIDENCE))

        if trigger_buy and rsi < 70:
            is_counter = signal_price < ema200
            if is_counter and adx_val >= 32.0:
                return
            if self.timeframe == "4h" and is_counter and weekly_ctx:
                if weekly_ctx.get("is_sell_exhaustion_active") or (-8 <= weekly_ctx.get("td_count", 0) < 0):
                    return

            conf = self._calculate_confidence_score(
                closed_candle, "BUY", divergence, is_counter, funding_rate=funding_val, weekly_context=weekly_ctx
            )
            if conf >= req_conf:
                entry_price = self._apply_slippage(raw_open_price, "BUY")
                sl, tp, tag, _, _ = compute_entry_levels(
                    "BUY", reason, entry_price, atr, is_counter, self.params
                )
                full_reason = f"{reason} ({tag})" if "TD9" in reason else f"{reason} + RSI {rsi:.1f}"
                conviction = compute_conviction_multiplier("BUY", rsi)
                boost = compute_conviction_boost(self.clean_symbol, conf)
                final_risk = self._get_base_risk() * conviction * boost
                self._open_trade("BUY", entry_price, sl, tp, full_reason, live_candle["datetime"], final_risk, atr)

        elif trigger_sell and rsi > 30:
            is_counter = signal_price > ema200
            if is_counter and adx_val >= 32.0:
                return
            if self.timeframe == "4h" and is_counter and weekly_ctx:
                if weekly_ctx.get("is_buy_exhaustion_active") or (0 < weekly_ctx.get("td_count", 0) <= 8):
                    return

            conf = self._calculate_confidence_score(
                closed_candle, "SELL", divergence, is_counter, funding_rate=funding_val, weekly_context=weekly_ctx
            )
            if conf >= req_conf:
                entry_price = self._apply_slippage(raw_open_price, "SELL")
                sl, tp, tag, _, _ = compute_entry_levels(
                    "SELL", reason, entry_price, atr, is_counter, self.params
                )
                full_reason = f"{reason} ({tag})" if "TD9" in reason else f"{reason} + RSI {rsi:.1f}"
                conviction = compute_conviction_multiplier("SELL", rsi)
                boost = compute_conviction_boost(self.clean_symbol, conf)
                final_risk = self._get_base_risk() * conviction * boost
                self._open_trade("SELL", entry_price, sl, tp, full_reason, live_candle["datetime"], final_risk, atr)

    def _check_research_entry(self, closed_candle, live_candle, df, i, atr, adx_val, funding_val):
        raw_open_price = float(live_candle["open"])
        signal_price = float(closed_candle["close"])
        ema50 = float(closed_candle.get("ema_50", signal_price))
        ema200 = float(closed_candle["ema_200"])
        rsi = float(closed_candle["rsi"])
        risk_pct = float(self.params.get("risk_pct", self._get_base_risk()))
        sl_mult = float(self.params.get("atr_sl_trend", 2.0))
        tp_mult = float(self.params.get("atr_tp_trend", 3.0))

        action = None
        reason = self.strategy

        if self.strategy in ("TD9_L0", "TD9_MR"):
            td_buy, td_sell = check_td_signal(closed_candle, df.iloc[i - 3])
            if self.strategy == "TD9_MR":
                adx_max = float(self.params.get("adx_max", 24.0))
                if adx_val > adx_max:
                    return
                if self.params.get("require_funding_filter", False):
                    if td_buy and funding_val > 0.0002:
                        td_buy = False
                    if td_sell and funding_val < -0.0002:
                        td_sell = False
            if td_buy:
                action = "BUY"
            elif td_sell:
                action = "SELL"

        elif self.strategy == "TREND_DC":
            dc_period = int(self.params.get("dc_period", 20))
            high_col = f"dc_high_{dc_period}"
            low_col = f"dc_low_{dc_period}"
            dc_hi = float(closed_candle.get(high_col, float("nan")))
            dc_lo = float(closed_candle.get(low_col, float("nan")))
            if pd.isna(dc_hi) or pd.isna(dc_lo):
                return
            adx_min = float(self.params.get("adx_min", 0.0))
            if adx_val < adx_min:
                return
            use_ema = bool(self.params.get("use_ema200_filter", False))
            if signal_price > dc_hi and (not use_ema or signal_price > ema200):
                action = "BUY"
            elif signal_price < dc_lo and (not use_ema or signal_price < ema200):
                action = "SELL"

        elif self.strategy == "TREND_EMA":
            adx_min = float(self.params.get("adx_min", 22.0))
            if adx_val < adx_min:
                return
            prev_candle = df.iloc[i - 2]
            prev_close = float(prev_candle["close"])
            prev_ema50 = float(prev_candle.get("ema_50", prev_close))
            if signal_price > ema200 and ema50 > ema200 and prev_close <= prev_ema50 and signal_price > ema50:
                action = "BUY"
            elif signal_price < ema200 and ema50 < ema200 and prev_close >= prev_ema50 and signal_price < ema50:
                action = "SELL"

        elif self.strategy == "FUND_SQUEEZE":
            long_f = float(self.params.get("funding_long_max", -0.0002))
            short_f = float(self.params.get("funding_short_min", 0.0004))
            if funding_val <= long_f and rsi <= 42.0:
                action = "BUY"
            elif funding_val >= short_f and rsi >= 58.0:
                action = "SELL"

        elif self.strategy in ("MR", "DUAL", "REGIME_DUAL"):
            sig = evaluate_orthogonal_signal(
                self.strategy, closed_candle, df.iloc[i - 3], adx_val, ema200, self.params
            )
            if sig is None:
                return
            action = sig["action"]
            reason = f"{sig['mode']}:{sig['reason']}"
            sl_mult = sig["sl_mult"]
            tp_mult = sig["tp_mult"]

        if action is None:
            return

        entry_price = self._apply_slippage(raw_open_price, action)
        if action == "BUY":
            sl = entry_price - (atr * sl_mult)
            tp = entry_price + (atr * tp_mult)
        else:
            sl = entry_price + (atr * sl_mult)
            tp = entry_price - (atr * tp_mult)
        self._open_trade(action, entry_price, sl, tp, reason, live_candle["datetime"], risk_pct, atr)

    def _open_trade(
        self,
        action: str,
        price: float,
        sl: float,
        tp: float,
        reason: str,
        time_stamp,
        risk_pct: float,
        atr: float,
    ):
        # Invariante direccional estricta
        if action == "BUY" and not (sl < price < tp):
            raise AssertionError(f"Invariante BUY violada: sl={sl}, entry={price}, tp={tp}")
        if action == "SELL" and not (tp < price < sl):
            raise AssertionError(f"Invariante SELL violada: tp={tp}, entry={price}, sl={sl}")

        risk_amount = self.bank * risk_pct
        sl_dist = abs(price - sl)
        if sl_dist <= 0:
            sl_dist = price * 0.001

        units = risk_amount / sl_dist
        pos_usd = units * price
        if pos_usd < 10.0:
            return

        required_leverage = max(1.0, pos_usd / self.bank)
        if required_leverage > self.max_leverage:
            required_leverage = self.max_leverage
            pos_usd = self.bank * self.max_leverage
            units = pos_usd / price
            actual_risk = units * sl_dist
        else:
            actual_risk = risk_amount

        entry_fee = pos_usd * self.taker_fee
        self.bank -= entry_fee

        # Margen aislado efectivo (para verificar liquidacion realista)
        allocated_margin = pos_usd / required_leverage
        trade_id = self._next_trade_seq
        self._next_trade_seq += 1

        self.active_trade = {
            "id": trade_id,
            "action": action,
            "entry_time": time_stamp,
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "initial_sl": sl,
            "size_units": units,
            "size_usd": pos_usd,
            "risk_usd": actual_risk,
            "full_target_risk_usd": actual_risk,
            "leverage": required_leverage,
            "allocated_margin": allocated_margin,
            "reason": reason,
            "scaled_out": False,
            "reinforced_13": False,
            "breakeven_active": False,
            "runner_active": False,
            "atr_at_entry": atr,
            "entry_fee_remaining": entry_fee,
            "funding_paid": 0.0,
            "max_fav_excursion": 0.0,
            "max_adv_excursion": 0.0,
        }

    def _manage_active_trade(self, live_candle, closed_candle, df, i, weekly_ctx=None):
        t = self.active_trade
        action = t["action"]
        entry = t["entry_price"]
        sl = t["stop_loss"]
        tp = t["take_profit"]
        units = t["size_units"]
        atr = t["atr_at_entry"]

        high_p = float(live_candle["high"])
        low_p = float(live_candle["low"])
        time_stamp = live_candle["datetime"]

        # 0. Funding rate cada 8h proporcional a duracion de barra (real historico si existe)
        bar_funding = float(closed_candle.get("funding_rate", self.funding_rate_8h))
        if bar_funding != 0.0:
            bar_secs = _TF_BAR_SECONDS.get(self.timeframe, 14400)
            periods_8h = bar_secs / 28800.0
            notional = units * float(live_candle["close"])
            funding_cost = notional * bar_funding * periods_8h
            if action == "SELL":
                funding_cost = -funding_cost  # Shorts cobran funding positivo
            self.bank -= funding_cost
            t["funding_paid"] += funding_cost

        # Excursiones MFE / MAE
        if action == "BUY":
            fav = max(0.0, high_p - entry)
            adv = max(0.0, entry - low_p)
        else:
            fav = max(0.0, entry - low_p)
            adv = max(0.0, high_p - entry)
        t["max_fav_excursion"] = max(t.get("max_fav_excursion", 0.0), fav)
        t["max_adv_excursion"] = max(t.get("max_adv_excursion", 0.0), adv)

        # Chequeo de Liquidacion (Margen aislado con maintenance margin 0.5%)
        maint_margin = (units * entry) * 0.005
        max_loss_before_liq = max(0.0, t["allocated_margin"] - maint_margin)
        worst_unrealized_loss = adv * units
        if worst_unrealized_loss >= max_loss_before_liq and max_loss_before_liq > 0:
            liq_loss = -t["allocated_margin"]
            net_pnl = liq_loss - t["entry_fee_remaining"]
            self.bank = max(0.0, self.bank + liq_loss)
            self._last_sl_ts = pd.Timestamp(time_stamp).timestamp()
            self.trades.append(
                {
                    "id": f"{t['id']}_liq",
                    "parent_id": t["id"],
                    "action": action,
                    "type": "LIQUIDATION",
                    "entry_time": t["entry_time"],
                    "exit_time": time_stamp,
                    "entry_price": entry,
                    "exit_price": low_p if action == "BUY" else high_p,
                    "pnl": net_pnl,
                    "reason": "Liquidation",
                    "model": t["reason"],
                    "bank": self.bank,
                    "mfe_r": t["max_fav_excursion"] / atr if atr > 0 else 0.0,
                    "mae_r": t["max_adv_excursion"] / atr if atr > 0 else 0.0,
                    "realized_r": -max_loss_before_liq / (atr * units) if (atr > 0 and units > 0) else -1.0,
                }
            )
            self.active_trade = None
            return

        countdown = int(closed_candle["td_countdown"])

        is_regime_mr = "REGIME_MR" in t.get("reason", "")
        is_regime_trend = "REGIME_TREND" in t.get("reason", "")
        use_be = (not is_regime_mr) and (not is_regime_trend) and bool(self.params.get("enable_breakeven", True))
        use_so = (not is_regime_mr) and (not is_regime_trend) and bool(self.params.get("enable_scale_out", True))
        use_dca = (not is_regime_mr) and (not is_regime_trend) and bool(self.params.get("enable_dca_13", True))

        # 1. Refuerzo DCA "El Batallon" (TD 13) con tope de riesgo real
        if use_dca and not t["reinforced_13"]:
            if (action == "BUY" and countdown == -13) or (action == "SELL" and countdown == 13):
                self._execute_dca_13(float(live_candle["open"]), atr)
                entry = t["entry_price"]
                sl = t["stop_loss"]
                tp = t["take_profit"]
                units = t["size_units"]

        updated_sl = sl

        # 1b. Macro Weekly Shield (si hay weekly_context)
        if weekly_ctx and not is_regime_mr and not is_regime_trend:
            curr_close = float(live_candle["close"])
            if action == "BUY" and weekly_ctx.get("is_sell_exhaustion_active") and curr_close > entry and updated_sl < entry:
                updated_sl = entry
                t["breakeven_active"] = True
            elif action == "SELL" and weekly_ctx.get("is_buy_exhaustion_active") and curr_close < entry and updated_sl > entry:
                updated_sl = entry
                t["breakeven_active"] = True

        # 2. Breakeven Shield (>= 1.0 ATR)
        if use_be:
            be_mult = max(1.0, float(self.params.get("be_threshold_atr", 1.5)))
            be_dist = atr * be_mult
            if action == "BUY" and high_p >= (entry + be_dist):
                if updated_sl < entry:
                    updated_sl = entry
                    t["breakeven_active"] = True
            elif action == "SELL" and low_p <= (entry - be_dist):
                if updated_sl > entry:
                    updated_sl = entry
                    t["breakeven_active"] = True

        # 3. Scale-Out Parcial
        if use_so and not t["scaled_out"]:
            so_mult = float(self.params.get("scale_out_atr", 2.0))
            so_pct = float(self.params.get("scale_out_pct", 0.5))
            so_dist = atr * so_mult
            if (action == "BUY" and high_p >= entry + so_dist) or (action == "SELL" and low_p <= entry - so_dist):
                so_price = (entry + so_dist) if action == "BUY" else (entry - so_dist)
                so_units = units * so_pct

                gross_partial = ((so_price - entry) if action == "BUY" else (entry - so_price)) * so_units
                so_exit_fee = (so_price * so_units) * self.taker_fee
                alloc_entry_fee = t["entry_fee_remaining"] * so_pct
                t["entry_fee_remaining"] -= alloc_entry_fee

                # self.bank ya desconto la entry_fee en _open_trade; sumamos gross - exit_fee a bank
                # y registramos en trades el PnL neto incluyendo alloc_entry_fee para consistencia contable
                self.bank += (gross_partial - so_exit_fee)
                net_partial_pnl = gross_partial - so_exit_fee - alloc_entry_fee

                t["size_units"] -= so_units
                t["size_usd"] = t["size_units"] * entry
                t["scaled_out"] = True

                if action == "BUY" and updated_sl < entry:
                    updated_sl = entry
                elif action == "SELL" and updated_sl > entry:
                    updated_sl = entry

                self.trades.append(
                    {
                        "id": f"{t['id']}_partial",
                        "parent_id": t["id"],
                        "action": action,
                        "type": f"SCALE_OUT_{int(so_pct * 100)}%",
                        "entry_time": t["entry_time"],
                        "exit_time": time_stamp,
                        "entry_price": entry,
                        "exit_price": so_price,
                        "pnl": net_partial_pnl,
                        "reason": f"Scale-Out Tactico (+{so_mult:.1f} ATR)",
                        "bank": self.bank,
                        "mfe_r": t["max_fav_excursion"] / atr if atr > 0 else 0.0,
                        "mae_r": t["max_adv_excursion"] / atr if atr > 0 else 0.0,
                        "realized_r": ((so_price - entry) if action == "BUY" else (entry - so_price)) / atr if atr > 0 else 0.0,
                    }
                )
                units = t["size_units"]

        # 4. Trailing Stop (en REGIME_DUAL solo se activa en rama TREND, no en MR)
        use_trailing = (not is_regime_mr) and (is_regime_trend or bool(self.params.get("enable_trailing", True)))
        if use_trailing:
            c_closed = float(closed_candle["close"])
            trail_mult = 2.5 if t.get("runner_active") else (3.5 if is_regime_trend else float(self.params.get("trailing_atr", 2.0)))
            tr_dist = atr * trail_mult
            if action == "BUY":
                new_sl = c_closed - tr_dist
                if new_sl > updated_sl:
                    updated_sl = new_sl
            else:
                new_sl = c_closed + tr_dist
                if new_sl < updated_sl:
                    updated_sl = new_sl

        t["stop_loss"] = updated_sl

        # 5. Evaluacion conservadora SL vs Channel Exit vs TP
        closed = False
        exit_price = 0.0
        close_reason = ""
        enable_runner = (not is_regime_mr) and (not is_regime_trend) and bool(self.params.get("enable_runner", True))
        enable_ch_exit = (not is_regime_mr) and (is_regime_trend or bool(self.params.get("enable_channel_exit", False)))

        if action == "BUY":
            sl_hit = low_p <= updated_sl
            tp_hit = (tp is not None) and (high_p >= tp)
            dc_exit_lvl = closed_candle.get("dc_low_10", float("nan"))
            ch_exit = enable_ch_exit and not pd.isna(dc_exit_lvl) and float(closed_candle["close"]) < float(dc_exit_lvl)
            if sl_hit:
                closed = True
                exit_price = self._apply_slippage(updated_sl, "SELL")
                if t.get("runner_active"):
                    close_reason = "Runner Trailing Exit (+Macro Trend)"
                else:
                    close_reason = "Stop Loss" if updated_sl < entry else "Breakeven / Trailing SL"
            elif ch_exit:
                closed = True
                exit_price = self._apply_slippage(float(live_candle["open"]), "SELL")
                close_reason = "Donchian Channel Exit"
            elif not t.get("runner_active") and tp_hit:
                if not enable_runner:
                    closed = True
                    exit_price = tp
                    close_reason = "Take Profit"
                else:
                    tp2_units = units * 0.5
                    gross_tp2 = (tp - entry) * tp2_units
                    tp2_exit_fee = (tp * tp2_units) * self.taker_fee
                    alloc_entry_fee = t["entry_fee_remaining"] * 0.5
                    t["entry_fee_remaining"] -= alloc_entry_fee

                    self.bank += (gross_tp2 - tp2_exit_fee)
                    net_tp2_pnl = gross_tp2 - tp2_exit_fee - alloc_entry_fee

                    pct_label = "25%" if t.get("scaled_out") else "50%"
                    t["size_units"] -= tp2_units
                    t["size_usd"] = t["size_units"] * entry
                    t["runner_active"] = True

                    updated_sl = max(updated_sl, entry + (atr * 2.0))
                    t["take_profit"] = None
                    t["stop_loss"] = updated_sl

                    self.trades.append(
                        {
                            "id": f"{t['id']}_tp2",
                            "parent_id": t["id"],
                            "action": action,
                            "type": f"TAKE_PROFIT_{pct_label}",
                            "entry_time": t["entry_time"],
                            "exit_time": time_stamp,
                            "entry_price": entry,
                            "exit_price": tp,
                            "pnl": net_tp2_pnl,
                            "reason": "Take Profit Objetivo",
                            "bank": self.bank,
                            "mfe_r": t["max_fav_excursion"] / atr if atr > 0 else 0.0,
                            "mae_r": t["max_adv_excursion"] / atr if atr > 0 else 0.0,
                            "realized_r": (tp - entry) / atr if atr > 0 else 0.0,
                        }
                    )
                    units = t["size_units"]

        elif action == "SELL":
            sl_hit = high_p >= updated_sl
            tp_hit = (tp is not None) and (low_p <= tp)
            dc_exit_lvl = closed_candle.get("dc_high_10", float("nan"))
            ch_exit = enable_ch_exit and not pd.isna(dc_exit_lvl) and float(closed_candle["close"]) > float(dc_exit_lvl)
            if sl_hit:
                closed = True
                exit_price = self._apply_slippage(updated_sl, "BUY")
                if t.get("runner_active"):
                    close_reason = "Runner Trailing Exit (+Macro Trend)"
                else:
                    close_reason = "Stop Loss" if updated_sl > entry else "Breakeven / Trailing SL"
            elif ch_exit:
                closed = True
                exit_price = self._apply_slippage(float(live_candle["open"]), "BUY")
                close_reason = "Donchian Channel Exit"
            elif not t.get("runner_active") and tp_hit:
                if not enable_runner:
                    closed = True
                    exit_price = tp
                    close_reason = "Take Profit"
                else:
                    tp2_units = units * 0.5
                    gross_tp2 = (entry - tp) * tp2_units
                    tp2_exit_fee = (tp * tp2_units) * self.taker_fee
                    alloc_entry_fee = t["entry_fee_remaining"] * 0.5
                    t["entry_fee_remaining"] -= alloc_entry_fee

                    self.bank += (gross_tp2 - tp2_exit_fee)
                    net_tp2_pnl = gross_tp2 - tp2_exit_fee - alloc_entry_fee

                    pct_label = "25%" if t.get("scaled_out") else "50%"
                    t["size_units"] -= tp2_units
                    t["size_usd"] = t["size_units"] * entry
                    t["runner_active"] = True

                    updated_sl = min(updated_sl, entry - (atr * 2.0))
                    t["take_profit"] = None
                    t["stop_loss"] = updated_sl

                    self.trades.append(
                        {
                            "id": f"{t['id']}_tp2",
                            "parent_id": t["id"],
                            "action": action,
                            "type": f"TAKE_PROFIT_{pct_label}",
                            "entry_time": t["entry_time"],
                            "exit_time": time_stamp,
                            "entry_price": entry,
                            "exit_price": tp,
                            "pnl": net_tp2_pnl,
                            "reason": "Take Profit Objetivo",
                            "bank": self.bank,
                            "mfe_r": t["max_fav_excursion"] / atr if atr > 0 else 0.0,
                            "mae_r": t["max_adv_excursion"] / atr if atr > 0 else 0.0,
                            "realized_r": (entry - tp) / atr if atr > 0 else 0.0,
                        }
                    )
                    units = t["size_units"]

        if closed:
            gross_pnl = ((exit_price - entry) if action == "BUY" else (entry - exit_price)) * units
            exit_fee = (exit_price * units) * self.taker_fee
            self.bank += (gross_pnl - exit_fee)
            net_pnl = gross_pnl - exit_fee - t["entry_fee_remaining"] - t["funding_paid"]

            if close_reason == "Stop Loss":
                self._last_sl_ts = pd.Timestamp(time_stamp).timestamp()

            self.trades.append(
                {
                    "id": t["id"],
                    "parent_id": t["id"],
                    "action": action,
                    "type": "FULL_EXIT",
                    "entry_time": t["entry_time"],
                    "exit_time": time_stamp,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "pnl": net_pnl,
                    "reason": close_reason,
                    "model": t["reason"],
                    "bank": self.bank,
                    "mfe_r": t["max_fav_excursion"] / atr if atr > 0 else 0.0,
                    "mae_r": t["max_adv_excursion"] / atr if atr > 0 else 0.0,
                    "realized_r": ((exit_price - entry) if action == "BUY" else (entry - exit_price)) / atr if atr > 0 else 0.0,
                }
            )
            self.active_trade = None

    def _execute_dca_13(self, raw_price: float, atr: float):
        t = self.active_trade
        action = t["action"]
        price = self._apply_slippage(raw_price, action)

        # Tope estricto: el refuerzo TD-13 nunca excede el 50% del riesgo objetivo original
        full_target = t.get("full_target_risk_usd", t["risk_usd"])
        added_risk_usd = min(full_target * 0.50, self.bank * 0.03)
        if added_risk_usd <= 0:
            return

        if action == "BUY":
            new_sl = price - (atr * 2.0)
            new_tp_offset = atr * 2.5
        else:
            new_sl = price + (atr * 2.0)
            new_tp_offset = -(atr * 2.5)

        sl_pct = max(0.001, abs(price - new_sl) / price)
        added_usd = min(added_risk_usd / sl_pct, self.bank * min(10.0, self.max_leverage))
        added_units = added_usd / price

        old_units = t["size_units"]
        old_usd = t["size_usd"]
        new_units = old_units + added_units
        new_usd = old_usd + added_usd
        avg_entry = new_usd / new_units

        fee = added_usd * self.taker_fee
        self.bank -= fee
        t["entry_fee_remaining"] += fee
        t["allocated_margin"] += added_usd / max(1.0, t["leverage"])

        t["size_units"] = new_units
        t["size_usd"] = new_usd
        t["entry_price"] = avg_entry
        t["stop_loss"] = new_sl
        t["take_profit"] = avg_entry + new_tp_offset
        t["reinforced_13"] = True
