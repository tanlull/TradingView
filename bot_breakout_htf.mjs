#!/usr/bin/env node
/**
 * Breakout HTF — XAUUSD 1H — PRODUCTION bot (ESM, for Kung Trinity / OpenClaw).
 *
 * This is the JavaScript twin of signal_breakout_htf.py. The signal logic MUST
 * stay byte-for-byte identical — parity is enforced by parity_check.py
 * (--emit-signals output of both engines must diff to 0 rows).
 *
 * Signal contract (identical to the .py):
 *   For each CLOSED bar t, sig[t] in {-1,0,+1}:
 *     +1  close[t] > max(high[t-lookback .. t-1])   -> LONG next open
 *     -1  close[t] < min(low[t-lookback .. t-1])    -> SHORT next open
 *      0  otherwise ; warmup (first `lookback` bars) = 0
 *   Risk after fill at P: LONG SL=P*(1-SL_FRAC) TP=P*(1+SL_FRAC*RR); SHORT mirror.
 *
 * CLI:
 *   node bot_breakout_htf.mjs <data.csv> --emit-signals   # time,signal (parity stream)
 *   node bot_breakout_htf.mjs <data.csv> --latest         # JSON latest signal + levels
 */
import { readFileSync } from "node:fs";

// ---------------------------------------------------------------- params (LOCKED, mirror .py)
const LOOKBACK = 20;
const RR = 2.5;
const SL_FRAC = 0.01;

// ---------------------------------------------------------------- data
function load(path) {
  const text = readFileSync(path, "utf8");
  const lines = text.split(/\r?\n/).filter((ln) => ln.length > 0);
  const header = lines[0].split(",").map((s) => s.trim().toLowerCase());
  const idx = (names) => {
    for (const nm of names) { const i = header.indexOf(nm); if (i >= 0) return i; }
    return -1;
  };
  const ti = idx(["time", "timestamp", "date", "datetime"]);
  const oi = idx(["open"]), hi = idx(["high"]), li = idx(["low"]), ci = idx(["close"]);
  const time = [], open = [], high = [], low = [], close = [];
  for (let k = 1; k < lines.length; k++) {
    const p = lines[k].split(",");
    time.push(p[ti]);
    open.push(parseFloat(p[oi])); high.push(parseFloat(p[hi]));
    low.push(parseFloat(p[li]));  close.push(parseFloat(p[ci]));
  }
  return { time, open, high, low, close };
}

// ---------------------------------------------------------------- signal (anti look-ahead)
function computeSignals(high, low, close, lookback = LOOKBACK) {
  const n = close.length;
  const sig = new Array(n).fill(0);
  for (let i = lookback; i < n; i++) {
    let hh = -Infinity, ll = Infinity;
    for (let j = i - lookback; j < i; j++) {      // bars i-lookback .. i-1
      if (high[j] > hh) hh = high[j];
      if (low[j] < ll) ll = low[j];
    }
    if (close[i] > hh) sig[i] = 1;
    else if (close[i] < ll) sig[i] = -1;
  }
  return sig;
}

// ---------------------------------------------------------------- CLI
function main(argv) {
  const args = argv.slice(2);
  if (args.length < 1) { process.stdout.write("usage: bot_breakout_htf.mjs <data.csv> [--emit-signals|--latest]\n"); return 1; }
  const path = args[0];
  const d = load(path);
  const sig = computeSignals(d.high, d.low, d.close);

  if (args.includes("--emit-signals")) {
    let out = "time,signal\n";
    for (let i = 0; i < sig.length; i++) out += `${d.time[i]},${sig[i]}\n`;
    process.stdout.write(out);
  } else if (args.includes("--latest")) {
    const i = sig.length - 1;
    const s = sig[i], c = d.close[i];
    let lv = null;
    if (s === 1) lv = { side: "long", sl: +(c * (1 - SL_FRAC)).toFixed(3), tp: +(c * (1 + SL_FRAC * RR)).toFixed(3) };
    else if (s === -1) lv = { side: "short", sl: +(c * (1 + SL_FRAC)).toFixed(3), tp: +(c * (1 - SL_FRAC * RR)).toFixed(3) };
    process.stdout.write(JSON.stringify({
      time: d.time[i], close: c, signal: s,
      action: s ? "enter next bar open" : "flat",
      levels_ref_close: lv,
      params: { lookback: LOOKBACK, rr: RR, sl_frac: SL_FRAC },
    }, null, 2) + "\n");
  } else {
    process.stdout.write("specify --emit-signals or --latest\n");
  }
  return 0;
}

// NB: use exitCode (not process.exit) so large --emit-signals stdout writes flush fully.
process.exitCode = main(process.argv);
