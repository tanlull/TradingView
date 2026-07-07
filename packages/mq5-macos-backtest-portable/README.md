# mq5-macos-backtest Portable Skill

This package contains the `mq5-macos-backtest` workflow for compiling `.mq5` Expert Advisors and running MetaTrader 5 Strategy Tester backtests on macOS/Wine.

## Contents

```text
mq5-macos-backtest/       Codex skill folder
adapters/AGENTS.md        Import bridge for Codex / Antigravity-style agents
adapters/CLAUDE.md        Import bridge for Claude
install.sh                Copies the skill into ~/.codex/skills
```

## Install For Codex

From this package folder:

```bash
./install.sh
```

Or manually:

```bash
mkdir -p ~/.codex/skills
cp -R mq5-macos-backtest ~/.codex/skills/
```

Then start a new Codex thread and use:

```text
Use $mq5-macos-backtest to compile and backtest this MQ5 EA on macOS MT5.
```

## Use With Antigravity / AGENTS.md

Copy `adapters/AGENTS.md` into the target project, or paste its contents into an existing `AGENTS.md`.

If the project already has an `AGENTS.md`, add this line near the top:

```text
@/absolute/path/to/mq5-macos-backtest/SKILL.md
```

## Use With Claude / CLAUDE.md

Copy `adapters/CLAUDE.md` into the target project, or paste its contents into an existing `CLAUDE.md`.

If Claude supports file imports in your setup, point it to:

```text
/absolute/path/to/mq5-macos-backtest/SKILL.md
```

Otherwise paste the contents of `mq5-macos-backtest/SKILL.md` into the project `CLAUDE.md`.

## Included Utility

Parse MT5 Strategy Tester HTML reports:

```bash
python3 mq5-macos-backtest/scripts/parse_mt5_report.py reports/mt5/*.htm
```

