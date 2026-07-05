#!/usr/bin/env python3
"""
More strategies on REAL XAUUSD 15m + ADX(14)>25 quality filter.

Added:
  C) Breakout   : Donchian N-bar high/low breakout (trend). Fixed SL + R-multiple TP.
  D) FVG        : 3-candle Fair Value Gap retest (SMC imbalance). Enter on pullback
                  into a bullish FVG (support) / bearish FVG (resistance).
  E) SMC        : Break-of-Structure + order-block pullback. Swings confirmed with a
                  delay (no look-ahead), enter first pullback after BOS.

All reuse strategies_compare.run_trades (anti look-ahead: signal from closed bar,
fill next open; intrabar SL before TP; fee 0.10% + slip 0.02% per side).
Note: FVG/SMC are discretionary concepts — these are ONE systematic interpretation,
not "the" definition. Results depend heavily on the coded rules.
"""
import numpy as np
import pandas as pd
from pathlib import Path
import signal_xauusd_meanrev as sig
import strategies_compare as S

N = None  # set at runtime


# ------------------------------------------------------------------ indicators
def adx(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff(); dn = -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def to_entries(df, long_sig, short_sig, adx_series=None, adx_thr=25.0):
    """closed-bar boolean signals -> entry array (fill NEXT bar open). Optional ADX gate."""
    n = len(df)
    ls = long_sig.shift(1).fillna(False).to_numpy()
    ss = short_sig.shift(1).fillna(False).to_numpy()
    e = np.zeros(n, dtype=int); e[ls] = 1; e[ss] = -1
    if adx_series is not None:
        g = (adx_series.shift(1) > adx_thr).fillna(False).to_numpy()
        e[~g] = 0
    return e


# ------------------------------------------------------------------ C) Breakout (Donchian)
def strat_breakout(df, lookback=20, sl_frac=0.010, rr=2.0, adx_series=None):
    h, l, c = df["high"], df["low"], df["close"]
    hh = h.rolling(lookback).max().shift(1)   # prior N-bar high (excludes current)
    ll = l.rolling(lookback).min().shift(1)
    long_sig = c > hh
    short_sig = c < ll
    e = to_entries(df, long_sig, short_sig, adx_series)
    return S.run_trades(df, e, sl_frac=sl_frac, tp_frac=sl_frac * rr, exit_on_sma=None)


# ------------------------------------------------------------------ D) FVG retest
def strat_fvg(df, max_wait=20, sl_frac=0.010, rr=2.0, adx_series=None):
    """
    Bullish FVG at bar i: high[i-2] < low[i]  -> gap zone [high[i-2], low[i]].
    Enter long when a later bar's low dips back into the zone (retest) and closes
    above zone bottom. Symmetric for bearish. Signals emitted on the RETEST bar.
    """
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    n = len(df)
    long_sig = np.zeros(n, dtype=bool); short_sig = np.zeros(n, dtype=bool)
    bull_zones = []  # (bottom, top, created_i)
    bear_zones = []
    for i in range(2, n):
        # detect new FVGs from the just-closed 3-candle pattern (i-2, i-1, i)
        if h[i-2] < l[i]:
            bull_zones.append((h[i-2], l[i], i))
        if l[i-2] > h[i]:
            bear_zones.append((h[i], l[i-2], i))
        # test retests on this closed bar
        for z in bull_zones[:]:
            bottom, top, ci = z
            if i - ci > max_wait or c[i] < bottom:
                bull_zones.remove(z); continue
            if l[i] <= top and c[i] >= bottom:   # dipped into zone, held above bottom
                long_sig[i] = True; bull_zones.remove(z)
        for z in bear_zones[:]:
            bottom, top, ci = z
            if i - ci > max_wait or c[i] > top:
                bear_zones.remove(z); continue
            if h[i] >= bottom and c[i] <= top:
                short_sig[i] = True; bear_zones.remove(z)
    ls = pd.Series(long_sig, index=df.index); ss = pd.Series(short_sig, index=df.index)
    e = to_entries(df, ls, ss, adx_series)
    return S.run_trades(df, e, sl_frac=sl_frac, tp_frac=sl_frac * rr, exit_on_sma=None)


# ------------------------------------------------------------------ E) SMC (BOS + pullback)
def strat_smc(df, k=5, sl_frac=0.010, rr=2.0, adx_series=None):
    """
    Swing high/low via k-bar fractal, CONFIRMED k bars later (no look-ahead).
    Bullish BOS: close breaks last confirmed swing high -> bullish bias.
    Enter long on the first pullback bar (red candle) after BOS. Symmetric short.
    """
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    n = len(df)
    last_sh = np.nan; last_sl = np.nan
    bias = 0; armed = False
    long_sig = np.zeros(n, dtype=bool); short_sig = np.zeros(n, dtype=bool)
    for i in range(k, n):
        # confirm swing at bar (i-k) using window [i-2k, i]  (all <= i, no future)
        p = i - k
        if p - k >= 0:
            win_h = h[p-k:i+1]; win_l = l[p-k:i+1]
            if h[p] == win_h.max(): last_sh = h[p]
            if l[p] == win_l.min(): last_sl = l[p]
        # structure break on closed bar i
        if not np.isnan(last_sh) and c[i] > last_sh:
            bias = 1; armed = True; last_sh = np.nan
        elif not np.isnan(last_sl) and c[i] < last_sl:
            bias = -1; armed = True; last_sl = np.nan
        # entry on first pullback after BOS
        if armed:
            if bias == 1 and c[i] < c[i-1]:
                long_sig[i] = True; armed = False
            elif bias == -1 and c[i] > c[i-1]:
                short_sig[i] = True; armed = False
    ls = pd.Series(long_sig, index=df.index); ss = pd.Series(short_sig, index=df.index)
    e = to_entries(df, ls, ss, adx_series)
    return S.run_trades(df, e, sl_frac=sl_frac, tp_frac=sl_frac * rr, exit_on_sma=None)


# ------------------------------------------------------------------ runner
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_15m_real.csv"
    df = sig.load_csv(path)
    A = adx(df, 14)
    bh = round((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100, 1)
    print(f"data {len(df):,} bars {df.index[0].date()}->{df.index[-1].date()} | "
          f"Buy&Hold {bh}% | ADX>25 on {(A>25).mean()*100:.0f}% of bars\n")

    configs = [
        ("C) Breakout20 2R",        lambda f: strat_breakout(df, 20, 0.01, 2.0, f)),
        ("D) FVG 2R",               lambda f: strat_fvg(df, 20, 0.01, 2.0, f)),
        ("E) SMC 2R",               lambda f: strat_smc(df, 5, 0.01, 2.0, f)),
        ("B) EMA-Pullback 2R",      lambda f: S.strat_ema_pullback(df, 50, 200, 0.01, 2.0)
                                    if f is None else _ema_adx(df, f)),
    ]

    rows = []
    for name, fn in configs:
        for tag, gate in (("no filter", None), ("ADX>25", A)):
            try:
                t, e = fn(gate)
                m = S.metrics(t, e, df, f"{name} [{tag}]")
                rows.append(m)
            except Exception as ex:
                rows.append({"strategy": f"{name} [{tag}]", "trades": 0, "err": str(ex)[:40]})
    out = pd.DataFrame(rows).set_index("strategy")
    cols = [c for c in ["trades","win_rate_%","avg_RR","profit_factor","expectancy_$",
                        "total_return_%","max_DD_%","final_equity_$"] if c in out.columns]
    print(out[cols].to_string())
    Path("reports").mkdir(parents=True, exist_ok=True)
    out[cols].to_csv("reports/strategy_comparison_v2.csv")


def _ema_adx(df, A):
    """EMA-pullback with ADX gate (reuse via re-deriving entries)."""
    c = df["close"]; ef = c.ewm(span=50, adjust=False).mean(); es = c.ewm(span=200, adjust=False).mean()
    low = df["low"]; high = df["high"]
    long_sig = (ef > es) & (low <= ef) & (c > ef)
    short_sig = (ef < es) & (high >= ef) & (c < ef)
    e = to_entries(df, long_sig, short_sig, A)
    return S.run_trades(df, e, sl_frac=0.01, tp_frac=0.02, exit_on_sma=None)
