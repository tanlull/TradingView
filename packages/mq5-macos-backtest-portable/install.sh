#!/usr/bin/env bash
set -euo pipefail

src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${CODEX_HOME:-$HOME/.codex}/skills"

mkdir -p "$target"
rm -rf "$target/mq5-macos-backtest"
cp -R "$src_dir/mq5-macos-backtest" "$target/"

echo "Installed mq5-macos-backtest to $target/mq5-macos-backtest"
echo 'Use it in Codex with: Use $mq5-macos-backtest to compile and backtest this MQ5 EA on macOS MT5.'
