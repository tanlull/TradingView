#!/usr/bin/env python3
"""
Parity check: signal_breakout_htf.py  vs  bot_breakout_htf.mjs

Runs --emit-signals on both engines over the same CSV and asserts the two signal
streams are IDENTICAL (0 differing rows). This is the 'Line of Trust' gate: the
live JS bot must produce exactly the signals the Python research engine validated.

Usage: python parity_check.py [data.csv]
Exit code 0 = parity OK, 1 = mismatch.
"""
import subprocess
import sys


def emit(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}:\n{r.stderr}", file=sys.stderr)
        sys.exit(2)
    return r.stdout.strip().splitlines()


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "data/XAUUSD_1H_2020_2025.csv"
    py = emit(["python3", "signal_breakout_htf.py", data, "--emit-signals"])
    js = emit(["node", "bot_breakout_htf.mjs", data, "--emit-signals"])

    print(f"python rows: {len(py)}   node rows: {len(js)}")
    if len(py) != len(js):
        print("❌ ROW COUNT MISMATCH"); sys.exit(1)

    diffs = [(i, a, b) for i, (a, b) in enumerate(zip(py, js)) if a != b]
    # signal distribution (from python, excl header)
    from collections import Counter
    dist = Counter(l.split(",")[1] for l in py[1:])
    print(f"signal distribution: {dict(sorted(dist.items()))}")

    if diffs:
        print(f"❌ {len(diffs)} DIFFERING ROWS. First 5:")
        for i, a, b in diffs[:5]:
            print(f"  line {i}: py='{a}'  js='{b}'")
        sys.exit(1)
    print(f"✅ PARITY OK — {len(py)-1} signal rows identical, 0 diffs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
