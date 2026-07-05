#!/usr/bin/env python3
"""
Strategy comparison on REAL XAUUSD 15m — fair test with risk control.

Two candidates vs the original (which blew up):
  A) MeanRev+SL   : same mean-reversion entry, BUT single unit + hard stop-loss,
                    exit at SMA touch (TP) or SL, whichever first. Fixes the
                    "-100% no-stop" failure of the original.
  B) EMA-Pullback : trend-following. Trade WITH the EMA50/EMA200 trend, enter on
                    a pullback to EMA50, fixed SL + R-multiple TP. Lower win rate
                    by design, but positive expectancy from big winners.

Anti look-ahead: all signals from the PREVIOUS closed bar (shift), entries fill at
NEXT bar open. Intrabar SL/TP: if both hit in one bar, SL assumed first (conservative).
Costs: fee 0.10% + slippage 0.02% per side.
"""
import numpy as np
import pandas as pd
from pathlib import Path
import signal_xauusd_meanrev as sig   # reuse loader + cost constants

COST_SIDE = (sig.DEFAULT_COSTS["fee_pct"] + sig.DEFAULT_COSTS["slippage_pct"]) / 100.0
CAP0 = 10_000.0
RISK_NOTIONAL = 1_000.0   # $ exposure per trade (single unit)


# ------------------------------------------------------------------ generic backtester
def run_trades(df, entries, sl_frac, tp_frac=None, exit_on_sma=None):
    """
    entries: int array per bar, +1 = go long at THIS bar's open, -1 = short, 0 = none
             (already shifted: decided from prior closed bar).
    sl_frac : stop distance as fraction of entry price (e.g. 0.01 = 1%).
    tp_frac : take-profit distance as fraction; None = no fixed TP.
    exit_on_sma: optional array; if provided, exit long when close>=sma, short when close<=sma.
    Returns (trades_df, equity Series).
    """
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy();  c = df["close"].to_numpy()
    idx = df.index
    n = len(df)

    equity = np.full(n, CAP0)
    realized = 0.0
    side = 0; entry_px = 0.0; sl = 0.0; tp = 0.0; entry_i = 0
    trades = []

    def close_trade(i, exit_px, reason):
        nonlocal realized, side, entry_px
        pnl = side * (exit_px - entry_px) / entry_px * RISK_NOTIONAL
        fees = COST_SIDE * RISK_NOTIONAL * 2
        realized += pnl - fees
        trades.append({"entry_time": idx[entry_i], "exit_time": idx[i],
                       "side": "long" if side == 1 else "short",
                       "entry": entry_px, "exit": exit_px, "reason": reason,
                       "pnl": pnl - fees, "bars_held": i - entry_i})
        side = 0

    for i in range(n):
        # manage open position with THIS bar's range
        if side != 0:
            hit_sl = (l[i] <= sl) if side == 1 else (h[i] >= sl)
            hit_tp = (h[i] >= tp) if (tp_frac and side == 1) else \
                     (l[i] <= tp) if (tp_frac and side == -1) else False
            if hit_sl:
                close_trade(i, sl, "SL")
            elif hit_tp:
                close_trade(i, tp, "TP")
            elif exit_on_sma is not None and not np.isnan(exit_on_sma[i]):
                if (side == 1 and c[i] >= exit_on_sma[i]) or \
                   (side == -1 and c[i] <= exit_on_sma[i]):
                    close_trade(i, c[i], "SMA")

        # new entry at this bar's open (only if flat)
        if side == 0 and entries[i] != 0:
            side = int(entries[i]); entry_px = o[i]; entry_i = i
            if side == 1:
                sl = entry_px * (1 - sl_frac); tp = entry_px * (1 + (tp_frac or 0))
            else:
                sl = entry_px * (1 + sl_frac); tp = entry_px * (1 - (tp_frac or 0))

        # mark-to-market
        unreal = side * (c[i] - entry_px) / entry_px * RISK_NOTIONAL if side else 0.0
        equity[i] = CAP0 + realized + unreal

    return pd.DataFrame(trades), pd.Series(equity, index=idx, name="equity")


# ------------------------------------------------------------------ strategy A: MeanRev + SL
def strat_meanrev_sl(df, sma_len=200, init_dist=0.5, sl_frac=0.010):
    close = df["close"]
    sma = close.rolling(sma_len).mean()
    dist = (close - sma) / sma * 100.0
    d_prev = dist.shift(1).to_numpy()          # prior closed bar
    sma_arr = sma.to_numpy()

    entries = np.zeros(len(df), dtype=int)
    # enter long when stretched below, short when stretched above
    entries[d_prev <= -init_dist] = 1
    entries[d_prev >= init_dist] = -1
    return run_trades(df, entries, sl_frac=sl_frac, tp_frac=None, exit_on_sma=sma_arr)


# ------------------------------------------------------------------ strategy B: EMA pullback (trend)
def strat_ema_pullback(df, ema_f=50, ema_s=200, sl_frac=0.010, rr=2.0):
    c = df["close"]
    ef = c.ewm(span=ema_f, adjust=False).mean()
    es = c.ewm(span=ema_s, adjust=False).mean()
    low = df["low"]; high = df["high"]

    up = (ef > es)
    dn = (ef < es)
    # pullback: in uptrend, bar's low dipped to/under EMA50 but closed back above it
    long_sig = up & (low <= ef) & (c > ef)
    short_sig = dn & (high >= ef) & (c < ef)

    entries = np.zeros(len(df), dtype=int)
    entries[long_sig.shift(1).fillna(False).to_numpy()] = 1
    entries[short_sig.shift(1).fillna(False).to_numpy()] = -1
    # trend-follow: fixed SL + TP at rr * SL, no SMA exit
    return run_trades(df, entries, sl_frac=sl_frac, tp_frac=sl_frac * rr, exit_on_sma=None)


# ------------------------------------------------------------------ metrics
def metrics(trades, eq, df, label):
    m = {"strategy": label, "trades": len(trades)}
    if len(trades):
        w = trades[trades.pnl > 0]; los = trades[trades.pnl <= 0]
        m["win_rate_%"] = round(len(w) / len(trades) * 100, 1)
        aw = w.pnl.mean() if len(w) else 0.0
        al = abs(los.pnl.mean()) if len(los) else np.nan
        m["avg_RR"] = round(aw / al, 2) if al and not np.isnan(al) else float("inf")
        gp, gl = w.pnl.sum(), abs(los.pnl.sum())
        m["profit_factor"] = round(gp / gl, 2) if gl else float("inf")
        m["expectancy_$"] = round(trades.pnl.mean(), 2)
        m["total_return_%"] = round(trades.pnl.sum() / CAP0 * 100, 1)
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    m["max_DD_%"] = round(dd.min(), 1)
    m["final_equity_$"] = round(float(eq.iloc[-1]), 0)
    return m


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_15m_real.csv"
    df = sig.load_csv(path)
    bh = round((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100, 1)
    print(f"data: {len(df):,} bars  {df.index[0]} -> {df.index[-1]}  |  Buy&Hold {bh}%\n")

    rows = []
    tA, eA = strat_meanrev_sl(df, sl_frac=0.010)
    rows.append(metrics(tA, eA, df, "A) MeanRev+SL 1.0%"))
    tA2, eA2 = strat_meanrev_sl(df, sl_frac=0.020)
    rows.append(metrics(tA2, eA2, df, "A) MeanRev+SL 2.0%"))
    tB, eB = strat_ema_pullback(df, sl_frac=0.010, rr=2.0)
    rows.append(metrics(tB, eB, df, "B) EMA-Pullback 2R"))
    tB2, eB2 = strat_ema_pullback(df, sl_frac=0.010, rr=1.5)
    rows.append(metrics(tB2, eB2, df, "B) EMA-Pullback 1.5R"))

    out = pd.DataFrame(rows).set_index("strategy")
    print(out.to_string())
    Path("reports").mkdir(parents=True, exist_ok=True)
    out.to_csv("reports/strategy_comparison.csv")
