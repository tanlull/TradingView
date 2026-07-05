#!/usr/bin/env python3
"""
Intrabar-fill backtest for Breakout HTF — resolves SL/TP order using FINE bars.

The coarse engine (signal_breakout_htf.backtest) works on 1H bars and, when SL and
TP both fall inside the same 1H bar, assumes SL is hit first (conservative). This
engine replays each trade minute-by-minute (or 5m) so the ACTUAL first-touch decides
the exit. Comparing the two tells us how much that assumption distorts results.

Signals: computed on the SIGNAL timeframe (1H). Fills: walked on the FINE timeframe.
Anti look-ahead preserved: entry = signal-bar's next open; exits only from fine bars
at/after entry. If SL and TP are both inside ONE fine bar, SL still wins (tiny residual).

Usage: python backtest_intrabar.py <signal_1H.csv> <fine_1m_or_5m.csv>
"""
import sys
import numpy as np
import pandas as pd
import signal_breakout_htf as S

RR, SL_FRAC, FEE = S.RR, S.SL_FRAC, S.FEE_PCT
RISK, CAP0 = S.RISK_NOTIONAL, S.CAP0
COST = FEE / 100.0


def load_ts(path):
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["time"], utc=True)
    return df.sort_values("ts").reset_index(drop=True)


def entries_from_signals(sigdf):
    """Return list of (entry_idx_in_signal, entry_time, side) respecting flat-only."""
    h = sigdf["high"].to_list(); l = sigdf["low"].to_list(); c = sigdf["close"].to_list()
    sig = S.compute_signals(h, l, c)
    # sequential flat-only entry selection is done later against fine exits;
    # here just return the raw per-bar intended side at each bar's OPEN
    intended = [0] * len(sig)
    for i in range(1, len(sig)):
        intended[i] = sig[i - 1]   # act at bar i open from closed bar i-1
    return intended


def run_fine(sigdf, finedf):
    o = sigdf["open"].to_numpy()
    ts_sig = sigdf["ts"].astype("int64").to_numpy()   # epoch ns
    intended = entries_from_signals(sigdf)

    fts = finedf["ts"].astype("int64").to_numpy()      # epoch ns
    fh = finedf["high"].to_numpy(); fl = finedf["low"].to_numpy()
    fo = finedf["open"].to_numpy(); fc = finedf["close"].to_numpy()
    nf = len(finedf)

    trades = []
    i = 1
    n = len(sigdf)
    fp = 0  # fine pointer (monotonic)
    while i < n:
        if intended[i] == 0:
            i += 1; continue
        side = intended[i]
        entry_t = ts_sig[i]
        # locate first fine bar at/after entry_t
        while fp < nf and fts[fp] < entry_t:
            fp += 1
        if fp >= nf:
            break
        entry = fo[fp]
        if side == 1:
            sl = entry * (1 - SL_FRAC); tp = entry * (1 + SL_FRAC * RR)
        else:
            sl = entry * (1 + SL_FRAC); tp = entry * (1 - SL_FRAC * RR)
        # walk fine bars to first touch
        j = fp; exit_px = None; exit_t = None
        while j < nf:
            hit_sl = (fl[j] <= sl) if side == 1 else (fh[j] >= sl)
            hit_tp = (fh[j] >= tp) if side == 1 else (fl[j] <= tp)
            if hit_sl:                      # SL priority if same fine bar
                exit_px = sl; exit_t = fts[j]; break
            if hit_tp:
                exit_px = tp; exit_t = fts[j]; break
            j += 1
        if exit_px is None:
            exit_px = fc[nf - 1]; exit_t = fts[nf - 1]
        pnl = side * (exit_px - entry) / entry * RISK - COST * RISK * 2
        trades.append({"entry_t": entry_t, "exit_t": exit_t, "side": side,
                       "entry": entry, "exit": exit_px, "pnl": pnl})
        # resume signal scan at the first bar AFTER exit (flat-only)
        while i < n and ts_sig[i] <= exit_t:
            i += 1
        # advance fine pointer near exit to keep it monotonic-ish
        fp = j
    return pd.DataFrame(trades)


def metrics(tr, label):
    w = tr[tr.pnl > 0]; ls = tr[tr.pnl <= 0]
    gp, gl = w.pnl.sum(), -ls.pnl.sum()
    eq = CAP0 + tr.pnl.cumsum(); peak = eq.cummax(); dd = ((eq - peak) / peak * 100).min()
    return (f"{label:16} trades {len(tr):>4}  WR {len(w)/len(tr)*100:4.1f}%  "
            f"PF {gp/gl:4.2f}  ret {tr.pnl.sum()/CAP0*100:6.1f}%  maxDD {dd:5.1f}%")


if __name__ == "__main__":
    sig_path = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_1H_2020_2025.csv"
    fine_path = sys.argv[2] if len(sys.argv) > 2 else "data/XAUUSD_5m_2020_2025.csv"
    sigdf = load_ts(sig_path); finedf = load_ts(fine_path)
    print(f"signals: {sig_path} ({len(sigdf)} bars)  |  fills: {fine_path} ({len(finedf)} bars)\n")

    # coarse (1H-fill, SL-before-TP assumption)
    d = {k: sigdf[k].to_list() for k in ("open", "high", "low", "close")}
    d["time"] = sigdf["time"].to_list()
    cm = S.backtest(d)
    print(f"{'COARSE 1H-fill':16} trades {cm['trades']:>4}  WR {cm['win_rate_%']:4.1f}%  "
          f"PF {cm['profit_factor']:4.2f}  ret {cm['total_return_%']:6.1f}%  maxDD {cm['max_drawdown_%']:5.1f}%")
    # fine (intrabar)
    tr = run_fine(sigdf, finedf)
    print(metrics(tr, "FINE intrabar"))

    # how often did a bar contain BOTH sl and tp (the ambiguous case)?
    print("\n(ถ้า PF/return สองบรรทัดใกล้กัน = assumption 'SL ก่อน TP' ไม่ได้บิดผลอย่างมีนัยยะ)")
