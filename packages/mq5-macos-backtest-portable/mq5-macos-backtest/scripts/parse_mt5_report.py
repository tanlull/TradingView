#!/usr/bin/env python3
"""Parse MetaTrader 5 Strategy Tester HTML reports into compact metrics.

Usage:
  python3 parse_mt5_report.py report1.htm report2.htm
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cells: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.replace("\xa0", " ").split())
        if text:
            self.cells.append(text)


KEYS = [
    "Expert:",
    "Symbol:",
    "Period:",
    "Company:",
    "Currency:",
    "Initial Deposit:",
    "Leverage:",
    "History Quality:",
    "Bars:",
    "Ticks:",
    "Total Net Profit:",
    "Gross Profit:",
    "Gross Loss:",
    "Profit Factor:",
    "Expected Payoff:",
    "Recovery Factor:",
    "Sharpe Ratio:",
    "Balance Drawdown Maximal:",
    "Equity Drawdown Maximal:",
    "Balance Drawdown Relative:",
    "Equity Drawdown Relative:",
    "Total Trades:",
    "Short Trades (won %):",
    "Long Trades (won %):",
    "Profit Trades (% of total):",
    "Loss Trades (% of total):",
    "Maximum consecutive wins ($):",
    "Maximum consecutive losses ($):",
    "Maximal consecutive profit (count):",
    "Maximal consecutive loss (count):",
    "Average consecutive wins:",
    "Average consecutive losses:",
]


def decode_report(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-16", "utf-16le", "utf-8", "cp1252", "latin1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_report(path: Path) -> dict[str, str]:
    parser = _TextParser()
    parser.feed(decode_report(path))
    cells = parser.cells
    out: dict[str, str] = {"file": str(path)}
    for key in KEYS:
        label = key[:-1]
        for idx, cell in enumerate(cells):
            if cell == key and idx + 1 < len(cells):
                out[label] = cells[idx + 1]
                break
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    rows = [parse_report(Path(arg)) for arg in argv[1:]]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
