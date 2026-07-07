# AGENTS.md

Use `SKILL.md` as the primary instruction file for this skill.

This skill is for compiling MQL5 Expert Advisors and running MetaTrader 5 Strategy Tester backtests on macOS through MetaQuotes Wine. Treat outputs as trading-system research evidence, not financial advice.

When using it:

- Preserve exact tester settings in generated `.ini` files.
- Record modelling mode, date range, symbol, timeframe, spread, deposit, leverage, lot settings, and report path.
- Prefer "Every tick based on real ticks" when the user requests real tick quality.
- Do not present backtest results as live-trading proof.
- Call out execution assumptions, cost sensitivity, broker data dependency, and risk.
