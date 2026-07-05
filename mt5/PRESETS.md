# Breakout HTF EA — 3 Presets (XAUUSD H1)

เลือก preset จาก input **`InpPreset`** ใน EA (`ea_breakout_htf.mq5`). ตัวเลขจาก
backtest ข้อมูลจริง 1M ของโบ้ 2022-2026 (ต้นทุน 0.05%/ข้าง). อดีตไม่การันตีอนาคต.

แกนร่วมทุก preset: Donchian breakout, LOOKBACK=20, RR=2.5, SL=1%, Long+Short, TF=H1.

| Preset | MaxOpen | SizeDecay | เทรด | WR | PF | Return | maxDD | ret/DD |
|---|---|---|---|---|---|---|---|---|
| **1. CONSERVATIVE** | 1 (flat) | — | 380 | 41.6% | **1.55** | +13.5% | **-1.1%** | **11.9** |
| **2. BALANCED** | 3 | 0.4 | 1,030 | 36.1% | 1.40 | +10.0% | -1.3% | 8.0 |
| **3. AGGRESSIVE** | 5 | 0.8 | 1,445 | 36.6% | 1.30 | **+17.4%** | -3.1% | 5.6 |

## เลือกตัวไหนดี
- **CONSERVATIVE** — risk-adjusted ดีสุด (ret/DD 11.9), DD ตื้นสุด, เรียบง่ายสุด (ไม้เดียว).
  เหมาะถ้าเน้นความนิ่ง/ทุนน้อย/เพิ่งเริ่ม.
- **BALANCED** — เทรดถี่ขึ้น ~2.7× โดย DD แทบไม่เพิ่ม (ไม้ซ้อนเล็กลงเร็ว decay 0.4).
  เหมาะถ้าอยากได้ signal ถี่ขึ้นแต่ยังคุมเสี่ยงแน่น. (หมายเหตุ: ปี 2024 -0.2%)
- **AGGRESSIVE** — gross return สูงสุด (+17.4%) บวกทุกปี แต่ DD ลึกสุด (-3.1%),
  ไม้ซ้อนใหญ่ (decay 0.8) = exposure สูง. เหมาะถ้ารับ DD ได้และอยากดันผลตอบแทน.

## ก่อนเงินจริง (ทุก preset)
1. **MT5 Strategy Tester → "Every tick based on real ticks"** เทียบกับ `backtest_multi.py`.
2. **Demo/paper 1-2 เดือน** เช็คสเปรด+slippage จริงของ broker (ต้อง < ~0.05%/ข้าง).
3. ตั้ง **BaseLot** ให้เหมาะกับทุน (ดู position-sizing) — DD ในตารางเป็น % ของ exposure ที่เทสต์.

## Custom
ตั้ง `InpPreset = PRESET_CUSTOM` แล้วปรับ `InpMaxOpen` / `InpSizeDecay` เอง.
reference: `backtest_multi.py` (รันดูตัวเลขทั้ง 3 preset ได้: `python3 backtest_multi.py`).
