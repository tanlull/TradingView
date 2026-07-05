#!/usr/bin/env python3
"""
Grid-Martingale (averaging-down basket) simulator for XAUUSD — HONEST risk sizing.

Models the popular "recovery grid" EA:
  - open an initial order (INIT_LOT) in one direction
  - every `step_usd` the price moves AGAINST the basket, add another order with
    lot = previous * `lot_mult`   (martingale)
  - when the basket's floating PnL >= `target_usd`, close EVERYTHING in profit and
    restart a fresh basket at the current price
  - `max_levels` caps how many orders a basket may stack (the ONLY thing between
    you and ruin)

Goal being tested: "when price drops, all orders close in profit without stopout."
This script measures whether that holds on REAL gold, and what capital / inputs
are required to survive the worst historical move — and what still can't be survived.

Contract math (XAUUSD): 1.00 lot = 100 oz; $1 price move on 0.01 lot = $1 PnL.
Margin/order = lots*100*price/leverage. Stopout when margin level < STOPOUT_LEVEL%.
Within a bar we add levels on the LOW (buy grid) and stress-test equity at the LOW
before checking the target at the HIGH — conservative.
"""
import sys
import numpy as np
import pandas as pd

CONTRACT = 100.0        # oz per 1.0 lot
STOPOUT_LEVEL = 50.0    # % margin level -> broker force-close (ruin for this strategy)
POINT = 0.01            # XAUUSD 1 point = 0.01 USD (2-digit broker). 100 points = $1.
                        # so step 2000 points = $20 ; 1 "pip"(=10 points) = $0.10


def simulate(df, direction=+1, init_lot=0.01, step_points=2000, lot_mult=2.0,
             target_usd=50.0, max_levels=10, capital=100_000.0, leverage=100.0):
    """direction +1 = buy grid (profits when price rises), -1 = sell grid.
    step_points: grid spacing in POINTS (XAUUSD: 100 points = $1)."""
    step_usd = step_points * POINT
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy();  c = df["close"].to_numpy()
    n = len(df)

    balance = capital
    entries = []   # list of (entry_price, lots)
    def open_level(price, lots): entries.append((price, lots))

    # start first basket at first bar open
    open_level(o[0], init_lot)
    last_entry = o[0]
    min_equity = capital
    min_margin_level = 1e9
    max_levels_reached = 1
    max_lots = init_lot
    baskets_closed = 0
    stopout = False

    for i in range(n):
        # adverse extreme for this basket within the bar
        adverse = l[i] if direction == +1 else h[i]      # worst price for the basket
        favour  = h[i] if direction == +1 else l[i]      # best price

        # 1) add martingale levels as price moves against us through steps
        while len(entries) < max_levels:
            trigger = last_entry - direction * step_usd    # buy: below; sell: above
            crossed = (adverse <= trigger) if direction == +1 else (adverse >= trigger)
            if not crossed:
                break
            next_lot = entries[-1][1] * lot_mult
            open_level(trigger, next_lot)
            last_entry = trigger
            max_levels_reached = max(max_levels_reached, len(entries))

        total_lots = sum(x[1] for x in entries)
        max_lots = max(max_lots, total_lots)

        # 2) stress equity at the adverse extreme (margin / stopout check)
        float_adv = sum(direction * lots * CONTRACT * (adverse - ep) for ep, lots in entries)
        margin = sum(lots * CONTRACT * adverse for _, lots in entries) / leverage
        equity_adv = balance + float_adv
        mlevel = (equity_adv / margin * 100) if margin > 0 else 1e9
        min_equity = min(min_equity, equity_adv)
        min_margin_level = min(min_margin_level, mlevel)
        if mlevel < STOPOUT_LEVEL or equity_adv <= 0:
            stopout = True
            break

        # 3) take-profit for the basket at the favourable extreme
        float_fav = sum(direction * lots * CONTRACT * (favour - ep) for ep, lots in entries)
        if float_fav >= target_usd:
            balance += float_fav
            baskets_closed += 1
            entries = []
            open_level(c[i], init_lot)   # restart at close
            last_entry = c[i]

    # close any open basket at final price (mark to market on close)
    if entries and not stopout:
        balance += sum(direction * lots * CONTRACT * (c[-1] - ep) for ep, lots in entries)

    return {
        "dir": "buy" if direction == +1 else "sell",
        "survived": not stopout,
        "final_balance": round(balance, 0),
        "return_%": round((balance - capital) / capital * 100, 1),
        "baskets_closed": baskets_closed,
        "max_levels": max_levels_reached,
        "max_total_lots": round(max_lots, 4),
        "min_equity": round(min_equity, 0),
        "min_margin_level_%": round(min_margin_level, 0),
    }


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_15m_real.csv"
    import signal_xauusd_meanrev as S
    df = S.load_csv(path)
    print(f"data: {path}  {len(df):,} bars  {df.index[0].date()}->{df.index[-1].date()}  "
          f"price ${df['close'].min():.0f}-{df['close'].max():.0f}\n")

    print(f"(XAUUSD: 1 point = ${POINT}; 100 points = $1; step 2000 points = $20)\n")
    hdr = f"{'stepPts':>7} {'=$':>5} {'mult':>4} {'tgt$':>5} {'maxLv':>5} {'dir':>4} | " \
          f"{'survive':>7} {'ret%':>7} {'baskets':>7} {'peakLots':>8} {'minMargin%':>10} {'minEquity':>10}"
    print(hdr); print("-" * len(hdr))
    combos = [   # (step_points, lot_mult, target_usd, max_levels)
        (1000, 2.0, 50, 10), (1000, 2.0, 50, 15),
        (2000, 2.0, 50, 12), (1000, 1.5, 50, 15),
        (2000, 1.5, 50, 20), (3000, 1.5, 100, 20),
        (1000, 1.0, 20, 30), (2000, 1.0, 30, 50),   # mult=1 => not martingale (linear grid)
    ]
    for step_pts, mult, tgt, mx in combos:
        for d in (+1, -1):
            r = simulate(df, direction=d, step_points=step_pts, lot_mult=mult,
                         target_usd=tgt, max_levels=mx)
            print(f"{step_pts:>7} {step_pts*POINT:>5.0f} {mult:>4} {tgt:>5} {mx:>5} {r['dir']:>4} | "
                  f"{('YES' if r['survived'] else 'STOPOUT'):>7} {r['return_%']:>7} "
                  f"{r['baskets_closed']:>7} {r['max_total_lots']:>8} "
                  f"{r['min_margin_level_%']:>10} {r['min_equity']:>10}")
