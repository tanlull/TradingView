#!/usr/bin/env python3
"""
Trade-level MARTINGALE overlay on top of a base strategy (with SL/TP).

Rule: after a losing trade multiply next trade's size by `factor`; after a win,
reset to base. Optional cap on consecutive steps. Everything (pnl AND fees) scales
LINEARLY with position size, so we can re-simulate equity by scaling each base-size
trade's pnl — mathematically exact.

⚠️ RISK NOTE: martingale converts an ordinary losing streak into exponential position
growth. Even a POSITIVE-expectancy system can hit "risk of ruin" when a long enough
losing run occurs. This script measures exactly that, it does not endorse the method.
"""
import numpy as np
import pandas as pd
import signal_xauusd_meanrev as sig
import strategies_compare as S
import strategies_v2 as V

CAP0 = 10_000.0
BASE_RISK = 100.0   # $ risked on the 1% SL at base size (1% of start capital)


def martingale_sim(trades, factor=2.0, cap_steps=None, reset_on_win=True,
                   cap0=CAP0, base_risk=BASE_RISK):
    """
    trades: chronological DataFrame with 'pnl' at base notional S.RISK_NOTIONAL
            (pnl already includes fees; both scale linearly with size).
    Returns dict of outcome stats + equity list.
    """
    # convert each trade's $pnl at base notional -> pnl per 1 unit of "base risk"
    # base pnl corresponds to RISK_NOTIONAL exposure; keep as the base multiplier=1 unit.
    pnl_base = trades["pnl"].to_numpy()
    win = pnl_base > 0

    cap = cap0
    mult = 1.0
    eq = [cap]
    ruined = False
    max_mult = 1.0
    streak = 0; longest_streak = 0

    for k in range(len(pnl_base)):
        trade_pnl = pnl_base[k] * mult
        cap += trade_pnl
        eq.append(cap)
        max_mult = max(max_mult, mult)
        if cap <= 0:
            ruined = True
            break
        if win[k]:
            mult = 1.0
            streak = 0
        else:
            streak += 1
            longest_streak = max(longest_streak, streak)
            mult *= factor
            if cap_steps is not None and mult > factor ** cap_steps:
                mult = 1.0   # give up the recovery ladder, reset (bounded martingale)

    eq = pd.Series(eq)
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    return {
        "factor": factor, "cap_steps": cap_steps,
        "ruined": ruined, "final_equity": round(cap, 0),
        "min_equity": round(eq.min(), 0), "max_DD_%": round(dd.min(), 1),
        "max_size_x": round(max_mult, 1), "longest_loss_streak": int(longest_streak),
        "trades_taken": int(k + 1),
    }


def flat_sim(trades, cap0=CAP0):
    cap = cap0 + trades["pnl"].cumsum()
    eq = pd.concat([pd.Series([cap0]), cap], ignore_index=True)
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    return {"final_equity": round(eq.iloc[-1], 0), "max_DD_%": round(dd.min(), 1)}


if __name__ == "__main__":
    df = sig.load_csv("data/XAUUSD_15m_real.csv")

    for cost in (0.12, 0.03):   # spec cost vs realistic gold cost, per side
        S.COST_SIDE = cost / 100
        trades, _ = V.strat_breakout(df, lookback=40, sl_frac=0.01, rr=2.0, adx_series=None)
        trades = trades.sort_values("exit_time").reset_index(drop=True)
        base = flat_sim(trades)
        print(f"\n{'='*74}\nBreakout40 2R  |  cost {cost:.2f}%/side  |  {len(trades)} trades")
        print(f"  FLAT sizing:      final ${base['final_equity']:>10}   maxDD {base['max_DD_%']}%")
        for factor, cap_steps in [(2.0, None), (2.0, 4), (1.5, None), (1.5, 6)]:
            r = martingale_sim(trades, factor=factor, cap_steps=cap_steps)
            capdesc = f"cap{cap_steps}" if cap_steps else "no-cap"
            status = "💥 RUINED" if r["ruined"] else f"final ${r['final_equity']:>10}"
            print(f"  MG x{factor} {capdesc:>6}: {status:>18}   "
                  f"maxDD {r['max_DD_%']}%  peakSize {r['max_size_x']}x  "
                  f"worstStreak {r['longest_loss_streak']}")
