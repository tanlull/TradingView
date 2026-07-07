#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_backtest.sh — compile + Strategy-Test ea_breakout_htf on macOS MT5
#
# Replicates the "MQ5 macOS Backtest" workflow (Wine/CrossOver + CLI + .ini,
# Model=4 real ticks). RUN THIS ON YOUR MAC — it needs your Wine/MT5 install.
#
#   bash mt5/run_backtest.sh
#
# What it does:
#   1. finds your MT5 install (net.metaquotes.wine / CrossOver bottle / .app)
#   2. copies ea_breakout_htf.mq5 into the terminal's MQL5/Experts
#   3. compiles it with metaeditor64.exe (deterministic CLI, no UI clicks)
#   4. runs terminal64.exe /config:strategy_tester.ini  (Model=4 real ticks)
#   5. tells you where the HTML report landed
# ---------------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"          # .../TradingView/mt5
# use the real-ticks (Model=4) config the Codex skill generated; override with $1
INI="${1:-$HERE/tester_ea_breakout_htf_balanced_realticks.ini}"
# EA name (no extension); override with $2 — e.g. ea_breakout_htf_ecma
EA_NAME="${2:-ea_breakout_htf}"
EA_SRC="$HERE/$EA_NAME.mq5"
[ -f "$EA_SRC" ] || { echo "!! EA source not found: $EA_SRC"; exit 1; }

echo "==> locating MT5 (Wine/CrossOver) ..."
CANDIDATES=(
  "$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5"
  "$HOME/Library/Application Support/CrossOver/Bottles/MetaTrader 5/drive_c/Program Files/MetaTrader 5"
  "$HOME/Library/Application Support/CrossOver/Bottles/MT5/drive_c/Program Files/MetaTrader 5"
  "/Applications/MetaTrader 5.app/Contents/SharedSupport/metatrader5/drive_c/Program Files/MetaTrader 5"
)
MT5DIR=""
for c in "${CANDIDATES[@]}"; do
  if [ -f "$c/terminal64.exe" ]; then MT5DIR="$c"; break; fi
done
if [ -z "$MT5DIR" ]; then
  echo "!! MT5 not found in the common paths. Find it yourself with:"
  echo '   find ~ /Applications -name terminal64.exe 2>/dev/null'
  echo "   then set MT5DIR at the top of this script."
  exit 1
fi
echo "    found: $MT5DIR"

# pick the wine runner (CrossOver's wine or a system wine)
WINE="$(command -v wine || true)"
CX="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine"
[ -x "$CX" ] && WINE="$CX"
if [ -z "$WINE" ]; then
  echo "!! no 'wine' found. If you use CrossOver, open the bottle and run the"
  echo "   two commands below from inside it; otherwise install wine."
fi

# locate the MQL5 tree (portable install keeps it next to terminal64.exe;
# otherwise it's under the wine user's AppData\Roaming\MetaQuotes\Terminal\<hash>)
MQL5="$MT5DIR/MQL5"
[ -d "$MQL5/Experts" ] || MQL5="$(dirname "$(find "$HOME/Library/Application Support" -path '*MQL5/Experts' -type d 2>/dev/null | head -1)")"
echo "==> copying EA into $MQL5/Experts"
mkdir -p "$MQL5/Experts"
cp "$EA_SRC" "$MQL5/Experts/"

echo "==> compiling (metaeditor64.exe /compile) ..."
"$WINE" "$MT5DIR/metaeditor64.exe" /compile:"$MQL5/Experts/$EA_NAME.mq5" /log || true
echo "    (check MQL5/Experts/$EA_NAME.log for errors; .ex5 = success)"
# keep a copy of the .ex5 next to the repo source for versioning
[ -f "$MQL5/Experts/$EA_NAME.ex5" ] && cp "$MQL5/Experts/$EA_NAME.ex5" "$HERE/" && echo "    copied $EA_NAME.ex5 back to repo mt5/"

echo "==> running Strategy Tester (Model=4 real ticks) ..."
cp "$INI" "$MT5DIR/strategy_tester.ini"
"$WINE" "$MT5DIR/terminal64.exe" /config:"$MT5DIR/strategy_tester.ini"

echo "==> done. HTML report is named per the .ini 'Report=' line (in $MT5DIR)."
echo "    เทียบตัวเลขกับ backtest_multi.py (Balanced ควรได้ ~PF 1.40 / DD ~-1.3%)"
echo "    เปลี่ยน preset: bash run_backtest.sh tester_ea_breakout_htf_aggressive_realticks.ini"
echo "    EA ตัว EC-MA:   bash run_backtest.sh mt5/tester_ea_breakout_htf_ecma_balanced_realticks.ini ea_breakout_htf_ecma"
