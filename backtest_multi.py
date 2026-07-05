#!/usr/bin/env python3
"""
Breakout HTF — MULTI-POSITION + SIZE-DECAY reference backtest (production spec).

This is the reference implementation that the MQL5 EA (ea_breakout_htf.mq5) must
match. Signal is the SAME closed-bar Donchian breakout as signal_breakout_htf.py;
the only additions are the EXECUTION rules:

  - allow up to MAX_OPEN concurrent positions (do NOT wait for the previous to close)
  - the k-th concurrent position (k=0 for the first) is sized  base * SIZE_DECAY**k
    (anti-martingale: later/lower-quality stacked breakouts risk less)

Locked config (validated on real 1M data 2022-2026, IS/OOS checked):
  LOOKBACK=20, RR=2.5, SL_FRAC=0.01, MAX_OPEN=3, SIZE_DECAY=0.4, cost 0.05%/side.
  Full-sample: PF 1.40, ret +10.0%, maxDD -1.3%, ret/DD 8.0
  OOS 2025-2026: PF 1.27 (edge survives out of sample).

Intrabar priority: SL checked before TP (conservative). Fill at bar open.

Usage: python backtest_multi.py <data.csv>   (accepts 1H OHLCV; MT5/TradingView format)
"""
import sys
import numpy as np
import pandas as pd

LOOKBACK = 20
RR = 2.5
SL_FRAC = 0.01
MAX_OPEN = 3
SIZE_DECAY = 0.4
FEE_PCT = 0.05          # per side, percent
BASE_NOTIONAL = 1000.0
CAP0 = 10000.0
COST = FEE_PCT / 100.0


def load(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next(c for c in ("time", "timestamp", "date", "datetime") if c in df.columns)
    df["ts"] = pd.to_datetime(df[tcol], utc=True, format="mixed")
    return df.sort_values("ts").reset_index(drop=True)


def backtest(df, max_open=MAX_OPEN, size_decay=SIZE_DECAY,
             lookback=LOOKBACK, rr=RR, sl_frac=SL_FRAC):
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy();  c = df["close"].to_numpy()
    ts = df["ts"].to_numpy(); n = len(df)
    hh = pd.Series(h).rolling(lookback).max().shift(1).to_numpy()
    ll = pd.Series(l).rolling(lookback).min().shift(1).to_numpy()

    pos = []            # open positions: dict(side, entry, sl, tp, nt)
    realized = 0.0
    trades = []         # (exit_ts, pnl, side, rank)
    eq = np.full(n, CAP0)

    for i in range(1, n):
        # manage existing positions on this bar
        still = []
        for p in pos:
            ex = None
            if p["side"] == 1:
                if l[i] <= p["sl"]:   ex = p["sl"]
                elif h[i] >= p["tp"]: ex = p["tp"]
            else:
                if h[i] >= p["sl"]:   ex = p["sl"]
                elif l[i] <= p["tp"]: ex = p["tp"]
            if ex is not None:
                pnl = p["side"] * (ex - p["entry"]) / p["entry"] * p["nt"] - COST * p["nt"] * 2
                realized += pnl
                trades.append((ts[i], pnl, p["side"], p["rank"]))
            else:
                still.append(p)
        pos = still

        # closed-bar breakout signal (uses bar i-1)
        s = 0
        if not np.isnan(hh[i-1]):
            if c[i-1] > hh[i-1]:   s = 1
            elif c[i-1] < ll[i-1]: s = -1

        # open a new (possibly stacked) position at this bar's open
        if s != 0 and len(pos) < max_open:
            rank = len(pos)
            nt = BASE_NOTIONAL * (size_decay ** rank)
            entry = o[i]
            if s == 1: sl = entry * (1 - sl_frac); tp = entry * (1 + sl_frac * rr)
            else:      sl = entry * (1 + sl_frac); tp = entry * (1 - sl_frac * rr)
            pos.append(dict(side=s, entry=entry, sl=sl, tp=tp, nt=nt, rank=rank))

        eq[i] = CAP0 + realized + sum(
            p["side"] * (c[i] - p["entry"]) / p["entry"] * p["nt"] for p in pos)

    tdf = pd.DataFrame(trades, columns=["exit_ts", "pnl", "side", "rank"])
    eqs = pd.Series(eq, index=df["ts"])
    return tdf, eqs


def report(tdf, eqs, label=""):
    pnl = tdf["pnl"].to_numpy()
    w = pnl[pnl > 0]; los = pnl[pnl <= 0]
    pf = w.sum() / -los.sum() if los.sum() < 0 else float("inf")
    dd = ((eqs - eqs.cummax()) / eqs.cummax() * 100).min()
    ret = pnl.sum() / CAP0 * 100
    # worst losing streak
    s = mx = 0
    for x in pnl: s = 0 if x > 0 else s + 1; mx = max(mx, s)
    print(f"{label}trades {len(tdf)}  WR {(pnl>0).mean()*100:.1f}%  PF {pf:.2f}  "
          f"ret {ret:.1f}%  maxDD {dd:.1f}%  ret/DD {ret/-dd:.1f}  worstStreak {mx}")
    yr = tdf.assign(y=pd.to_datetime(tdf["exit_ts"]).dt.year).groupby("y").pnl.sum() / CAP0 * 100
    print("  yearly %:", "  ".join(f"{y}:{v:.1f}" for y, v in yr.items()))
    # per-rank contribution
    rk = tdf.groupby("rank").pnl.agg(["count", "sum"])
    print("  by rank:", "  ".join(f"#{r}:{int(row['count'])}tr/${row['sum']:.0f}" for r, row in rk.iterrows()))


# preset ladder shared with the MQL5 EA (ea_breakout_htf.mq5)
PRESETS = {
    "CONSERVATIVE": dict(max_open=1, size_decay=0.4),
    "BALANCED":     dict(max_open=3, size_decay=0.4),
    "AGGRESSIVE":   dict(max_open=5, size_decay=0.8),
}

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_1H_MT5_export_20220408_20260703.csv"
    df = load(path)
    print(f"data: {path}  {len(df)} bars  {df['ts'].iloc[0]} -> {df['ts'].iloc[-1]}\n")
    for name, kw in PRESETS.items():
        print(f"=== {name}  (cap{kw['max_open']} decay{kw['size_decay']}) ===")
        tdf, eqs = backtest(df, **kw)
        report(tdf, eqs)
        print()
