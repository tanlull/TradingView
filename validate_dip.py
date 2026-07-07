#!/usr/bin/env python3
"""validate_dip.py — Buy-the-dip XAUUSD 1H : full validation (VERDICT: FAIL out-of-time)

Strategy tested (long): close > SMA200 AND close <= rolling20high*(1-DEPTH)
  -> enter next bar open, SL 1%, TP RR*SL, SL-first assumption, cost per round trip.
Short = mirror (close < SMA200 AND close >= rolling20low*(1+DEPTH)).

Result summary (2026-07-07, cost 0.03%/side):
  - Tuned window 2022-2026 : LONG PF 1.33 (+66.5%, DD -21.5%) ; 1M intrabar PF 1.26
  - UNSEEN    2020-2025    : LONG PF 1.17
  - UNSEEN    2012-2022    : LONG PF 0.91 (-26.5%, DD -37.8%)  <- FAIL
  - Robustness grid 2012-2022: green 1/16 combos  <- FAIL
  - SHORT: PF < 1 ทุกช่วง
  => edge เป็น regime-dependent (ขาขึ้นทอง 2021+) ไม่ใช่ structural edge
     ห้าม promote เป็นบอท ต่างจาก Breakout HTF ที่ผ่านทุกช่วง (1.12/1.22/1.25)

Usage:
  python3 validate_dip.py            # run full validation on project data files
"""
import pandas as pd, numpy as np

DATA = {
    "2012-2022 (unseen)": "data/XAUUSD_1H_real.csv",
    "2020-2025 (unseen)": "data/XAUUSD_1H_2020_2025.csv",
    "2022-2026 (tuned)":  "data/XAUUSD_1H_MT5_export_20220408_20260703.csv",
}
DEPTH, RR, SLF, COST = 0.005, 2.5, 0.01, 0.0006  # cost = round trip (0.03%/side)


def load(fp):
    df = pd.read_csv(fp)
    df.columns = [x.lower() for x in df.columns]
    tcol = [c for c in df.columns if "time" in c or "date" in c][0]
    df["time"] = pd.to_datetime(df[tcol], format="mixed")
    return df


def bt(df, depth=DEPTH, rr=RR, slf=SLF, cost=COST, side="long"):
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    sma = pd.Series(c).rolling(200).mean().values
    ref = (pd.Series(h).rolling(20).max() if side == "long"
           else pd.Series(l).rolling(20).min()).shift(1).values  # no look-ahead
    rets, i, n = [], 201, len(c)
    while i < n - 1:
        if side == "long":
            sig = c[i] > sma[i] and not np.isnan(ref[i]) and c[i] <= ref[i] * (1 - depth)
        else:
            sig = c[i] < sma[i] and not np.isnan(ref[i]) and c[i] >= ref[i] * (1 + depth)
        if sig:
            e = o[i + 1]
            sl = e * (1 - slf) if side == "long" else e * (1 + slf)
            tp = e * (1 + slf * rr) if side == "long" else e * (1 - slf * rr)
            j = i + 1
            while j < n:  # conservative: SL checked before TP
                if side == "long":
                    if l[j] <= sl: rets.append((sl - e) / e - cost); break
                    if h[j] >= tp: rets.append((tp - e) / e - cost); break
                else:
                    if h[j] >= sl: rets.append((e - sl) / e - cost); break
                    if l[j] <= tp: rets.append((e - tp) / e - cost); break
                j += 1
            else:
                break
            i = j
        i += 1
    r = np.array(rets)
    if not len(r):
        return 0, 0.0, 0.0, 0.0, 0.0
    eq = np.cumprod(1 + r); pk = np.maximum.accumulate(eq)
    w, L = r[r > 0], r[r <= 0]
    pf = w.sum() / -L.sum() if len(L) and L.sum() < 0 else float("inf")
    return len(r), len(w) / len(r) * 100, pf, (eq[-1] - 1) * 100, (eq / pk - 1).min() * 100


def main():
    dfs = {k: load(v) for k, v in DATA.items()}
    print("=== OUT-OF-TIME, locked config (depth0.5% rr2.5 SL1% SMA200) ===")
    for side in ("long", "short"):
        for name, df in dfs.items():
            n, wr, pf, ret, dd = bt(df, side=side)
            print(f"{side.upper():5s} {name:20s}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} "
                  f"ret {ret:+7.1f}% DD {dd:6.1f}%")
    print("\n=== Robustness grid, UNSEEN 2012-2022, long (PF) ===")
    old = dfs["2012-2022 (unseen)"]
    green = tot = 0
    rrs = [1.5, 2.0, 2.5, 3.0]
    print("depth\\rr  " + "  ".join(f"{r:4.1f}" for r in rrs))
    for d in (0.003, 0.005, 0.008, 0.012):
        row = []
        for r in rrs:
            _, _, pf, _, _ = bt(old, depth=d, rr=r)
            row.append(f"{pf:4.2f}"); tot += 1; green += pf > 1
        print(f"{d*100:4.1f}%    " + "  ".join(row))
    print(f"green {green}/{tot}")
    print("\n=== Cost stress, 2012-2022 (per-side) ===")
    for cs in (0.0003, 0.0005, 0.001):
        _, _, pf, ret, _ = bt(old, cost=cs * 2)
        print(f"cost {cs*100:.2f}%/side: PF {pf:.2f} ret {ret:+.1f}%")


if __name__ == "__main__":
    main()
