#!/usr/bin/env python3
"""
Breakout HTF — XAUUSD 1H — PRODUCTION signal engine (Python side of the Line of Trust).

Validated config (see HANDOFF.md): Donchian breakout, lookback=20, R:R=2.5, SL=1%.
IS 2012-2018 PF 1.12 | OOS 2019-2022 PF 1.22 | fresh 2022-2025 PF 1.25.

Signal contract (what the bot consumes)
---------------------------------------
For each CLOSED bar t the engine emits sig[t] in {-1, 0, +1}:
  +1  close[t] breaks above the highest high of the prior `lookback` bars  -> go LONG
  -1  close[t] breaks below the lowest low  of the prior `lookback` bars  -> go SHORT
   0  no breakout
Execution happens at the OPEN of bar t+1 (next bar). Anti look-ahead: sig[t] uses
only bars <= t. Warmup (first `lookback` bars) always emits 0.

Risk model applied by the bot after an entry fill at price P:
  LONG : SL = P*(1-SL_FRAC)   TP = P*(1+SL_FRAC*RR)
  SHORT: SL = P*(1+SL_FRAC)   TP = P*(1-SL_FRAC*RR)
Intrabar priority: SL is checked before TP (conservative).

CLI
---
  python signal_breakout_htf.py <data.csv> --emit-signals   # time,signal  (parity stream)
  python signal_breakout_htf.py <data.csv> --latest         # JSON of the latest bar's signal
  python signal_breakout_htf.py <data.csv>                  # backtest metrics (verify edge)
"""
import csv
import json
import sys

# ------------------------------------------------------------------ params (LOCKED)
LOOKBACK = 20
RR = 2.5
SL_FRAC = 0.01
FEE_PCT = 0.05        # per side, percent (realistic gold)
SLIP_PCT = 0.00       # folded into FEE for this engine; keep explicit knob
RISK_NOTIONAL = 1000.0
CAP0 = 10000.0


# ------------------------------------------------------------------ data
def load(path):
    """Read OHLCV CSV, keep raw time strings. Returns dict of columns."""
    t, o, h, l, c, v = [], [], [], [], [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        cols = {k.lower(): k for k in r.fieldnames}
        tk = next(cols[x] for x in ("time", "timestamp", "date", "datetime") if x in cols)
        for row in r:
            t.append(row[tk])
            o.append(float(row[cols["open"]])); h.append(float(row[cols["high"]]))
            l.append(float(row[cols["low"]]));  c.append(float(row[cols["close"]]))
            v.append(float(row[cols["volume"]]) if "volume" in cols else 0.0)
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


# ------------------------------------------------------------------ signal (anti look-ahead)
def compute_signals(high, low, close, lookback=LOOKBACK):
    """sig[t] in {-1,0,1} from prior `lookback` bars' extremes vs close[t]."""
    n = len(close)
    sig = [0] * n
    for i in range(lookback, n):
        hh = max(high[i - lookback:i])   # bars i-lookback .. i-1
        ll = min(low[i - lookback:i])
        if close[i] > hh:
            sig[i] = 1
        elif close[i] < ll:
            sig[i] = -1
    return sig


# ------------------------------------------------------------------ backtest (verify edge)
def backtest(d, lookback=LOOKBACK, rr=RR, sl_frac=SL_FRAC):
    o, h, l, c = d["open"], d["high"], d["low"], d["close"]
    n = len(c)
    sig = compute_signals(h, l, c, lookback)
    cost_side = FEE_PCT / 100.0
    side = 0; entry = sl = tp = 0.0
    realized = 0.0; trades = []; eq = [CAP0] * n

    for i in range(n):
        # manage open position on this bar
        if side != 0:
            hit_sl = (l[i] <= sl) if side == 1 else (h[i] >= sl)
            hit_tp = (h[i] >= tp) if side == 1 else (l[i] <= tp)
            ex = None
            if hit_sl: ex = sl
            elif hit_tp: ex = tp
            if ex is not None:
                pnl = side * (ex - entry) / entry * RISK_NOTIONAL
                pnl -= cost_side * RISK_NOTIONAL * 2
                realized += pnl; trades.append(pnl); side = 0
        # new entry at THIS bar open from prior closed bar's signal
        if side == 0 and i > 0 and sig[i - 1] != 0:
            side = sig[i - 1]; entry = o[i]
            if side == 1:
                sl = entry * (1 - sl_frac); tp = entry * (1 + sl_frac * rr)
            else:
                sl = entry * (1 + sl_frac); tp = entry * (1 - sl_frac * rr)
        unreal = side * (c[i] - entry) / entry * RISK_NOTIONAL if side else 0.0
        eq[i] = CAP0 + realized + unreal

    wins = [p for p in trades if p > 0]; loss = [p for p in trades if p <= 0]
    gp = sum(wins); gl = -sum(loss)
    peak = eq[0]; mdd = 0.0
    for x in eq:
        peak = max(peak, x); mdd = min(mdd, (x - peak) / peak * 100)
    return {
        "trades": len(trades),
        "win_rate_%": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "profit_factor": round(gp / gl, 3) if gl else float("inf"),
        "total_return_%": round(sum(trades) / CAP0 * 100, 1),
        "max_drawdown_%": round(mdd, 1),
        "params": {"lookback": lookback, "rr": rr, "sl_frac": sl_frac, "fee_pct": FEE_PCT},
    }


# ------------------------------------------------------------------ CLI
def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    d = load(argv[1])
    sig = compute_signals(d["high"], d["low"], d["close"])
    if "--emit-signals" in argv:
        out = sys.stdout
        out.write("time,signal\n")
        for tm, s in zip(d["time"], sig):
            out.write(f"{tm},{s}\n")
    elif "--latest" in argv:
        i = len(sig) - 1
        s = sig[i]; c = d["close"][i]
        entry_ref = c  # bot fills at next open; use close as reference
        lv = None
        if s == 1:
            lv = {"side": "long", "sl": round(entry_ref * (1 - SL_FRAC), 3),
                  "tp": round(entry_ref * (1 + SL_FRAC * RR), 3)}
        elif s == -1:
            lv = {"side": "short", "sl": round(entry_ref * (1 + SL_FRAC), 3),
                  "tp": round(entry_ref * (1 - SL_FRAC * RR), 3)}
        print(json.dumps({
            "time": d["time"][i], "close": c, "signal": s,
            "action": "enter next bar open" if s else "flat",
            "levels_ref_close": lv,
            "params": {"lookback": LOOKBACK, "rr": RR, "sl_frac": SL_FRAC},
        }, indent=2))
    else:
        print(json.dumps(backtest(d), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
