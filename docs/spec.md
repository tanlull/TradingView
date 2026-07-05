# Strategy Specification: Mean Reversion with Incremental Entry (XAUUSD 15M)

> สร้างจากขั้นตอน Build Logic ตาม docs/TradingView_to_Bot_Workflow.md
> ต้นแบบ: "Mean Reversion with Incremental Entry" by HedgerLabs
> (https://www.tradingview.com/script/IQTlQsCJ-Mean-Reversion-with-Incremental-Entry-by-HedgerLabs/)
> วันที่สร้าง: 2026-07-04

## 1. Market & Data

| Item | Value |
|---|---|
| Asset | XAUUSD (Gold Spot / Gold Futures proxy) |
| Timeframe | 15 นาที |
| Data source | Yahoo Finance (GC=F) หรือ CSV OHLCV ที่ผู้ใช้จัดหา |
| ระยะข้อมูลขั้นต่ำ | มากที่สุดเท่าที่แหล่งข้อมูลให้ (เป้าหมาย > 100 เทรด) |

## 2. Core Logic

### Indicator
- `SMA = Simple Moving Average(close, sma_length)`
- `dist% = (close - SMA) / SMA × 100`

### Entry (Long) — เมื่อราคา "ต่ำกว่า" SMA
- ไม้แรก: `dist% ≤ -initial_distance`
- ไม้ถัดไป (Incremental): เพิ่มทีละไม้ทุกครั้งที่ `dist%` ต่ำลงอีกครบ `step_distance` จากระดับเข้าไม้ล่าสุด
- ทุกไม้ขนาดเท่ากัน (equal sizing)

### Entry (Short) — เมื่อราคา "สูงกว่า" SMA
- สมมาตรกับฝั่ง Long: ไม้แรกเมื่อ `dist% ≥ +initial_distance` แล้วเพิ่มไม้ทุก `step_distance`

### Exit
- ปิดทุกไม้ของ position เมื่อราคากลับมาแตะ/ข้ามเส้น SMA
  - Long: ปิดเมื่อ `close ≥ SMA`
  - Short: ปิดเมื่อ `close ≤ SMA`
- **ไม่มี Stop Loss / Take Profit** (ตามต้นฉบับ — ผู้ใช้ยืนยันแล้ว รับความเสี่ยง drawdown ลึกกรณีเทรนด์แรง)
- ไม่มีการถือ Long และ Short พร้อมกัน (ปิดฝั่งเดิมก่อนเปิดฝั่งตรงข้าม)

## 3. Parameters (ค่าตั้งต้น + ช่วง Robustness Sweep)

| Parameter | Default | Sweep range |
|---|---|---|
| `sma_length` | 200 | 100 – 300 (step 25) |
| `initial_distance` (%) | 0.50 | 0.30 – 1.00 (step 0.10) |
| `step_distance` (%) | 0.25 | คงที่ = initial_distance / 2 |
| `max_entries` ต่อฝั่ง | 5 | คงที่ (กัน position โตไม่จำกัด) |

> หมายเหตุ: ทองคำผันผวนต่ำกว่าคริปโต ค่า distance จึงตั้งต่ำกว่าตัวอย่าง XRP ในคู่มือ
> `max_entries = 5` เป็น guard เชิงวิศวกรรม (ต้นฉบับไม่จำกัด) — ถ้าต้องการตามต้นฉบับเป๊ะให้ตั้งเป็น ∞

## 4. Anti-Bias Rules (บังคับใช้ในโค้ดทุกไฟล์)

- สัญญาณคำนวณจาก **แท่งที่ปิดแล้วเท่านั้น**: ใช้ `.shift(1)` กับ SMA และ dist% ก่อนเทียบเงื่อนไข
- Execution ที่ราคา **open ของแท่งถัดไป** หลังเกิดสัญญาณ
- ไม่ใช้ `calc_on_every_tick` แบบต้นฉบับ (เป็นแหล่ง repaint) — ใช้ bar-close เท่านั้น

## 5. Costs

| Item | Value |
|---|---|
| Fee | 0.10% ต่อข้าง (เข้า+ออก) |
| Slippage | 0.02% ต่อข้าง |

## 6. Acceptance Criteria (Checklist Verdict)

- [ ] Trade count > 100
- [ ] Max Drawdown อยู่ในเกณฑ์ยอมรับได้ (รายงานตัวเลขจริง — ไม่มี SL ต้องดูข้อนี้หนักพิเศษ)
- [ ] Win Rate & R:R สมดุล
- [ ] ชนะ Buy & Hold ของ XAUUSD ช่วงเดียวกัน
- [ ] ไม้ชนะสูงสุดกำไรไม่เกิน 10% ของกำไรรวม
- [ ] คิด Fee + Slippage แล้ว
- [ ] Robustness Surface (sma_length × initial_distance) มีโซนกำไรเขียวเป็นวงกว้าง

## 7. Deliverables

1. `notebooks/backtest_xauusd_meanrev.ipynb` — Build Signal + Backtest + Verdict + Robustness
2. `signal_xauusd_meanrev.py` — production signal check (ฝั่งหลังบ้าน)
3. `bot_xauusd_meanrev.mjs` — production bot script (ESM สำหรับ Kung Trinity / OpenClaw)
4. Parity check: สัญญาณ .py และ .mjs ต้องตรงกับ notebook 100%
