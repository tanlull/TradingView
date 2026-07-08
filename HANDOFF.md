# HANDOFF — TradingView → Bot Workflow (Mean Reversion XAUUSD 15M)

> สถานะ ณ 2026-07-04 สำหรับส่งต่อให้แชทถัดไปทำต่อ
> อ้างอิงกระบวนการ: `docs/TradingView_to_Bot_Workflow.md`

## เป้าหมายรวม
แปลงกลยุทธ์ "Mean Reversion with Incremental Entry by HedgerLabs" (TradingView)
เป็นบอทเทรดจริง ผ่าน 4 ขั้น: Build Logic → Build Signal+Backtest → Verdict → Build Bot (.py + .mjs) + Parity Check

## การตัดสินใจที่ผู้ใช้ล็อกไว้แล้ว (อย่าถามซ้ำ)
- **Asset / Timeframe:** XAUUSD, 15 นาที
- **ทิศทาง:** Long + Short (สมมาตร)
- **ความเสี่ยง:** ตามต้นฉบับ = **ไม่มี SL/TP** (exit ที่ SMA touch เท่านั้น)
- **ต้นทุน:** Fee 0.10%/ข้าง + Slippage 0.02%/ข้าง
- พารามิเตอร์เริ่มต้น: sma_length=200, initial_distance=0.50%, step_distance=0.25%, max_entries=5/ฝั่ง

## ทำเสร็จแล้ว ✅
1. **`docs/spec.md`** — Build Logic เสร็จสมบูรณ์ (Task 1 ✅) มีทั้ง logic, params, anti-bias rules, acceptance criteria
2. **`signal_xauusd_meanrev.py`** — signal engine + event backtester + metrics เสร็จ
   - `compute_positions()` ใช้ `.shift(1)` กัน look-ahead, execute ที่ open แท่งถัดไป
   - รองรับ CLI: `--emit-signals` (สำหรับ parity), `--latest`, และ backtest (default)
   - ✅ **รันผ่านแล้วบนข้อมูล synthetic** (smoke-test)
3. **`notebooks/backtest_xauusd_meanrev.ipynb`** — Task 2 เสร็จ (รันแบบ smoke-test) ✅
   - 18 cells, รัน nbconvert ผ่าน 0 error, ฝังกราฟ 2 รูป (equity+drawdown, robustness heatmap)
   - มี: anti-look-ahead assert, equity vs Buy&Hold, drawdown, **verdict checklist table**,
     **robustness surface** sma_length(100–300) × initial_distance(0.30–1.00) = 72 combos
   - สลับข้อมูลจริงได้โดยแก้ตัวแปร `DATA_FILE` ในเซลล์แรก แล้ว Run All
4. **`data/XAUUSD_15m_real.csv`** — ✅ **ข้อมูลจริง** 230,400 แท่ง (2012-05-15 → 2022-03-04)
   - แหล่ง: github.com/ejtraderLabs/historical-data (MT export) — normalize ราคา ÷100 เป็น USD/oz
   - ผ่าน sanity: high≥low, OHLC-consistency 0 violations, spacing 15m (เว้นเสาร์-อาทิตย์)
   - **วิธีดึง:** `git clone --depth 1 https://github.com/ejtraderLabs/historical-data.git`
     (github.com อยู่ใน allowlist; raw.githubusercontent/yahoo/stooq ยัง blocked แต่ git clone ผ่าน)
5. **`make_synthetic_xauusd.py` + `data/SYNTHETIC_xauusd_15m.csv`** — ข้อมูลจำลองสำหรับ smoke-test เท่านั้น

## 🔴 VERDICT (ข้อมูลจริง 2012–2022) — กลยุทธ์ "ตก" ชัดเจน
| Check | ผล | ผ่าน? |
|---|---|---|
| Trade count > 100 | 1,255 | ✅ |
| Max Drawdown | **-102.6%** (พอร์ตติดลบ = ล้างพอร์ต) | ❌ |
| Win Rate / R:R | WR 67% แต่ RR 0.20 → PF 0.42 | ❌ |
| ชนะ Buy & Hold | return **-99.7%** vs B&H +26.7% | ❌ |
| Top trade ≤10% | 1.4% | ✅ |
| Fee+Slippage | คิดแล้ว (0.12%/ข้าง) | ✅ |
| Robustness surface | **เขียว 0/72 combos** (ทุกพารามิเตอร์ขาดทุน) | ❌ |

**สรุป:** Mean-Reversion แบบ "ไม่มี SL/TP" บนทองจริง 10 ปี = ระเบิดพอร์ต
ชนะบ่อย (67%) แต่กำไรจิ๊บ ๆ / พอเจอเทรนด์ทองแรง ๆ ไม้ซ้อน 5 ไม้ไม่กลับมาแตะ SMA → ขาดทุนหนักครั้งเดียวกินกำไรทั้งปี
**เป็นผลที่ robust** (ขาดทุนทุก 72 combo) → ไม่ใช่ปัญหาจูนพารามิเตอร์ แต่เป็นตัวคอนเซ็ปต์เอง

### ถ้าจะไปต่อ (ทางเลือกให้ผู้ใช้)
- เพิ่ม **Stop Loss / max adverse excursion cap** (แก้ที่ต้นเหตุ drawdown) แล้ว backtest ใหม่
- หรือ **ตีตกกลยุทธ์นี้** ตาม verdict — ไม่ควรเอาไปทำบอทจริง (Task 4) จนกว่าจะแก้ SL
- bash sandbox: allowlist เปิดเฉพาะ `pypi.org`, `files.pythonhosted.org`, `github.com`
  - BLOCKED: yahoo (query1.finance.yahoo.com), binance (api.binance.com), stooq.com, raw.githubusercontent.com
- `web_fetch` ดึง JSON/CSV ดิบไม่ได้ (คืนค่าว่าง — เรนเดอร์เฉพาะ HTML)

### ทางเลือกแก้ (ให้แชทถัดไปเลือก/ถามผู้ใช้)
1. **ผู้ใช้วางไฟล์ CSV เอง** ลงโฟลเดอร์ `/Users/tan/git/TradingView/` (คอลัมน์: time/open/high/low/close/volume)
   → แล้วรัน `python3 signal_xauusd_meanrev.py <file.csv>` ได้เลย (loader รองรับ TradingView/MT5 export)
2. หา dataset XAUUSD 15m ที่ host บน **github.com** (allowlisted) แล้ว pip/clone ลงมา
3. ใช้ `pip install` ดึง data package ที่ bundle ราคาทอง (ผ่าน pypi ได้)
4. สร้าง **synthetic OHLCV** สำหรับ smoke-test pipeline ก่อน (ระบุชัดว่าเป็นข้อมูลจำลอง ห้ามใช้ตัดสิน verdict จริง)

## งานที่เหลือ (ตามลำดับ)
- [x] **Task 2:** `notebooks/backtest_xauusd_meanrev.ipynb` — เสร็จ ✅
- [x] **Task 3 (Verdict บนข้อมูลจริง):** เสร็จ → **ผล = FAIL** (ดูตาราง VERDICT ด้านบน) ✅
- [ ] **ทางแยกการตัดสินใจ (รอผู้ใช้เลือก):** จะแก้ SL หรือเปลี่ยนกลยุทธ์ ก่อนไป Task 4
- [ ] **Task 4 (ระงับไว้ ⛔):** `bot_xauusd_meanrev.mjs` + Parity Check
      — **อย่าเพิ่งทำ** จนกว่าจะมีกลยุทธ์ที่ผ่าน verdict (ห้ามเอากลยุทธ์ที่ล้างพอร์ตไปรันบอทจริง)

## 📌 ทิศทางถัดไป — ผู้ใช้ถามหา "กลยุทธ์ win rate ดีกว่า"
**บทเรียนสำคัญที่ต้องย้ำ:** win rate สูงเป็นกับดัก — ตัวที่ตกไป WR 67% แต่ล้างพอร์ตเพราะ R:R=0.20
ตัวชี้วัดจริงคือ **expectancy = WR×avgWin − (1−WR)×avgLoss** ต้องเป็นบวก

**แคนดิเดตที่เสนอผู้ใช้ (เทสต์บน `data/XAUUSD_15m_real.csv` ด้วย pipeline เดิมได้เลย):**
1. **Mean Reversion + Stop Loss** ⭐แนะนำเริ่มก่อน — คอนเซ็ปต์เดิม + ใส่ SL/TP + ถือไม้เดียว
   → พิสูจน์ว่าปัญหาคือ "ไม่มี SL" จริงไหม (แก้ที่ต้นเหตุ drawdown -100%)
2. **Bollinger Band + RSI reversion** — แตะ BB ล่าง + RSI<30 ออกที่เส้นกลาง, มี SL ใต้ swing low
3. **EMA Pullback (trend-following)** — ย่อมาแตะ EMA20/50 ในเทรนด์แล้วเข้าตามเทรนด์
   (ทองชอบวิ่งเทรนด์ยาว = เหตุผลที่ mean-reversion เจ๊ง → ตัวนี้ได้เปรียบเชิงโครงสร้าง)
4. **VWAP reversion (intraday)** — เหวี่ยงห่าง VWAP มากแล้วคืนสู่ VWAP เหมาะกับ 15m

> ✅ เทสต์แล้ว 7 กลยุทธ์บนข้อมูลจริง (ดูผลด้านล่าง)

## 📊 ผลเทสต์กลยุทธ์ทั้งหมด (XAUUSD 15m จริง, 0.12%/ข้าง)
ทุกตัวใช้ fixed SL 1% + TP 2R → **R:R ล็อกที่ ~1.42** เท่ากันหมด ตัวแปรจริงคือ WR vs breakeven(~33%) + ต้นทุน

| กลยุทธ์ | WR | PF | Return | MaxDD |
|---|---|---|---|---|
| **C) Breakout40 2R** ⭐ | 39.8% | 0.94 | **-4.0%** | **-4.4%** |
| B) EMA-Pullback 2R | 34.9% | 0.76 | -15.2% | -15.7% |
| D) FVG 2R | 36.1% | 0.80 | -15.7% | -16.0% |
| E) SMC 2R | 35.1% | 0.77 | -17.1% | -17.1% |
| A) MeanRev+SL 2% | 54.0% | 0.40 | -50.6% | -51% |

**ข้อค้นพบ:**
- **Breakout ดีสุด** — เกือบคุ้มทุนที่ต้นทุน 0.12%/ข้าง, DD แค่ 4%
- **cost sensitivity (Breakout20):** คุ้มทุนที่ 0.08%/ข้าง → ต่ำกว่านั้นกำไร
  (0.02%/ข้าง = +11.5%, PF 1.19) → **ต้นทุนจริงของทอง ~0.02-0.04%/ข้าง = Breakout เป็นบวกจริง**
- **ADX>25 filter ทำให้แย่ลงทุกตัว** — พวกนี้เป็น breakout/trend อยู่แล้ว filter ตัดเทรดดีทิ้ง
  และขัดกับ pullback entry (pullback เกิดตอน ADX ต่ำ → กรองทิ้งเกือบหมด)
- WR สูง (MeanRev+SL 54%) = พอร์ตแย่สุด (ย้ำบทเรียน win-rate trap อีกรอบ)

**ไฟล์:** `strategies_compare.py` (A,B), `strategies_v2.py` (C,D,E,ADX),
`reports/strategy_comparison_v2.csv`, `reports/figures/strategy_equity_compare_v2.png`

**ทิศต่อไปที่มีลุ้น:** เอา Breakout ไปเทสต์บน 1H/4H (มีในรепо ejtraderLabs) — ต้นทุนต่อการเคลื่อนไหวเล็กลง

## 🎲 Martingale overlay (ทดสอบตามที่ผู้ใช้ขอ) — บน Breakout40, ต้นทุนจริง 0.03%/ข้าง
ไฟล์: `martingale_test.py`, `reports/figures/martingale_equity.png`
กติกา: แพ้ 1 ไม้ (SL) → คูณขนาดไม้ถัดไป × factor, ชนะ → reset. pnl+fee scale เชิงเส้น (แม่นยำ)

| Sizing | Final | MaxDD | Peak size | หมายเหตุ |
|---|---|---|---|---|
| **Flat (คงที่)** ⭐ | +12% | **-1.6%** | 1x | เส้นสวยสุด risk-adjusted ดีสุด |
| MG x2 no-cap | $57k | **-96%** | **1024x** | เกือบล้างพอร์ต — รอดเพราะ"ดวง"ของ history นี้ |
| MG x2 cap4 | +40% | -10.5% | 16x | แบบจำกัดชั้น |
| MG x1.5 no-cap | +58% | -12% | 58x | |

ที่ต้นทุนสเปก 0.12%/ข้าง: **MG x2 no-cap = 💥 RUINED** (แพ้ติด 9 ไม้ → 512x → พอร์ตแตก)

**สรุปตรง ๆ:** worst losing streak = 9–10 ไม้ (เกิดแน่นอนในทุกระบบ) → factor 2 = 512–1024x
- 1024x บนพอร์ต $10k = ต้องรับ notional ~$10.24M ต่อไม้เดียว → **เป็นไปไม่ได้จริง margin call = ล้างพอร์ต**
- ตัวเลข $57k เป็นภาพลวง (survivorship) — ลำดับราคาแย่กว่านี้นิดเดียว = ruin
- **martingale ไม่ได้แก้กลยุทธ์** — Breakout แบบ flat ก็ได้ +12% DD 1.6% อยู่แล้ว
  martingale แค่เอาเส้นสวย ๆ ไปแลกกับโอกาสล้างพอร์ต → ไม่คุ้ม
- ถ้าจะใช้จริงต้องเป็นแบบ **cap ชั้น (bounded)** เท่านั้น และยังแย่กว่า flat เชิง risk-adjusted

## 🎯 Martingale + WR สูง + TF สูงขึ้น (ตามที่ผู้ใช้ขอ)
ไฟล์: `martingale_highwr.py`, `reports/figures/martingale_highwr_twins.png` | ข้อมูล: `data/XAUUSD_1H_real.csv`, `data/XAUUSD_4H_real.csv`
Engine: mean-reversion exit ที่ SMA (target เล็ก = ชนะบ่อย) + SL กว้าง (WR สูงขึ้น)

**TF สูงขึ้นช่วย base จริง** (ต้นทุน 0.03%/ข้าง): 1H SL4% → WR 71%, PF 0.90, -4.4% | 4H SL4% → WR 71%, PF 0.91, -3.2%
(ดีกว่า 15m มาก แต่ยัง**ขาดทุนนิดหน่อย** = expectancy ยังลบ)

**บทเรียนเด็ด — WR ไม่ได้กำหนดการล้างพอร์ต "worst losing streak" ต่างหากที่กำหนด:**
| เคส | WR | worst streak | MG x2 no-cap |
|---|---|---|---|
| 1H SL4% | 71% | **5** | รอด $9.8k |
| 4H SL4% | 71% | **10** | 💥 RUINED |

→ **WR เท่ากันเป๊ะ 71% แต่ชะตาคนละทาง** เพราะ streak แย่สุดต่างกัน (5 vs 10)
worst streak เป็น random tail ที่ WR เฉลี่ยสูงคุมไม่ได้ → ทำนายล่วงหน้าไม่ได้ว่าจะเจอตัวไหน

**สรุปคณิตศาสตร์:** martingale แก้ expectancy ลบไม่ได้ WR สูง+RR ต่ำ (0.37-0.5) = ยัง expectancy ลบหลังต้นทุน
ตัวที่ "รอด" คือดวง ไม่ใช่ edge และไม่มี martingale variant ไหนชนะ flat เชิง risk-adjusted
เคสที่รอด ($9.8k) ยัง**ขาดทุน**อยู่ดี (base -4.4%) แค่เพิ่ม DD 5 เท่า

## ไฟล์ในโฟลเดอร์ตอนนี้
```
docs/TradingView_to_Bot_Workflow.md   คู่มือต้นทาง
docs/spec.md                          ✅ Build Logic (Mean Reversion, no SL/TP)
signal_xauusd_meanrev.py         ✅ signal engine + event backtester + metrics
notebooks/backtest_xauusd_meanrev.ipynb ✅ รันบนข้อมูลจริงแล้ว (18 cells, verdict=FAIL, robustness 0/72)
data/XAUUSD_15m_real.csv         ✅ ข้อมูลจริง 230,400 แท่ง 2012–2022 (÷100 = USD/oz)
make_synthetic_xauusd.py         ตัวสร้าง synthetic (smoke-test เท่านั้น)
data/SYNTHETIC_xauusd_15m.csv    ข้อมูลจำลอง (ห้ามใช้ตัดสิน verdict)
_build_notebook.py               ตัว build โน้ตบุ๊กจาก cell sources (rerun ได้)
docs/images/step1..step4 *.jpg   ภาพประกอบคู่มือ
HANDOFF.md                       ไฟล์นี้
```

## วิธีดึงข้อมูลทองจริงซ้ำ (ถ้าต้องการ)
```bash
git clone --depth 1 https://github.com/ejtraderLabs/historical-data.git
# ได้ XAUUSD/XAUUSDm15.csv → normalize ÷100 → เซฟเป็น data/XAUUSD_15m_real.csv
# หมายเหตุ sandbox: github.com + pypi.org เท่านั้นที่ allowlist; yahoo/binance/stooq/raw.githubusercontent ยัง block
```

## คำสั่งเริ่มงานต่อสำหรับแชทถัดไป
> "อ่าน HANDOFF.md — Task 3 เสร็จแล้ว verdict ตก (mean-reversion no-SL ล้างพอร์ตบนทองจริง)
> ผู้ใช้ถามหากลยุทธ์ win rate ดีกว่า ผมเสนอ 4 ตัวไว้ (ดูหัวข้อ 'ทิศทางถัดไป')
> ให้เทสต์ตัวที่ผู้ใช้เลือกด้วย pipeline เดิมบน data/XAUUSD_15m_real.csv — เขียน signal engine ใหม่แบบเดียวกับ
> signal_xauusd_meanrev.py (กัน look-ahead ด้วย shift(1), execute ที่ open) แล้วรัน verdict + robustness"

## ✅ พบ EDGE จริง! Breakout บน TF สูง = positive expectancy (robust)
ไฟล์: `reports/figures/breakout_htf_robustness.png` (heatmap), `reports/figures/breakout_4h_equity.png`
**PF>1 แทบทุก config บน 1H/4H ที่ต้นทุนจริง** (0.03-0.06%/ข้าง) — เขียวทั้งกระดาน
ตรงข้ามกับ mean-reversion (แดงทั้งกระดาน) → edge เชิงโครงสร้างจริง ไม่ใช่ overfit

**Config เลือก: Breakout 4H lookback20 rr1.5 @0.05%/ข้าง**
- Trades 664 (>100 ✅), WR 46.7%, PF 1.11, MaxDD flat -1.7%
- Compounded 1%-risk: $10k→$14.8k (+48%), CAGR ~4.3%/ปี, maxDD -16%
- ชนะ Buy&Hold (window 4H): +48% vs +15.5% ✅

**ตีความ:** edge จริงแต่โมเดสต์ (CAGR ~4%) จุดแข็ง = robust + DD ต่ำ + ชนะ B&H
→ ตัวนี้ผ่าน verdict พอจะไป Task 4 (บอท .mjs + parity) ได้ ต่างจาก mean-reversion ที่ควรตีตก
ไฟล์ใหม่: `data/XAUUSD_1H_real.csv`, `data/XAUUSD_4H_real.csv`, `martingale_highwr.py`, `martingale_test.py`, `strategies_v2.py`

## ✅✅ VALIDATION ผ่านหมด + ข้อมูลใหม่ถึง 2025 (สำคัญมาก)
ไฟล์: `validate_breakout.py`, `reports/figures/breakout_1h_validation.png`, `reports/figures/breakout_1h_recent_2025.png`
ข้อมูลใหม่: `data/XAUUSD_{15m,1H,4H}_2020_2025.csv` (จาก github ilahuerta-IA/backtrader-pullback, 5m→resample, ราคา USD จริง ถึง 3363)

**ตัวชนะสุดท้าย: Breakout 1H, lookback=20, R:R=2.5** (จูนบน 2012-2018 เท่านั้น)
พิสูจน์ 3 ช่วงเวลาอิสระ — edge อยู่รอดทุกช่วง:
| ช่วง | PF | หมายเหตุ |
|---|---|---|
| IS 2012-2018 (จูนตรงนี้) | 1.12 | in-sample |
| OOS 2019-2022 | **1.22** | ดีกว่า IS = ไม่ overfit |
| FRESH 2022-2025 (ไม่เคยเห็น) | **1.25** | ยืนยันบนข้อมูลใหม่ล่าสุด |

รายปี 2021-2025: PF 1.50/1.09/1.25/1.30/**1.42** (2025 ดีสุด = ยังเวิร์กในปีล่าสุด)
long PF 1.21 / short PF 1.11 (สองทางบวก) | 9/11 ปีกำไร | cost stress ยืนถึง 0.10%/ข้าง
compounded 1%-risk บน 2020-2025: $10k→$16.8k, maxDD -13.8%

**ข้อจำกัด:** ข้อมูลฟรีถึงแค่ ส.ค. 2025 (ไม่มี source ฟรีถึงกลางปี 2026)
**สถานะ:** ✅ ผ่าน verdict + robust + OOS + fresh-data → พร้อมไป Task 4 (บอท .mjs + parity) ได้เต็มตัว

## ✅ Task 4 เสร็จ — Production signal + bot + parity (Breakout 1H)
ไฟล์: `signal_breakout_htf.py`, `bot_breakout_htf.mjs`, `parity_check.py`
- **signal_breakout_htf.py** — signal contract sig[t]∈{-1,0,1} (breakout lb20), CLI `--emit-signals`/`--latest`/backtest
  - backtest verify: trades 346, WR 36.1%, **PF 1.234**, +5.7% (ตรงกับ validation เป๊ะ)
- **bot_breakout_htf.mjs** — ESM twin (Kung Trinity/OpenClaw), logic เดียวกัน
  - ⚠️ บั๊กที่เจอ+แก้: อย่าใช้ `process.exit()` หลัง write ยาว (stdout ตัด) → ใช้ `process.exitCode`
- **PARITY OK 0 diffs** ทั้ง 3 ไฟล์ (1H 2020-2025, 15m 230k แถว, 1H 2012-2022) — .py กับ .mjs สัญญาณตรงกัน 100%
- risk model: LONG SL=P(1-1%) TP=P(1+2.5%) ; SHORT mirror ; SL ก่อน TP (intrabar)

**เหลือก่อนรันจริง:** (1) ข้อมูล 1H ก.ย.2025→ปัจจุบันจาก MT5 (`mt5/ExportBarsCSV.mq5`, ตั้ง `InpTF=TF_H1`) หรือ connector
(2) ต่อ bot เข้า execution layer จริง (Kung Trinity/OpenClaw) + paper trade ก่อน

## Continuation Note — Codex Study Pass 2026-07-05
สำหรับแชทถัดไป / Codex รอบหน้า: โปรเจกต์นี้ศึกษาแล้วและสามารถทำต่อได้ทันทีจากสถานะนี้

**สถานะล่าสุดที่ยืนยันซ้ำแล้ว**
- โฟลเดอร์ `/Users/tan/git/TradingView` ไม่ใช่ git repo ตอนตรวจ (`git status` = fatal not a git repository)
- โปรเจกต์เป็น pipeline ทดสอบระบบเทรด: TradingView idea → spec → Python backtest/signal → Node `.mjs` bot twin → parity check
- กลยุทธ์ Mean Reversion เดิมใน `docs/spec.md` / `signal_xauusd_meanrev.py` ถูกตีตกแล้วบนข้อมูลจริง เพราะ PF แย่และ drawdown ถึงขั้นล้างพอร์ต
- กลยุทธ์ที่ผ่านคือ **Breakout HTF XAUUSD 1H**:
  - source of truth: `signal_breakout_htf.py`
  - bot twin: `bot_breakout_htf.mjs`
  - parity gate: `parity_check.py`
  - validation: `validate_breakout.py`
  - locked params: `LOOKBACK=20`, `RR=2.5`, `SL_FRAC=0.01`, fee backtest `0.05%/side`
  - signal contract: closed-bar Donchian breakout, fill at next bar open, SL checked before TP intrabar

**คำสั่งที่รันยืนยันแล้ว**
```bash
rtk python3 signal_breakout_htf.py data/XAUUSD_1H_2020_2025.csv
rtk python3 parity_check.py data/XAUUSD_1H_2020_2025.csv
rtk python3 parity_check.py data/XAUUSD_15m_real.csv
rtk python3 parity_check.py data/XAUUSD_1H_real.csv
rtk python3 validate_breakout.py
```

**ผลตรวจล่าสุด**
- `signal_breakout_htf.py data/XAUUSD_1H_2020_2025.csv`: trades 346, WR 36.1%, PF 1.234, return +5.7%, maxDD -1.4%
- `backtest_intrabar.py data/XAUUSD_1H_2020_2025.csv data/XAUUSD_5m_2020_2025.csv`: coarse 1H PF 1.23 แต่ fine 5m PF เหลือ 1.05, return +1.2%, maxDD -3.4% → edge ยังบวกแต่บางมาก ต้องเช็ค 1m/broker cost ก่อน live
- parity ผ่าน 0 diffs:
  - `data/XAUUSD_1H_2020_2025.csv`: 29,257 rows
  - `data/XAUUSD_15m_real.csv`: 230,400 rows
  - `data/XAUUSD_1H_real.csv`: 57,600 rows
- `validate_breakout.py`:
  - 1H IS 2012-2018 PF 1.12
  - 1H OOS 2019-2022 PF 1.22
  - OOS grid robustness 18/20 configs PF>1
  - long PF 1.21 / short PF 1.11
  - cost stress PF: 0.03%=1.22, 0.06%=1.13, 0.10%=1.02
- มี pandas `FutureWarning` จาก `strategies_v2.py` เรื่อง `.fillna(False)` downcasting แต่ไม่ทำให้ validation fail

**จุดทำต่อที่แนะนำ**
1. อัปเดตข้อมูล XAUUSD 1H ตั้งแต่ ก.ย. 2025 ถึงปัจจุบันด้วย `mt5/ExportBarsCSV.mq5` (`InpTF=TF_H1`) หรือ broker/MT5 connector
2. รวม/normalize CSV ให้ schema เป็น `time,open,high,low,close,volume`
3. รัน backtest + parity ใหม่บนข้อมูลที่อัปเดต
4. ถ้ายังผ่าน ให้ต่อ `bot_breakout_htf.mjs` เข้ากับ execution layer จริงแบบ paper trade ก่อน
5. ห้ามกลับไปทำ mean-reversion no-SL เป็นบอทจริง เว้นแต่เปลี่ยน risk model แล้ว backtest ใหม่ตั้งแต่ต้น

## 🧨 Grid-Martingale investigation (โบ้ขอ: หา step/mult/target ให้ปิดกำไรไม่ stopout)
ไฟล์: `martingale_grid.py`, `reports/figures/martingale_grid_tradeoff.png` | ทุน $100k, init 0.01 lot
สเปกทอง: 1 lot=100oz, 0.01 lot $1 move=$1. เทสต์จริง 2012-2022 + 2020-2025 ทั้ง buy&sell grid

**ตัวชี้วัดความปลอดภัยที่แท้จริง = "kill$"** = ระยะที่ราคาวิ่งสวน basket ใหม่จนพอร์ตแตก
| step$ | mult | maxLv | target$ | รอดทั้ง 4? | ret เฉลี่ย | kill$ | peak lots |
|---|---|---|---|---|---|---|---|
| 10 | 2.0 | 10 | 50 | ✅ | ~110% | **$178** | 10.2 |
| 20 | 2.0 | 12 | 50 | ✅ | ~46% | $225 | 41 |
| 20 | 1.5 | 20 | 50 | ✅ | ~25% | $356 | 66 |
| 30 | 1.5 | 20 | 100 | ✅ | ~13% | $526 | 66 |
| 10 | 1.0 | 30 | 20 | ✅ | -11% | **$3479** | 0.3 |

**ความจริงที่ต้องบอกโบ้:**
- คอนฟิกที่กำไรงาม (mult 2, step แคบ) มี **kill$ แค่ $134-225** — แต่ทอง 2020-22 ร่วง $460, เทรนด์ 2020-25 ขึ้น $1900
  → **กำไรพวกนี้อยู่รอดเพราะ "โชค" (survivorship)** target มาก่อนราคาจะวิ่งเกิน kill$ พอดี ไม่ใช่เพราะปลอดภัยจริง
- จะให้ kill$ ใหญ่พอทนการเคลื่อนไหวจริงของทอง ต้องดัน **mult→1.0 (ไม่ใช่ martingale แล้ว)** + step กว้าง → แต่ก็ขาดทุนเวลาเทรนด์สวน
- **direction คือตัวฆ่า:** sell grid บนเทรนด์ขึ้นของทอง = stopout/ขาดทุน (-40%) ทำนายเทรนด์ไม่ได้ = โยนหัวก้อยกับ ruin
- peak lots 66 ที่ mult1.5/20lv จริง ๆ เปิดไม่ได้ด้วยทุน $100k (ต้อง margin ~$266k) → broker ตัดก่อน = maxLv จริงน้อยกว่านั้น

**สรุป:** เป้า "ปิดทุกไม้กำไรไม่ stopout" = พนันว่าราคาไม่วิ่งสวนเกิน kill$ ก่อน target — บนทองจริง kill$ ของคอนฟิกกำไร < การเคลื่อนไหวปกติของทอง = **ระเบิดเวลา** ยังไม่ระเบิดแค่เพราะ sample ไม่เจอ
ถ้าจะเล่นจริง: cap levels เสมอ, mult≤1.5, step $20-30, **ใส่ basket hard-SL** (ทิ้งคำว่า "ไม่มี stopout") และใช้เงินก้อนเล็ก ไม่ใช่ทั้ง $100k

## ✅ Production: Multi-position + size-decay (จูนแล้ว + OOS ผ่าน)
ไฟล์: `backtest_multi.py` (reference), `mt5/ea_breakout_htf.mq5` (auto-trade EA)
**Locked config:** Breakout 1H, LOOKBACK=20, RR=2.5, SL=1%, MAX_OPEN=3, SIZE_DECAY=0.4, cost 0.05%/ข้าง
- full-sample 2022-2026: PF 1.40, ret +10.0%, maxDD -1.3%, ret/DD 8.0
- OOS 2025-2026: PF 1.27 (edge รอด) ✅
- by-rank: ไม้#0 (เต็มไซซ์) ทำเงินหลัก, ไม้#1 (0.4x) เสริม, ไม้#2 (0.16x) แทบไม่ช่วย ($31)
  → cap 2 ก็เกือบเท่า cap 3 ถ้าอยากลดความซับซ้อน

**บทเรียนคันโยก size vs SL:** ปรับ **ขนาดไม้** ตาม rank (anti-martingale) = เวิร์ก /
ปรับ **SL แคบลง** ตาม rank = พัง (breakout SL แคบโดน whipsaw)

**EA ใช้งาน:** วาง `ea_breakout_htf.mq5` ใน MQL5/Experts → compile → ลากใส่ชาร์ต XAUUSD **H1**
- inputs: MaxOpen(3), SizeDecay(0.4), BaseLot(0.10), RR(2.5), SLpct(1.0) — ตั้ง MaxOpen=1 = flat-only
- ⚠️ ต้อง **demo/paper ก่อน** + เช็คสเปรดจริง broker

**สรุปตัวเลือก production (เลือกได้):**
- flat-only (MaxOpen=1): PF 1.55, ret/DD 11.9 — risk-adjusted ดีสุด เรียบง่ายสุด
- multi cap3+decay0.4: PF 1.40, ret/DD 8.0, เทรด ×2.7 — ถี่ขึ้นมาก DD แทบไม่เพิ่ม

## 🔻 Buy-the-dip investigation (2026-07-07) — VERDICT: FAIL out-of-time
ไฟล์: `validate_dip.py` (มีสรุปผลใน docstring, รันซ้ำได้)
คำถามโบ้: "กราฟแกว่ง/ย่อตลอด ใช้ตั้ง martingale ได้ไหม" + "เก็บตอนย่อ work ไหม"

**1) Runs analysis (1H 2022→2026-07):** "ย่อเสมอ" ไม่จริง — ทองเคยวิ่ง **+34% โดยไม่ย่อถึง 3%**
(จบ 2025-10-17), +13.9% ไม่ย่อ 2%, ฝั่งลง -14.1% ไม่เด้ง 3% (2026-03)
→ martingale grid sim บนไฟล์เดียวกัน: ต้องมีทุน 50-4,554× base lot ถึงรอด maxDD, ล้างพอร์ตโดยดีไซน์
(ยืนยันบทเรียนเดิมใน section Grid-Martingale — ไม่ต้องเทสซ้ำอีก)

**2) Buy-the-dip แบบมีวินัย** (close>SMA200 + ย่อ 0.5% จาก 20-bar high, SL 1%, RR 2.5, fill next open):
| ช่วง | PF (long) | หมายเหตุ |
|---|---|---|
| 2022-2026 (จูนตรงนี้) | 1.33 coarse / **1.26 บน 1M intrabar** | +54%, DD -25.6% |
| 2020-2025 (unseen) | 1.17 | ยังบวก |
| **2012-2022 (unseen)** | **0.91** (-26.5%, DD -38%) | ❌ FAIL |
| Robustness grid 2012-2022 | **เขียว 1/16** | ❌ FAIL |
| Short mirror | PF<1 ทุกช่วง | ❌ |

**สรุป:** edge ของ dip เป็น **regime-dependent** (ได้ผลเฉพาะขาขึ้นทอง 2021+) ไม่ใช่ structural edge
ต่างจาก Breakout HTF ที่ผ่านทุกช่วง (1.12/1.22/1.25) → **ห้าม promote dip เป็นบอท**
บทเรียน: sweep บนข้อมูลช่วงเดียวหลอกได้สนิท (PF 1.33 ดูดี, IS/OOS ในช่วงเดียวกันก็ผ่าน) —
ตัวตัดสินจริงคือ out-of-time ข้าม regime. ย่อลึก 1.5-2% ยิ่งแย่ (ย่อลึกในขาขึ้น = เทรนด์กำลังพัง)

## 🔧 งานปรับปรุงที่ระบุไว้ (2026-07-07, เรียงตามความสำคัญ)
1. ~~git init + commit~~ ✅ **ปิดแล้ว 2026-07-07** — เป็น repo แล้ว push ขึ้น `github.com/tanlull/TradingView` (main)
   note เดิมใน Codex pass 2026-07-05 ที่ว่า "ไม่ใช่ git repo" = **หมดอายุแล้ว**
   ⚠️ 2 จุดต้องระวัง:
   - commit message ควรสื่อความ (ตอนนี้มี "test"/"commit" — ย้อนหาไม่ได้)
   - `data/XAUUSD_1m_MT5_export.csv` **83MB ใกล้เพดาน GitHub 100MB/ไฟล์** — export 1M รอบหน้าไฟล์จะโตเกิน
     → ก่อน push ครั้งหน้า: ใช้ git-lfs หรือ gitignore ไฟล์ data ใหญ่ (วิธี export ซ้ำมีจดไว้ใน HANDOFF แล้ว)
2. **Validate multi-position config บน 2012-2022 unseen** — MAX_OPEN=3/SIZE_DECAY=0.4 (PF 1.40)
   จูนบน 2022-2026 + OOS แค่ 2025-2026 = ด่านเดียวกับที่ dip เพิ่งสอบตก ต้องผ่านก่อนเชื่อ
   (flat-only ผ่าน 2012-2022 แล้ว ตัว decay overlay ยังไม่เคย)
3. **Parity gate สำหรับ MQL5 EA** — `ea_breakout_htf.mq5` ไม่เคยเทียบสัญญาณกับ Python
   (มีแค่ .py↔.mjs) ให้ EA log สัญญาณเป็น CSV จาก Strategy Tester แล้วรัน parity — ต้องเสร็จก่อน paper trade
4. **Cost model จริง** — ✅ **ปิดเกือบหมด 2026-07-07**: broker จริงของโบ้ spread XAUUSD ≈ **$0.35** (35 points)
   + มี rebate ทุก lot → ที่ราคาทอง $4,175 = **0.0042%/ข้าง** ต่ำกว่า assumption backtest (0.05%) **12 เท่า**
   รันด้วย signal_breakout_htf.py จริงบน 2022-2026: PF 1.553 (@0.05%) → **1.759 (@ต้นทุนจริง)**, +17.0%, DD -0.9%
   เหลือปิดสนิท: log spread จริง ณ จังหวะเข้าไม้ตอน paper trade (breakout เข้าตอนราคาวิ่ง = spread อาจถ่าง
   แต่ต่อให้ถ่าง 5 เท่า = 0.02%/ข้าง ยังต่ำกว่า assumption เดิม) + จดตัวเลข rebate/lot
5. **`validate_any.py`** — รวม battery (out-of-time ข้าม regime + robustness grid + cost stress + short mirror
   + intrabar) เป็น gate มาตรฐานรับ signal function — กลยุทธ์ใหม่ทุกตัวต้องผ่านด่านเดียวกัน

## 🧪 Batch test 4 แนวทางใหม่ (2026-07-07) — ไม่มีตัวไหนผ่าน out-of-time
เทสบน 3 ช่วง: 12-22 (unseen) / 20-25 / 22-26, cost 0.03%/ข้าง, SL-first, ตัวเลข = PF

| กลยุทธ์ | 12-22 | 20-25 | 22-26 | verdict |
|---|---|---|---|---|
| **A) Session breakout** (quiet-8h range, data-driven session detect) | 0.90-0.96 | 0.78-0.81 | 0.98-1.05 | ❌ ตายทุก variant (rr/window) |
| **B) Exit variants บน Breakout lb20:** fixed RR2.5 (baseline) | 1.00 | — | 1.29 | ✅ robust สุด |
| — breakeven@1R | 0.85 | — | 1.31 | ❌ โดน wick ออกก่อนใน 12-22 |
| — ATR3 trailing | **0.62** | — | 0.87 | ❌ พังยับ |
| — partial 50%@1.5R | 0.86 | — | 1.58 | ❌ สวยเฉพาะ regime ปัจจุบัน |
| **C) Donchian55 1H** | 0.97 | 1.04 | 1.57 | ❌ ไม่ robust เท่า lb20 |
| — Donchian20 4H | 0.96 | 1.11 | 1.40 | ❌ เส้นเดียวกัน |
| — EMA50/200 cross 4H | 0.71 | 1.73 | 3.11 | ❌ regime-dependent สุดขั้ว |
| **D) BB+RSI reversion** (แคนดิเดตเก่า #2) | 0.68 | 0.72 | 0.69 | ❌ WR 55% แต่เจ๊ง — win-rate trap ซ้ำ |
| — VWAP reversion (แคนดิเดตเก่า #4) | 0.73 | 0.70 | 0.96 | ❌ ปิด loop แล้ว |

**ข้อสรุป:**
- **Breakout lb20 + fixed RR2.5 ยังเป็นแชมป์** — ไม่มี exit ไหนที่ปรับแล้วดีขึ้นแบบข้าม regime
  (สอดคล้องบทเรียนเดิม: แตะ SL/exit ของ breakout = พัง)
- แนว trend ที่ "ดูดีตอนนี้" (EMA cross PF 3.11, partial 1.58) คือกับดัก regime ขาขึ้นทอง 2022-26 เหมือน dip
- reversion family ตายครบทุกตัวแล้ว (MeanRev, MeanRev+SL, BB+RSI, VWAP, dip) — เลิกขุดแนวนี้ได้
- ⚠️ engine ที่ใช้เทียบใน batch นี้เป็นตัว lightweight (baseline lb20 ได้ 1.00 บน 12-22
  ต่ำกว่า validate_breakout.py ที่ได้ 1.12 — คนละ cost/entry-overlap) → ใช้เทียบ **ระหว่าง variant** ได้
  แต่ตัวเลขสัมบูรณ์ให้ยึด validate_breakout.py

### E) Per-trade martingale บน BB+RSI (WR 55%) — 💥 ตายทุกแบบ
โบ้ถาม: WR 55% + มี TP/SL ทำ martingale ทีละไม้ได้ไหม → **ไม่ได้**
flat ก็ขาดทุนอยู่แล้ว (expectancy ลบ: ชนะ ~0.5R แพ้ 1R), martingale = size × expectancy ลบ = เจ๊งเร็วขึ้น
x2 no-cap RUINED 2/3 ช่วง, x1.5 RUINED 22-26 (worst streak **13 ไม้** ทั้งที่ WR 51-55%)
→ ตอกย้ำ: WR คุม streak ไม่ได้, martingale แก้ expectancy ลบไม่ได้ (บทเรียนที่ 3 รอบแล้ว — พอได้แล้ว)

### F/G) Extension-priority sizing บน Breakout lb20 — ทั้งสองทิศไม่ผ่าน
สมมติฐานโบ้: "break มาไกลใกล้กลับตัว → ลด priority" / แล้วลองกลับทิศ "เพิ่ม priority" ด้วย
ext = ระยะจาก SMA200 หน่วย ATR ณ จุด signal, tercile analysis (ไม่ต้องเลือก threshold):
| ช่วง | avgR fresh | avgR extended |
|---|---|---|
| 12-22 | -0.028 | -0.010 |
| 20-25 | +0.052 | +0.052 (เท่ากันเป๊ะ) |
| 22-26 | +0.096 | **+0.252** |
- "ไกล = ใกล้กลับตัว" **ผิด** — extended ไม่แย่กว่า fresh เลย (momentum persistence)
- ลด size ตอน extended: ตัดไม้ดีทิ้ง กำไรหาย DD ไม่ลด / เพิ่ม size ตอน extended: ดีเฉพาะ 22-26
  (ret/DD 5.2→6.0) แต่ 12-22 DD หนักขึ้น -34.8→-41.1% = regime bet ไม่ใช่ edge
- **สรุปรวมวันนี้: exit 3 แบบ + priority 2 ทิศ + martingale — ทุกการแต่งเติมแพ้ baseline ข้าม regime
  → Breakout lb20 + fixed RR2.5 + size คงที่ = final answer อย่าแต่งเพิ่ม ไปโฟกัส spread จริง + paper trade**

### H) Win-streak anti-martingale (เพิ่ม size หลังชนะ) — ไม่ผ่านเช่นกัน
ไม่มี hot-hand: P(win|เพิ่งชนะ) ≈ P(win|เพิ่งแพ้) และสองช่วงหลัง**กลับด้าน** (avgR หลังแพ้ +0.07/+0.25
ดีกว่าหลังชนะ +0.03/+0.09 — แพ้กระจุกใน chop แล้วไม้ถัดมา breakout จริง) → sim winx1.5-x2:
ผลมั่วข้าม regime (20-25 ดีขึ้น, 22-26 แย่ลง, 12-22 DD บวม -35→-69%)
**นับรวม: 12/12 variants แพ้ baseline — ปิดหัวข้อ "ปรุง Breakout" อย่างเป็นทางการ**

### I) ✅ Equity-curve anti-martingale (EC-MA filter) — variant แรกที่รอด (13th ที่ลอง)
กติกา: equity (จาก closed trades ของกลยุทธ์เอง) ต่ำกว่า MA-10 ไม้ → เทรดครึ่ง size, กลับเหนือ → เต็ม
| | 12-22 | 20-25 | 22-26 |
|---|---|---|---|
| DD: base → ecma | -34.8 → **-28.6%** | -18.7 → **-17.9%** | -16.7 → **-11.3%** |
| PF: base → ecma | 1.00 → 1.01 | 1.07 → 1.08 | 1.29 → 1.31 |
| ret/DD 22-26 | | | 5.2 → **6.3** |
- **เป็น DD-reducer (ลด 20-30% relative) ไม่ใช่ profit-booster** — return สัมบูรณ์ลดนิดหน่อยช่วงดี
- Robust: ทุก window 5-50 ลด DD ครบ 3 ช่วง (15/15 ช่อง), PF ไม่เสีย — ผ่าน battery เดียวกับที่ฆ่า dip
- กลไก: ไม้แพ้กระจุกใน chop → EC ต่ำกว่า MA = proxy chop → ลดไม้ตรงนั้น = ตรรกะเดียวกับ SIZE_DECAY
- ⚠️ variant ที่ 13 — multiple-comparison risk มีจริง ผล modest ต้องยืนยันใน paper trade
- ต่อยอด: เพิ่ม input `InpEcmaFilter` ใน ea_breakout_htf.mq5 (track own equity, MA10, halve lot) + รัน tester ซ้ำ

### J) Trend-filtered martingale grid (ไอเดียโบ้: ถัวตามเทรนด์เท่านั้น ห้ามสวน) — เกือบ แต่ไม่รอด 1M
กติกา: SMA200 กำหนดทิศ, buy-grid เฉพาะขาขึ้น / sell-grid เฉพาะขาลง, ถัว ×mult ทุก step 1%,
TP ตะกร้าที่ BE+0.5%, **ปิดตะกร้าทันทีเมื่อเทรนด์พลิก** (ตัวนี้คือหัวใจ — hold-thru-flip ตาย DD 1,000x)
- Coarse 1H (cost จริง): บวกครบ 3 ช่วง, mult ช่วยจริง (DCA control x1.0 แพ้ชัด) — martingale ที่ดีสุดที่เคยเทส
- **แต่ 1M replay (22-26): DD บวม 5 เท่า** — x2: -181%→**-959%ofBase**, x1.5: -65%→-358%, ret/DD เหลือ 0.5-1.1
  (ช่วงระหว่างถัวกับ flip-close ราคาแกว่งลึกกว่าที่แท่ง 1H เห็น) + cost-sensitive (ตาย 20-25 ที่ 0.03%/side)
- Verdict: ❌ แพ้ Breakout (ret/DD 5-12) ทุกมิติ — ไม่มีเหตุผลให้ใช้
- **บทเรียนใหม่: ระบบ grid = class ที่ coarse backtest หลอกหนักสุด** (breakout coarse→fine หด ~6%
  แต่ grid DD บวม ~500%) → ข้อเสนอ grid ใด ๆ ต่อจากนี้ ตัดสินด้วย 1M replay เท่านั้น

### ✅ ผล Strategy Tester ของโบ้เอง (2026 YTD, AGGRESSIVE, real ticks, History Quality 100%)
Net +$27,447 บน $10k / PF 1.51 / Sharpe 3.32 / 278 trades / WR 38.1% / Equity DD relative **-31.8%**
consecutive: ชนะ 14 ($9.6k) แพ้ 14 (-$3.3k) | short win 43.2% > long 34.4% (เก็บขาลง มี.ค. 2026 ได้จริง)
ตีความ: ตรงย่านโมเดล (PF 1.38-1.55) ✅ แต่เป็น 6 เดือนใน regime ดีสุด — อย่า extrapolate +274%
DD -32% คือราคาจริงของ AGGRESSIVE (BaseLot 0.10 @ทอง $4k = ~4%/ไม้แรก, ตะกร้า ~13%)
→ ถ้ารับไม่ได้: BALANCED หรือ BaseLot 0.05
