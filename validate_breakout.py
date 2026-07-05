#!/usr/bin/env python3
"""
Robustness / anti-overfit validation for Breakout on higher timeframes.

Guards applied:
  1. IS/OOS split — pick params on 2012-2018, validate untouched on 2019-2022.
  2. Grid OOS robustness — % of the param grid that stays PF>1 out of sample.
  3. Yearly consistency — PF per calendar year (edge should not rely on one year).
  4. Long/short split — is the edge one-sided?
  5. Cost stress — PF at 0.03 / 0.06 / 0.10 %/side.

No look-ahead: reuses strategies_v2.strat_breakout (signal from closed bar, fill next open).
"""
import numpy as np, pandas as pd
import signal_xauusd_meanrev as sig, strategies_compare as S, strategies_v2 as V

SPLIT = pd.Timestamp("2019-01-01", tz="UTC")


def stats(df, lb, rr, cost, side_filter=None):
    S.COST_SIDE = cost / 100
    t, e = V.strat_breakout(df, lb, 0.01, rr, None)
    if side_filter:
        t = t[t["side"] == side_filter]
    if len(t) == 0:
        return dict(trades=0, PF=np.nan, ret=np.nan, WR=np.nan)
    w = t[t.pnl > 0].pnl.sum(); l = abs(t[t.pnl <= 0].pnl.sum())
    return dict(trades=len(t), PF=round(w / l, 2) if l else np.inf,
                ret=round(t.pnl.sum() / 100, 1), WR=round((t.pnl > 0).mean() * 100, 1))


def grid_pf(df, cost):
    lbs = [15, 20, 30, 40, 55]; rrs = [1.5, 2.0, 2.5, 3.0]
    vals = [stats(df, lb, rr, cost)["PF"] for lb in lbs for rr in rrs]
    vals = [v for v in vals if not np.isnan(v)]
    return np.array(vals)


def run_tf(path, tf):
    df = sig.load_csv(path)
    IS = df[df.index < SPLIT]; OOS = df[df.index >= SPLIT]
    print(f"\n{'='*78}\n{tf}  |  IS {IS.index[0].date()}–{IS.index[-1].date()} ({len(IS)} bars)  "
          f"|  OOS {OOS.index[0].date()}–{OOS.index[-1].date()} ({len(OOS)} bars)")

    # 1) pick best config on IS by PF (cost 0.05)
    best = None
    for lb in [15, 20, 30, 40, 55]:
        for rr in [1.5, 2.0, 2.5, 3.0]:
            s = stats(IS, lb, rr, 0.05)
            if s["trades"] >= 50 and (best is None or s["PF"] > best[2]):
                best = (lb, rr, s["PF"])
    lb, rr, _ = best
    print(f"IS-best pick: lookback={lb}  R:R={rr}")
    si = stats(IS, lb, rr, 0.05); so = stats(OOS, lb, rr, 0.05)
    print(f"  IS : PF {si['PF']}  WR {si['WR']}%  ret {si['ret']}%  ({si['trades']} tr)")
    print(f"  OOS: PF {so['PF']}  WR {so['WR']}%  ret {so['ret']}%  ({so['trades']} tr)  "
          f"<-- {'HOLDS ✅' if so['PF'] > 1 else 'FAILS ❌'}")

    # 2) grid robustness OOS
    g = grid_pf(OOS, 0.05)
    print(f"  OOS grid robustness: {int((g>1).sum())}/{len(g)} configs PF>1  "
          f"(median PF {np.median(g):.2f})")

    # 3) yearly PF for the pick
    print("  yearly PF:", end=" ")
    for yr in range(2012, 2023):
        seg = df[(df.index.year == yr)]
        if len(seg) < 200: continue
        s = stats(seg, lb, rr, 0.05)
        print(f"{yr}:{s['PF']}", end="  ")
    print()

    # 4) long/short split (full sample)
    sl = stats(df, lb, rr, 0.05, "long"); ss = stats(df, lb, rr, 0.05, "short")
    print(f"  long PF {sl['PF']} ({sl['trades']}tr) | short PF {ss['PF']} ({ss['trades']}tr)")

    # 5) cost stress (full)
    print("  cost stress PF:", "  ".join(
        f"{c}%:{stats(df, lb, rr, c)['PF']}" for c in (0.03, 0.06, 0.10)))
    return lb, rr


if __name__ == "__main__":
    for path, tf in [("data/XAUUSD_4H_real.csv", "4H"), ("data/XAUUSD_1H_real.csv", "1H")]:
        run_tf(path, tf)
