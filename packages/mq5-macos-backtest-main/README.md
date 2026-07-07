# mq5-macos-backtest

Claude-compatible skill package for MT5/MQL5 work on macOS.

## What It Does

- Compiles `.mq5` Expert Advisors with MetaEditor under MetaQuotes Wine.
- Copies EAs into the MT5 `MQL5/Experts` folder when needed.
- Builds Strategy Tester `.ini` files.
- Runs MT5 backtests from the command line.
- Supports "Every tick" and "Every tick based on real ticks" tester modes.
- Helps parse and compare MT5 Strategy Tester HTML reports.

## Install

Upload this ZIP to Claude Skills.

The archive intentionally follows this simple layout:

```text
mq5-macos-backtest-main/
  AGENTS.md
  LICENSE
  README.md
  SKILL.md
```

## Fallback

If Claude still rejects the ZIP, paste the content of `SKILL.md` into the project `CLAUDE.md`.
