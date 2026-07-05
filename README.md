# TradingView Bot Research

XAUUSD trading-system research pipeline: TradingView idea -> Python signal/backtest -> Node bot twin -> parity check.

For the full project history and current continuation notes, read `HANDOFF.md`.

## Folder Layout

- `data/` — OHLCV CSV datasets and synthetic smoke-test data
- `data/mt5_raw/` — copied MT5 built-in history cache (`.hcc`), not directly used by Python backtests
- `docs/` — strategy specification and workflow documentation
- `docs/images/` — workflow screenshots
- `mt5/` — MetaTrader CSV export script
- `notebooks/` — generated Jupyter notebooks
- `reports/` — generated comparison CSVs
- `reports/figures/` — charts and validation images
- root `*.py` / `*.mjs` — executable research engines, validators, parity checks, and bot twin
- `AGENTS.md` / `CLAUDE.md` — short agent-specific operating instructions
- `HANDOFF.md` — long memory and latest project state

## Current Candidate

Current candidate is **Breakout HTF XAUUSD 1H**.

- Python source of truth: `signal_breakout_htf.py`
- Node bot twin: `bot_breakout_htf.mjs`
- Parity gate: `parity_check.py`
- Intrabar replay: `backtest_intrabar.py`

The original mean-reversion no-SL strategy is rejected unless its risk model is changed and fully re-tested.

## Smoke Commands

```bash
rtk python3 signal_breakout_htf.py data/XAUUSD_1H_2020_2025.csv
rtk python3 parity_check.py
rtk python3 backtest_intrabar.py
rtk python3 validate_breakout.py
```
# TradingView
