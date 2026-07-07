---
name: mq5-macos-backtest
description: Compile MQL5/MQ5 Expert Advisors on macOS MT5/Wine and run MetaTrader 5 Strategy Tester backtests from CLI configs. Use when Codex needs to compile .mq5 to .ex5, copy EAs into MQL5/Experts, create MT5 tester .ini files, run "Every tick" or "Every tick based on real ticks" model, collect HTML/PNG reports, parse Strategy Tester metrics, or compare presets such as CONSERVATIVE/BALANCED/AGGRESSIVE on macOS.
---

# MQ5 macOS Backtest

## Overview

Use this workflow for MT5 on macOS where MetaTrader runs through Wine/CrossOver/MetaQuotes Wine. Prefer deterministic CLI compilation and Strategy Tester `.ini` files over manual UI clicks.

Always distinguish MT5 tester models:
- `Model=4`: Every tick based on real ticks.
- `Model=0`: Every tick.
- If the user asks for real ticks, use `Model=4`; only fall back to `Model=0` after reporting the exact blocker.

## Paths To Discover

Find the active MT5 install before acting. Common paths:

```bash
~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5
~/Library/Application Support/CrossOver/Bottles/MetaTrader 5/drive_c/Program Files/MetaTrader 5
/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine
```

Prefer the install that already contains the user's scripts/EAs or recent logs. Useful files:

```text
terminal64.exe
MetaEditor64.exe
MQL5/Experts/
MQL5/Scripts/
Logs/YYYYMMDD.log
MQL5/Logs/YYYYMMDD.log
Tester/cache/
```

## Compile Workflow

1. Locate the `.mq5` EA source.
2. Copy it into `MQL5/Experts/` when the user wants it available in MT5.
3. Compile with MetaEditor. The `Z:\Users\...` source path style often works better than `C:\Program Files\...` for repo files:

```bash
WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5" \
"/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" \
"C:\\Program Files\\MetaTrader 5\\MetaEditor64.exe" \
/compile:"Z:\\Users\\tan\\git\\TradingView\\mt5\\ea_breakout_htf.mq5" \
/log:"Z:\\Users\\tan\\git\\TradingView\\mt5\\ea_breakout_htf.compile.log"
```

4. Verify compile success by reading the log and confirming the `.ex5` exists. Do not trust process exit code alone.
5. Copy the compiled `.ex5` into `MQL5/Experts/` if compilation produced it beside the repo source.

Expected compile-log success line:

```text
Result: 0 errors, 0 warnings
```

## Tester Config

Create one `.ini` per preset/run. Keep configs in the project when possible, e.g. `mt5/tester_<ea>_<preset>_realticks.ini`.

Use this shape:

```ini
[Tester]
Expert=ea_breakout_htf.ex5
Symbol=XAUUSD
Period=H1
Optimization=0
Model=4
FromDate=2022.04.08
ToDate=2026.07.03
ForwardMode=0
Deposit=10000
Currency=USD
ProfitInPips=0
Leverage=2000
ExecutionMode=200
OptimizationCriterion=3
Visual=0
Report=ea_breakout_htf.CONSERVATIVE.XAUUSD.H1.20220408_20260703.realticks
ReplaceReport=1
ShutdownTerminal=1

[TesterInputs]
InpPreset=0||0||0||3||N
InpMagic=20260705||20260705||1||202607050||N
InpLookback=20||20||1||200||N
InpRR=2.5||2.5||0.1||10.0||N
InpSLpct=1.0||1.0||0.1||10.0||N
InpMaxOpen=1||1||1||10||N
InpSizeDecay=0.4||0.4||0.1||1.0||N
InpBaseLot=0.10||0.10||0.01||10.0||N
InpAllowLong=true||true||0||true||N
InpAllowShort=true||true||0||true||N
InpSlippage=20||20||1||200||N
```

Notes:
- `Expert` is relative to `MQL5/Experts/`.
- `Report` writes files in the MT5 root, not necessarily the project.
- Include `ShutdownTerminal=1` for unattended runs.
- Use `InpPreset` enum ordinals when known. Example for `ea_breakout_htf`: `0=CONSERVATIVE`, `1=BALANCED`, `2=AGGRESSIVE`.

## Run Strategy Tester

Run terminal with the config:

```bash
WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5" \
WINEDLLOVERRIDES="mmdevapi=d" \
"/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" \
"C:\\Program Files\\MetaTrader 5\\terminal64.exe" \
/portable /config:"Z:\\Users\\tan\\git\\TradingView\\mt5\\tester_ea_breakout_htf_conservative_realticks.ini"
```

Keep the exec session open until it exits. Poll logs while running:

```text
Logs/YYYYMMDD.log
MQL5/Logs/YYYYMMDD.log
```

Successful tester log lines look like:

```text
Tester automatical testing started
Tester last test passed with result "successfully finished"
```

Known MT5/Wine noise that can usually be ignored if reports are produced:

```text
ToolbarWindowProc unknown msg
mmdevapi.dll couldn't load
RtlLeaveCriticalSection section ... is not acquired
```

Real-tick blocker to report exactly:

```text
XAUUSD: received too many containers without changes [51]
```

## Collect And Parse Reports

Copy report artifacts from MT5 root into the project:

```bash
mkdir -p reports/mt5
cp "$MT5_ROOT"/ea_name*.htm reports/mt5/
cp "$MT5_ROOT"/ea_name*.png reports/mt5/
```

Use `scripts/parse_mt5_report.py` to extract metrics from UTF-16 MT5 HTML reports:

```bash
python3 ~/.codex/skills/mq5-macos-backtest/scripts/parse_mt5_report.py reports/mt5/*.htm
```

Report at least:
- model: `Every tick based on real ticks` or `Every tick`
- initial deposit/capital
- initial lot and lot ladder
- period, history quality, bars, ticks
- net profit, gross profit/loss, profit factor, expected payoff
- balance/equity drawdown
- total trades, win rate, consecutive wins/losses
- links to HTML reports

## Preset Lot Ladder Pattern

For EAs using `lot = BaseLot * SizeDecay^k`, compute the likely sequence with the broker lot step and the EA's `NormalizeDouble(..., 2)` behavior.

Example with `BaseLot=0.10`:

```text
CONSERVATIVE: MaxOpen=1, SizeDecay=0.4 -> 0.10 total 0.10
BALANCED:     MaxOpen=3, SizeDecay=0.4 -> 0.10, 0.04, 0.02 total 0.16
AGGRESSIVE:   MaxOpen=5, SizeDecay=0.8 -> 0.10, 0.08, 0.06, 0.05, 0.04 total 0.33
```

## Integrity Checks

- Verify `.ex5` timestamp/size after compile.
- Verify the tester report exists before claiming a run completed.
- Parse the report instead of relying on screenshots.
- If asked to compare runs, use reports from the same model/date/symbol/deposit/lot settings.
- State when history quality is not 100%, especially for real-tick tests.
