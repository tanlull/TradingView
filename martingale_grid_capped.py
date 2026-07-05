#!/usr/bin/env python3
"""
Grid-Martingale WITH risk controls, sized for $100k XAUUSD:
  - basket_sl_usd : hard stop on the whole basket's floating loss (caps ruin)
  - margin_cap_frac: never open a new level if projected margin > capital*frac
                     (this makes max_levels effectively money-limited, not wishful)

This converts martingale's "rare catastrophic loss" into "capped frequent losses",
so profitability becomes an honest expectancy question: do the many small basket
TPs outweigh the occasional basket-SL hits (a basket of many lots stopped out)?

Contract XAUUSD: 1 lot=100oz; 0.01 lot $1 move=$1. Margin=lots*100*price/leverage.
Within a bar: add levels at LOW, check basket-SL at LOW (worst), then TP at HIGH.
"""
import sys
import numpy as np

CONTRACT = 100.0
STOPOUT_LEVEL = 50.0


def simulate(df, direction=+1, init_lot=0.01, step_usd=20.0, lot_mult=1.5,
             target_usd=50.0, basket_sl_usd=3000.0, margin_cap_frac=0.30,
             max_levels=50, capital=100_000.0, leverage=100.0, spread_usd=0.0):
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy();  c = df["close"].to_numpy()
    n = len(df)
    margin_cap = capital * margin_cap_frac

    def basket_cost(ents):   # round-trip spread cost for all orders in the basket
        return sum(spread_usd * lots * CONTRACT for _, lots in ents)

    balance = capital
    entries = [(o[0], init_lot)]
    last_entry = o[0]
    tp_hits = sl_hits = 0
    worst_basket_loss = 0.0
    min_equity = capital
    true_stopout = False

    for i in range(n):
        adverse = l[i] if direction == +1 else h[i]
        favour  = h[i] if direction == +1 else l[i]

        # 1) add martingale levels (blocked by margin cap or max_levels)
        while len(entries) < max_levels:
            trigger = last_entry - direction * step_usd
            crossed = (adverse <= trigger) if direction == +1 else (adverse >= trigger)
            if not crossed:
                break
            next_lot = entries[-1][1] * lot_mult
            proj_lots = sum(x[1] for x in entries) + next_lot
            proj_margin = proj_lots * CONTRACT * adverse / leverage
            if proj_margin > margin_cap:      # margin guard: stop adding
                break
            entries.append((trigger, next_lot)); last_entry = trigger

        # 2) worst-case floating loss at adverse -> basket SL / stopout check
        float_adv = sum(direction * lots * CONTRACT * (adverse - ep) for ep, lots in entries)
        margin = sum(lots * CONTRACT * adverse for _, lots in entries) / leverage
        equity_adv = balance + float_adv
        min_equity = min(min_equity, equity_adv)
        mlevel = (equity_adv / margin * 100) if margin > 0 else 1e9
        if mlevel < STOPOUT_LEVEL or equity_adv <= 0:
            true_stopout = True; break
        if float_adv <= -basket_sl_usd:       # hard basket stop
            balance += float_adv - basket_cost(entries)
            sl_hits += 1
            worst_basket_loss = min(worst_basket_loss, float_adv)
            entries = [(c[i], init_lot)]; last_entry = c[i]
            continue

        # 3) basket take-profit at favour
        float_fav = sum(direction * lots * CONTRACT * (favour - ep) for ep, lots in entries)
        if float_fav >= target_usd + basket_cost(entries):
            balance += float_fav - basket_cost(entries); tp_hits += 1
            entries = [(c[i], init_lot)]; last_entry = c[i]

    if entries and not true_stopout:
        balance += sum(direction * lots * CONTRACT * (c[-1] - ep) for ep, lots in entries)

    return {
        "dir": "buy" if direction == +1 else "sell",
        "true_stopout": true_stopout,
        "return_%": round((balance - capital) / capital * 100, 1),
        "tp_baskets": tp_hits, "sl_baskets": sl_hits,
        "worst_basket_loss": round(worst_basket_loss, 0),
        "min_equity": round(min_equity, 0),
    }


if __name__ == "__main__":
    import signal_xauusd_meanrev as S
    d1 = S.load_csv("data/XAUUSD_15m_real.csv")
    d2 = S.load_csv("data/XAUUSD_15m_2020_2025.csv")

    # sweep: step, mult, target, basket_sl, margin_cap
    combos = [
        (20, 1.5, 50, 2000, 0.30), (20, 1.5, 50, 3000, 0.30),
        (20, 1.5, 100, 3000, 0.30), (30, 1.5, 100, 3000, 0.30),
        (20, 2.0, 50, 3000, 0.30), (20, 2.0, 50, 5000, 0.30),
        (30, 2.0, 100, 5000, 0.40), (20, 1.5, 50, 5000, 0.50),
        (40, 1.5, 100, 4000, 0.30), (30, 1.75, 80, 4000, 0.35),
    ]
    hdr = (f"{'step':>4}{'mult':>5}{'tgt':>5}{'bSL$':>6}{'mCap':>5} | "
           f"{'netRet%(4 runs)':>26} {'worstNet':>9} {'SLhits':>7} {'stopout?':>8}")
    print(hdr); print("-" * len(hdr))
    for step, mult, tgt, bsl, mcap in combos:
        runs = [simulate(df, direction=d, step_usd=step, lot_mult=mult, target_usd=tgt,
                         basket_sl_usd=bsl, margin_cap_frac=mcap)
                for df in (d1, d2) for d in (+1, -1)]
        rets = [r["return_%"] for r in runs]
        netsum = sum(rets)
        anyso = any(r["true_stopout"] for r in runs)
        slh = sum(r["sl_baskets"] for r in runs)
        print(f"{step:>4}{mult:>5}{tgt:>5}{bsl:>6}{mcap:>5} | "
              f"buy/sell 12-22: {rets[0]:>5},{rets[1]:>5}  20-25: {rets[2]:>5},{rets[3]:>5} "
              f"| Σ{netsum:>6} {slh:>7} {'YES' if anyso else 'no':>8}")
