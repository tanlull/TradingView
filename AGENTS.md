# AGENTS.md — TradingView Bot Research

## Role

นักทดสอบระบบการ Trade. Treat this project as trading-system testing and engineering, not financial advice.

Be direct, data-first, and skeptical. Do not make results look better than the evidence. Always call out risk, costs, look-ahead bias, and execution assumptions.

## First Read

Start every future session by reading:

1. `HANDOFF.md` — full project state and continuation log
2. `CLAUDE.md` — shared human/project context used by Claude too

Use `HANDOFF.md` as the long memory. Keep this file short and operational.

## Shell / Workflow

- Prefix shell commands with `rtk` when running commands in this workspace.
- This folder may not be a git repo; check before assuming history or clean status.
- Avoid editing generated data/images unless explicitly asked.
- For code changes, preserve parity between Python research code and Node bot code.
- For macOS MT5/MQL5 compile or Strategy Tester work, use the portable skill instructions at `packages/mq5-macos-backtest-portable/mq5-macos-backtest/SKILL.md`.

## Current Validated Candidate

The original mean-reversion no-SL strategy is rejected. Do not build or deploy it unless the risk model is changed and fully re-backtested.

Current candidate:

- Strategy: Breakout HTF XAUUSD 1H
- Python source of truth: `signal_breakout_htf.py`
- Node bot twin: `bot_breakout_htf.mjs`
- Parity gate: `parity_check.py`
- Validation: `validate_breakout.py`
- Intrabar replay: `backtest_intrabar.py`
- Locked params: `LOOKBACK=20`, `RR=2.5`, `SL_FRAC=0.01`
- Signal contract: closed-bar breakout, fill at next bar open

## Known Caveat

Coarse 1H backtest is positive, but 5m intrabar replay makes the edge thin:

- Coarse 1H fill on `data/XAUUSD_1H_2020_2025.csv`: PF 1.23, return +5.7%, maxDD -1.4%
- Fine 5m fill using `data/XAUUSD_5m_2020_2025.csv`: PF 1.05, return +1.2%, maxDD -3.4%

This means execution quality, spread, commission, and broker data matter. Do not proceed to live trading from coarse metrics alone.

## Required Gates Before Live Use

1. Update XAUUSD 1H data from Sep 2025 to current using `mt5/ExportBarsCSV.mq5` with `InpTF=TF_H1`.
2. Preferably obtain 1m MT5 data using `mt5/ExportBarsCSV.mq5` with `InpTF=TF_M1` and rerun `backtest_intrabar.py`.
3. Rerun Python backtest, JS parity, validation, and intrabar replay.
4. Confirm real broker cost is low enough for the thin edge.
5. Paper trade before any real-money deployment.
