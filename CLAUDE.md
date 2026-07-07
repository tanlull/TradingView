# CLAUDE.md — TradingView Bot Research

## บทบาท

โบ้ = เพื่อนสนิท. ผู้ใช้เป็นนักทดสอบระบบเทรด ไม่ใช่ที่ปรึกษาการเงิน.

พูดตรง เน้นความจริงจากข้อมูล ไม่ปั้น backtest ให้สวย และเตือนความเสี่ยงเสมอ. ทุกการทดสอบต้องคิด fee/slippage, กัน look-ahead, และแยกให้ชัดว่าเป็น coarse backtest หรือ intrabar replay.

## อ่านก่อนเริ่มงาน

1. อ่าน `HANDOFF.md` ก่อนเสมอ เพราะเป็น long memory ของโปรเจกต์
2. อ่าน `AGENTS.md` ด้วยถ้าทำงานร่วมกับ Codex หรือ agent อื่น
3. อย่าถามซ้ำเรื่องที่ล็อกไว้แล้วในไฟล์เหล่านี้ เว้นแต่ข้อมูลขัดกันจริง

## สถานะล่าสุด

Workflow หลักทำครบแล้ว: Logic → Signal+Backtest → Verdict → Bot+Parity.

กลยุทธ์ต้นฉบับ **Mean Reversion ไม่มี SL/TP** ถูกตีตก:

- ล้างพอร์ตบนข้อมูลทองจริง
- robustness แย่
- ห้ามเอาไปทำบอทจริง ยกเว้นเปลี่ยน risk model แล้ว backtest ใหม่ตั้งแต่ต้น

กลยุทธ์ที่ผ่าน coarse validation คือ **Breakout HTF XAUUSD 1H**:

- `signal_breakout_htf.py` = Python source of truth
- `bot_breakout_htf.mjs` = Node ESM bot twin สำหรับ Kung Trinity / OpenClaw
- `parity_check.py` = parity gate
- `validate_breakout.py` = IS/OOS + robustness validation
- `backtest_intrabar.py` = fine-bar replay สำหรับเช็ค SL/TP order

Locked params:

- `LOOKBACK=20`
- `RR=2.5`
- `SL_FRAC=0.01`
- signal = closed-bar Donchian breakout
- fill = next bar open

## ตัวเลขสำคัญ

Coarse 1H backtest บน `data/XAUUSD_1H_2020_2025.csv`:

- trades 346
- WR 36.1%
- PF 1.23
- return +5.7%
- maxDD -1.4%

5m intrabar replay บน `data/XAUUSD_5m_2020_2025.csv` (2020-2025):

- trades 372 / WR 32.5% / PF 1.05 / return +1.2% / maxDD -3.4%

**REAL 1M intrabar บน `data/XAUUSD_1m_MT5_export.csv` (2022-04 → 2026-07-03, ของโบ้ export เอง):**
signals `data/XAUUSD_1H_MT5_export_20220408_20260703.csv`

- Coarse 1H-fill: trades 380 / WR 41.6% / PF **1.55** / return +13.5% / maxDD -1.1%
- Fine 1M intrabar: trades 389 / WR 40.1% / PF **1.46** / return +11.7% / maxDD -1.6%
- ต่างกันแค่ ~6% → assumption "SL ก่อน TP" ไม่บิดผลมีนัยยะบน 1M จริง ✅
- parity บนไฟล์นี้ = 0 diffs. 1M sanity: high≥low 0 ผิด, OHLC 0 ผิด, spacing 1min เป๊ะ

สรุป: edge Breakout 1H **ยืนยันแข็งบนข้อมูลสดถึง ก.ค. 2026** (PF 1.46 หลังคิด intrabar จริง).
2022-2026 เป็นช่วงที่ edge ดีกว่า 2020-2025. ยังต้องเช็ค spread จริง + paper trade ก่อนเงินจริง.

## งานค้างที่ควรทำต่อ

1. ✅ เสร็จ: 1M intrabar ผ่านแล้ว (PF 1.46) + 1H สดถึง ก.ค.2026 (PF 1.55) + parity 0 diffs
2. เช็คต้นทุน/สเปรดจริงของ broker ว่าต่ำพอสำหรับ edge (ต้อง < ~0.05%/ข้าง)
3. paper trade 1-2 เดือนก่อนเงินจริง
4. MQL5 auto-trade EA — 1m intrabar ผ่านแล้ว ทำได้ (โบ้เคยขอไว้)
   ไฟล์ 1M ล่าสุด: `data/XAUUSD_1m_MT5_export.csv`, 1H: `..._20220408_20260703.csv`

## หมายเหตุเทคนิค

- ข้อมูลที่มี: `data/XAUUSD_{15m,1H,4H}_real.csv`, `data/XAUUSD_{15m,1H,4H,5m}_2020_2025.csv`
- ข้อมูลฟรีในโปรเจกต์ถึงประมาณ ส.ค. 2025
- MT5 บนเครื่องผู้ใช้เป็น macOS native; ใช้ `mt5/ExportBarsCSV.mq5` เพื่อ export CSV แล้วเลือก timeframe จาก `InpTF`
- ถ้าต้อง compile/backtest MQ5 EA ด้วย MT5 Strategy Tester บน macOS ให้ใช้ workflow ใน `packages/mq5-macos-backtest-portable/mq5-macos-backtest/SKILL.md`
- ถ้าแก้ logic ใน Python ต้องแก้ Node twin และรัน parity ทุกครั้ง
- หลีกเลี่ยง Martingale แบบไม่ cap; ผลทดสอบเดิมชี้ว่าเสี่ยง ruin และไม่แก้ expectancy
