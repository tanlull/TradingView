#!/usr/bin/env python3
"""
Does martingale work better on a HIGH win-rate strategy at higher timeframes?

High-WR engine: mean-reversion, exit at SMA touch (small target = frequent wins),
with a WIDE stop (fewer stop-outs -> higher WR, but each loss is large).
Tested on 15m / 1H / 4H. Then martingale overlay + ruin measurement.

Honest question this answers: high WR shortens TYPICAL losing streaks, but does the
WORST streak (the tail that causes ruin) get short enough to make martingale safe?
"""
import numpy as np, pandas as pd
import signal_xauusd_meanrev as sig
import strategies_compare as S
import martingale_test as M


def worst_streak(pnl):
    w = pnl > 0; s = mx = 0
    for x in w:
        if x: s = 0
        else: s += 1; mx = max(mx, s)
    return mx


def run(path, tf, sma_len, sl_frac):
    df = sig.load_csv(path)
    t, e = S.strat_meanrev_sl(df, sma_len=sma_len, init_dist=0.5, sl_frac=sl_frac)
    t = t.sort_values("exit_time").reset_index(drop=True)
    m = S.metrics(t, e, df, "x")
    ws = worst_streak(t["pnl"].to_numpy())
    print(f"\n{tf}  SMA{sma_len} SL{sl_frac*100:.0f}%  | trades {m['trades']:>4}  "
          f"WR {m['win_rate_%']:>4}%  RR {m['avg_RR']}  PF {m['profit_factor']}  "
          f"return {m['total_return_%']:>6}%  worstLossStreak {ws}")
    # martingale overlays
    for factor, cap in [(2.0, None), (2.0, 4), (1.5, None)]:
        r = M.martingale_sim(t, factor=factor, cap_steps=cap)
        cd = f"cap{cap}" if cap else "no-cap"
        st = "💥 RUINED" if r["ruined"] else f"${r['final_equity']:>9}"
        print(f"    MG x{factor} {cd:>6}: {st:>13}  maxDD {r['max_DD_%']:>6}%  "
              f"peakSize {r['max_size_x']:>6}x")
    return m, ws


if __name__ == "__main__":
    S.COST_SIDE = 0.03 / 100   # realistic gold cost per side
    print("=== realistic cost 0.03%/side | high-WR mean-reversion + martingale ===")
    # wider SL -> higher WR. sweep to find genuinely high WR configs.
    for path, tf in [("data/XAUUSD_15m_real.csv","15m"),
                     ("data/XAUUSD_1H_real.csv","1H"),
                     ("data/XAUUSD_4H_real.csv","4H")]:
        for sl in (0.02, 0.04):
            run(path, tf, 200, sl)
