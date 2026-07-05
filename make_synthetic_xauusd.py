#!/usr/bin/env python3
"""
Synthetic XAUUSD 15m OHLCV generator  ——  SMOKE-TEST DATA ONLY.

!!! WARNING !!!
This is ARTIFICIAL data used only to exercise the backtest pipeline
(equity curve, drawdown, robustness surface). It is NOT real gold price.
DO NOT use any metric produced from this file to judge the strategy's
real edge or to make a go/no-go verdict.

Model: Ornstein-Uhlenbeck mean reversion around a slow random-walk "fair value",
with gold-like 15m volatility and intrabar high/low wicks. Deterministic seed
so the pipeline is reproducible.
"""
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 20260704
BARS = 12_000          # ~125 trading days of 15m bars (24h market)
START = "2025-01-02 00:00:00"
P0 = 2050.0            # starting price level (USD/oz), gold-like


def make(seed: int = SEED, n: int = BARS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # slow-drifting "fair value" (random walk, tiny step)
    fair_step = rng.normal(0, 0.15, n).cumsum()
    fair = P0 + fair_step

    # OU mean-reverting deviation of close around fair value
    theta = 0.015         # reversion speed per bar
    sigma = 2.6           # shock stdev (USD) per 15m bar (larger swings -> more entries)
    dev = np.zeros(n)
    for i in range(1, n):
        dev[i] = dev[i - 1] * (1 - theta) + rng.normal(0, sigma)

    close = fair + dev
    # open = previous close + small gap
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1] + rng.normal(0, 0.2, n - 1)

    # wicks
    hi_wick = np.abs(rng.normal(0, 0.6, n))
    lo_wick = np.abs(rng.normal(0, 0.6, n))
    high = np.maximum(open_, close) + hi_wick
    low = np.minimum(open_, close) - lo_wick
    volume = rng.integers(500, 5000, n).astype(float)

    idx = pd.date_range(START, periods=n, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {"time": idx, "open": open_, "high": high, "low": low,
         "close": close, "volume": volume}
    )
    return df.round(2)


if __name__ == "__main__":
    out = "data/SYNTHETIC_xauusd_15m.csv"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df = make()
    df.to_csv(out, index=False)
    print(f"wrote {out}: {len(df)} bars, "
          f"{df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
    print(f"price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
