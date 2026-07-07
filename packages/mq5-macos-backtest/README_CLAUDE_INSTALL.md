# mq5-macos-backtest for Claude

Use this package when Claude cannot install the `.skill` file.

## Install

1. Upload `mq5-macos-backtest-claude.zip` to Claude Skills.
2. The ZIP contains `mq5-macos-backtest/Skill.md`, which is the Claude-friendly entry file.
3. If Claude still rejects the upload, open `mq5-macos-backtest/Skill.md` and paste its content into the project `CLAUDE.md` as a fallback.

## Contents

- `mq5-macos-backtest/Skill.md` - Claude skill instructions
- `mq5-macos-backtest/SKILL.md` - Codex-compatible copy
- `mq5-macos-backtest/scripts/parse_mt5_report.py` - MT5 HTML report parser
- `mq5-macos-backtest/agents/openai.yaml` - portable metadata

## Notes

This skill assumes macOS MetaTrader 5 under MetaQuotes Wine, and a project similar to `/Users/tan/git/TradingView`.
