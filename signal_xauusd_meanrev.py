#!/usr/bin/env python3
"""
Mean Reversion with Incremental Entry — XAUUSD 15M
Production signal engine (Python side of the Line of Trust).

Spec: docs/spec.md | Original: HedgerLabs (TradingView)

Anti look-ahead rules:
  * All decisions use the PREVIOUS closed bar (shift(1)).
  * Execution happens at the CURRENT bar's open.

CLI:
  python signal_xauusd_meanrev.py <data.csv> --emit-signals   # timestamp,pos_units (parity check)
  python signal_xauusd_meanrev.py <data.csv> --latest         # JSON of latest target position
"""

import json
import sys

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- parameters
DEFAULT_PARAMS = {
    "sma_length": 200,
    "initial_distance": 0.50,   # percent
    "step_distance": 0.25,      # percent
    "max_entries": 5,
}

DEFAULT_COSTS = {
    "fee_pct": 0.10,        # per side, percent
    "slippage_pct": 0.02,   # per side, percent
}


# ---------------------------------------------------------------- data loading
def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV CSV (TradingView / MT5 / generic). Returns UTC-indexed df."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next(c for c in ("time", "timestamp", "date", "datetime") if c in df.columns)
    t = df[tcol]
    if np.issubdtype(t.dtype, np.number):
        unit = "s" if t.iloc[0] < 1e12 else "ms"
        idx = pd.to_datetime(t, unit=unit, utc=True)
    else:
        idx = pd.to_datetime(t, utc=True, format="mixed")
    out = df[["open", "high", "low", "close"]].copy()
    out["volume"] = df["volume"] if "volume" in df.columns else 0.0
    out.index = idx
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out.astype(float)


# ---------------------------------------------------------------- signal engine
def compute_positions(df: pd.DataFrame, params: dict) -> pd.Series:
    """
    Returns target position in units (signed int) HELD DURING each bar,
    decided from the previous closed bar, executed at this bar's open.
    +k = k long entries stacked, -k = k short entries, 0 = flat.
    """
    n = int(params["sma_length"])
    init_d = float(params["initial_distance"])
    step_d = float(params["step_distance"])
    max_e = int(params["max_entries"])

    close = df["close"].to_numpy()
    sma = pd.Series(close).rolling(n).mean().to_numpy()
    dist = (close - sma) / sma * 100.0  # percent

    pos = np.zeros(len(df), dtype=np.int64)
    side, k = 0, 0  # current side (+1/-1/0), entries stacked
    for i in range(1, len(df)):
        d = dist[i - 1]          # previous CLOSED bar   (shift(1))
        if np.isnan(d):
            pos[i] = 0
            continue
        c_prev, s_prev = close[i - 1], sma[i - 1]

        if side == 1 and c_prev >= s_prev:      # exit long at SMA touch
            side, k = 0, 0
        elif side == -1 and c_prev <= s_prev:   # exit short at SMA touch
            side, k = 0, 0

        if side == 0:
            if d <= -init_d:
                side, k = 1, 1
            elif d >= init_d:
                side, k = -1, 1
        elif side == 1 and k < max_e:
            if d <= -(init_d + k * step_d):     # price fell further -> add
                k += 1
        elif side == -1 and k < max_e:
            if d >= (init_d + k * step_d):
                k += 1

        pos[i] = side * k
    return pd.Series(pos, index=df.index, name="pos_units")


# ---------------------------------------------------------------- backtest
def backtest(df: pd.DataFrame, params: dict = None, costs: dict = None,
             per_entry_notional: float = 1_000.0, initial_capital: float = 10_000.0):
    """Event backtest from the position series. Returns (trades_df, equity, metrics)."""
    params = {**DEFAULT_PARAMS, **(params or {})}
    costs = {**DEFAULT_COSTS, **(costs or {})}
    cost_side = (costs["fee_pct"] + costs["slippage_pct"]) / 100.0

    pos = compute_positions(df, params).to_numpy()
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    idx = df.index

    trades = []           # completed round-trips
    entries = []          # open entry prices (abs)
    side = 0
    equity = np.full(len(df), initial_capital, dtype=float)
    realized = 0.0

    for i in range(len(df)):
        p, prev = pos[i], (pos[i - 1] if i else 0)
        if p != prev:
            fill = opens[i]
            if side != 0 and (p == 0 or np.sign(p) != side):
                # close whole stack at fill
                pnl = sum(side * (fill - e) / e * per_entry_notional for e in entries)
                fees = cost_side * per_entry_notional * len(entries) * 2
                realized += pnl - fees
                trades.append({
                    "exit_time": idx[i], "side": "long" if side == 1 else "short",
                    "n_entries": len(entries), "avg_entry": float(np.mean(entries)),
                    "exit": fill, "pnl": pnl - fees,
                })
                entries, side = [], 0
            if p != 0:
                side = int(np.sign(p))
                while len(entries) < abs(p):
                    entries.append(fill)
        elif p != 0 and abs(p) > len(entries):
            entries.extend([opens[i]] * (abs(p) - len(entries)))

        unreal = sum(side * (closes[i] - e) / e * per_entry_notional for e in entries)
        equity[i] = initial_capital + realized + unreal

    trades_df = pd.DataFrame(trades)
    eq = pd.Series(equity, index=idx, name="equity")
    metrics = _metrics(trades_df, eq, df, initial_capital)
    return trades_df, eq, metrics


def _metrics(trades: pd.DataFrame, eq: pd.Series, df: pd.DataFrame, cap0: float) -> dict:
    m = {"trade_count": int(len(trades))}
    if len(trades):
        wins = trades[trades.pnl > 0]
        losses = trades[trades.pnl <= 0]
        m["win_rate_pct"] = round(len(wins) / len(trades) * 100, 2)
        aw = wins.pnl.mean() if len(wins) else 0.0
        al = abs(losses.pnl.mean()) if len(losses) else np.nan
        m["avg_rr"] = round(aw / al, 2) if al and not np.isnan(al) else float("inf")
        gp, gl = wins.pnl.sum(), abs(losses.pnl.sum())
        m["profit_factor"] = round(gp / gl, 2) if gl else float("inf")
        total_profit = trades.pnl.sum()
        m["total_return_pct"] = round(total_profit / cap0 * 100, 2)
        m["max_single_trade_share_pct"] = (
            round(wins.pnl.max() / gp * 100, 2) if len(wins) and gp > 0 else 0.0
        )
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    m["max_drawdown_pct"] = round(dd.min(), 2)
    m["buy_hold_return_pct"] = round(
        (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100, 2
    )
    m["final_equity"] = round(float(eq.iloc[-1]), 2)
    return m


# ---------------------------------------------------------------- CLI
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    df = load_csv(argv[1])
    if "--emit-signals" in argv:
        pos = compute_positions(df, DEFAULT_PARAMS)
        out = pd.DataFrame({"timestamp": (df.index.view("int64") // 10**9), "pos": pos.to_numpy()})
        sys.stdout.write(out.to_csv(index=False))
    elif "--latest" in argv:
        pos = compute_positions(df, DEFAULT_PARAMS)
        print(json.dumps({
            "time": str(df.index[-1]),
            "close": float(df["close"].iloc[-1]),
            "target_pos_units": int(pos.iloc[-1]),
            "params": DEFAULT_PARAMS,
        }, indent=2))
    else:
        _, _, metrics = backtest(df)
        print(json.dumps(metrics, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
