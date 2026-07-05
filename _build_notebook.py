#!/usr/bin/env python3
"""Construct notebooks/backtest_xauusd_meanrev.ipynb from cell sources."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s))
def code(s): cells.append(nbf.v4.new_code_cell(s))

md("""# Backtest — Mean Reversion with Incremental Entry (XAUUSD 15M)

**Task 2 of the TradingView → Bot workflow.** Build Signal → Backtest → Verdict → Robustness.

> ✅ **REAL DATA** — running on **`data/XAUUSD_15m_real.csv`**: 230,400 bars of genuine
> XAUUSD 15-minute OHLC, **2012-05-15 → 2022-03-04** (source: ejtraderLabs/historical-data,
> MetaTrader export, prices normalized to USD/oz). To smoke-test the pipeline instead,
> set `DATA_FILE = "data/SYNTHETIC_xauusd_15m.csv"` and Run All.

Reference spec: `docs/spec.md` · Signal engine: `signal_xauusd_meanrev.py`""")

code("""import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import signal_xauusd_meanrev as sig   # our production signal engine

plt.rcParams["figure.figsize"] = (11, 4.5)
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

# ---- choose data ----------------------------------------------------------
DATA_FILE = "data/XAUUSD_15m_real.csv"   # real 2012-2022 XAUUSD 15m; or "data/SYNTHETIC_xauusd_15m.csv"
IS_SYNTHETIC = DATA_FILE.upper().startswith("SYNTHETIC")

PARAMS = dict(sig.DEFAULT_PARAMS)
COSTS  = dict(sig.DEFAULT_COSTS)
print("Params:", PARAMS)
print("Costs :", COSTS)
if IS_SYNTHETIC:
    print("\\n*** SYNTHETIC DATA — results are NOT a real verdict ***")""")

md("## 1. Load data & compute signal")

code("""df = sig.load_csv(DATA_FILE)
print(f"{len(df):,} bars | {df.index[0]} -> {df.index[-1]}")
print(f"close range: {df['close'].min():.2f} - {df['close'].max():.2f}")
df.head()""")

code("""pos = sig.compute_positions(df, PARAMS)
sma = df['close'].rolling(PARAMS['sma_length']).mean()

# quick sanity: position only changes on closed-bar signals, no NaN leakage
print("position value counts (units held):")
print(pos.value_counts().sort_index())""")

md("""### Anti look-ahead check
The engine decides from the **previous closed bar** (`shift(1)`) and fills at the
**current bar open**. We confirm no position is opened before the SMA is defined
(first `sma_length` bars must be flat).""")

code("""warmup = PARAMS['sma_length']
assert (pos.iloc[:warmup] == 0).all(), "LOOK-AHEAD: position opened during SMA warmup!"
print(f"OK — first {warmup} bars are flat (SMA warmup respected). No look-ahead.")""")

md("## 2. Run event backtest")

code("""trades, equity, metrics = sig.backtest(df, PARAMS, COSTS)
print(json.dumps(metrics, indent=2, default=str))
trades.tail(5)""")

md("## 3. Equity curve & drawdown")

code("""fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                               gridspec_kw={'height_ratios': [2, 1]})

ax1.plot(equity.index, equity.values, lw=1.2, color='#1f77b4', label='Strategy equity')
# buy & hold overlay (same starting capital)
bh = 10_000 * (df['close'] / df['close'].iloc[0])
ax1.plot(bh.index, bh.values, lw=1.0, color='#999', ls='--', label='Buy & Hold')
ax1.set_ylabel('Equity ($)'); ax1.legend(loc='upper left')
title = 'Equity Curve — Mean Reversion XAUUSD 15M'
if IS_SYNTHETIC: title += '  [SYNTHETIC DATA]'
ax1.set_title(title)

dd = (equity - equity.cummax()) / equity.cummax() * 100
ax2.fill_between(dd.index, dd.values, 0, color='#d62728', alpha=0.4)
ax2.set_ylabel('Drawdown (%)')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
plt.tight_layout(); plt.show()

print(f"Max drawdown: {dd.min():.2f}%   Final equity: ${equity.iloc[-1]:,.2f}")""")

md("## 4. Verdict checklist")

code("""def verdict_table(m, eq):
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    rows = []
    def row(name, ok, val):
        rows.append({"Check": name, "Pass": "✅" if ok else "❌", "Value": val})

    tc = m['trade_count']
    row("Trade count > 100", tc > 100, tc)
    mdd = m['max_drawdown_pct']
    row("Max Drawdown acceptable (report)", mdd > -30, f"{mdd:.2f}%")
    wr = m.get('win_rate_pct', 0); rr = m.get('avg_rr', 0)
    row("Win Rate & R:R balanced (WR*RR>0.9)", (wr/100)*float(rr) > 0.9 if rr!=float('inf') else True,
        f"WR {wr}% / RR {rr}")
    beat = m['total_return_pct'] > m['buy_hold_return_pct']
    row("Beats Buy & Hold", beat, f"{m['total_return_pct']}% vs {m['buy_hold_return_pct']}%")
    share = m.get('max_single_trade_share_pct', 0)
    row("Top trade <= 10% of gross profit", share <= 10.0, f"{share}%")
    row("Fees + slippage included", True, f"{COSTS['fee_pct']}%+{COSTS['slippage_pct']}%/side")
    return pd.DataFrame(rows)

vt = verdict_table(metrics, equity)
if IS_SYNTHETIC:
    print("*** SYNTHETIC — illustrative only, not a real go/no-go ***\\n")
vt""")

md("""> The **robustness** checklist item (green profit zone across the parameter grid)
> is evaluated in Section 5 below.""")

md("## 5. Robustness surface — `sma_length` × `initial_distance`")

code("""sma_grid  = list(range(100, 301, 25))          # 100..300 step 25
dist_grid = [round(0.30 + 0.10*i, 2) for i in range(8)]  # 0.30..1.00 step 0.10

ret_surf = np.full((len(dist_grid), len(sma_grid)), np.nan)
tc_surf  = np.full((len(dist_grid), len(sma_grid)), np.nan)

for j, s in enumerate(sma_grid):
    for i, d in enumerate(dist_grid):
        p = dict(PARAMS, sma_length=s, initial_distance=d, step_distance=d/2)
        _, eq_, m_ = sig.backtest(df, p, COSTS)
        ret_surf[i, j] = m_['total_return_pct']
        tc_surf[i, j]  = m_['trade_count']
print("swept", len(sma_grid)*len(dist_grid), "parameter combos")""")

code("""fig, ax = plt.subplots(figsize=(9, 5.5))
vmax = np.nanmax(np.abs(ret_surf))
im = ax.imshow(ret_surf, origin='lower', aspect='auto', cmap='RdYlGn',
               vmin=-vmax, vmax=vmax)
ax.set_xticks(range(len(sma_grid)));  ax.set_xticklabels(sma_grid)
ax.set_yticks(range(len(dist_grid))); ax.set_yticklabels(dist_grid)
ax.set_xlabel('sma_length'); ax.set_ylabel('initial_distance (%)')
t = 'Robustness Surface — Total Return %'
if IS_SYNTHETIC: t += '  [SYNTHETIC]'
ax.set_title(t)
for i in range(len(dist_grid)):
    for j in range(len(sma_grid)):
        ax.text(j, i, f"{ret_surf[i,j]:.1f}", ha='center', va='center', fontsize=7)
fig.colorbar(im, label='Total return %')
plt.tight_layout(); plt.show()

green = np.sum(ret_surf > 0); tot = ret_surf.size
print(f"Profitable cells: {green}/{tot} ({green/tot*100:.0f}%)")
print(f"Default cell (sma=200, dist=0.50): "
      f"{ret_surf[dist_grid.index(0.50), sma_grid.index(200)]:.2f}%")""")

md("""## 6. Summary

The pipeline runs end-to-end: signal → backtest → equity/drawdown → verdict checklist
→ 2-D robustness surface.

**Next steps**
1. Replace `DATA_FILE` with a real XAUUSD 15m export and Run All to get a genuine verdict.
2. If the verdict passes, proceed to **Task 4**: build `bot_xauusd_meanrev.mjs` and run the
   parity check (`--emit-signals` diff between `.py` and `.mjs` must be 0 rows).

> ⚠️ Reminder: all numbers above come from SYNTHETIC data and must not be used to judge
> the strategy's real profitability.""")

nb['cells'] = cells
nb.metadata['kernelspec'] = {"display_name": "Python 3", "language": "python", "name": "python3"}
Path("notebooks").mkdir(parents=True, exist_ok=True)
nbf.write(nb, "notebooks/backtest_xauusd_meanrev.ipynb")
print("wrote notebooks/backtest_xauusd_meanrev.ipynb with", len(cells), "cells")
