//+------------------------------------------------------------------+
//|  ea_breakout_htf.mq5                                             |
//|  XAUUSD Breakout HTF — multi-position + size-decay auto-trader   |
//|                                                                  |
//|  Mirrors backtest_multi.py (the Python reference / source of     |
//|  truth). Validated on real 1M data 2022-2026 (IS/OOS checked):   |
//|    LOOKBACK=20, RR=2.5, SL=1%, MAX_OPEN=3, SIZE_DECAY=0.4        |
//|    full-sample PF 1.40 / ret/DD 8.0 ; OOS 2025-26 PF 1.27       |
//|                                                                  |
//|  LOGIC (per CLOSED H1 bar):                                      |
//|   long  if close[1] > highest high of the 20 bars before it     |
//|   short if close[1] < lowest  low  of the 20 bars before it     |
//|   -> open at market; SL = 1%, TP = 2.5% (RR 2.5)                |
//|   -> may stack up to MAX_OPEN positions (don't wait for close)  |
//|   -> the k-th open position uses lot = BaseLot * SIZE_DECAY^k    |
//|                                                                  |
//|  ⚠️ TEST ON DEMO FIRST. Past results do not guarantee future.   |
//|  Set MAX_OPEN=1 to run the simpler flat-only version.           |
//+------------------------------------------------------------------+
#property copyright "TradingView->Bot project"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//------------------------------------------------------------------ presets
// Validated on real 1M data 2022-2026 (cost 0.05%/side):
//   CONSERVATIVE cap1        -> PF 1.55 ret+13.5% DD-1.1% ret/DD 11.9  (best risk-adj)
//   BALANCED     cap3 dec0.4 -> PF 1.40 ret+10.0% DD-1.3% ret/DD 8.0   (more trades)
//   AGGRESSIVE   cap5 dec0.8 -> PF 1.30 ret+17.4% DD-3.1% ret/DD 5.6   (max gross)
enum EPreset { PRESET_CONSERVATIVE, PRESET_BALANCED, PRESET_AGGRESSIVE, PRESET_CUSTOM };

//------------------------------------------------------------------ inputs
input EPreset InpPreset      = PRESET_BALANCED; // pick a preset (Custom uses the fields below)
input long    InpMagic       = 20260705;   // magic number (identifies our trades)
input int     InpLookback    = 20;         // Donchian lookback (bars)
input double  InpRR          = 2.5;        // reward:risk (TP = RR * SL)
input double  InpSLpct       = 1.0;        // stop-loss in % of entry price
input int     InpMaxOpen     = 3;          // [CUSTOM] max concurrent positions (1 = flat)
input double  InpSizeDecay   = 0.4;        // [CUSTOM] k-th position lot = BaseLot * decay^k
input double  InpBaseLot     = 0.10;       // first-position lot size
input bool    InpAllowLong   = true;
input bool    InpAllowShort  = true;
input int     InpSlippage    = 20;         // max deviation (points)

CTrade   trade;
datetime lastBarTime = 0;
int      g_maxOpen;      // resolved from preset
double   g_sizeDecay;    // resolved from preset

//------------------------------------------------------------------ init
int OnInit()
{
   // resolve preset -> effective MaxOpen / SizeDecay
   switch(InpPreset)
   {
      case PRESET_CONSERVATIVE: g_maxOpen = 1; g_sizeDecay = 0.4; break;
      case PRESET_BALANCED:     g_maxOpen = 3; g_sizeDecay = 0.4; break;
      case PRESET_AGGRESSIVE:   g_maxOpen = 5; g_sizeDecay = 0.8; break;
      default:                  g_maxOpen = InpMaxOpen; g_sizeDecay = InpSizeDecay; break;
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("ea_breakout_htf on %s %s | preset=%s -> MaxOpen=%d SizeDecay=%.2f",
               _Symbol, EnumToString(_Period), EnumToString(InpPreset),
               g_maxOpen, g_sizeDecay);
   if(_Period != PERIOD_H1)
      Print("WARNING: attach to an H1 chart — signal is defined on H1 bars.");
   return(INIT_SUCCEEDED);
}

//------------------------------------------------------------------ helpers
int CountOurPositions()
{
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         cnt++;
   }
   return cnt;
}

double NormLot(double lot)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0) lot = MathRound(lot / step) * step;
   lot = MathMax(minL, MathMin(maxL, lot));
   return NormalizeDouble(lot, 2);
}

//------------------------------------------------------------------ main
void OnTick()
{
   // act once per new H1 bar
   datetime t0 = iTime(_Symbol, PERIOD_H1, 0);
   if(t0 == lastBarTime) return;
   lastBarTime = t0;

   int lb = InpLookback;
   // need bars: index 1 (just-closed) + lb bars before it (2..lb+1)
   if(Bars(_Symbol, PERIOD_H1) < lb + 3) return;

   double closePrev = iClose(_Symbol, PERIOD_H1, 1);
   // highest high / lowest low of the lb bars BEFORE the just-closed bar (shift 2..lb+1)
   int hi_idx = iHighest(_Symbol, PERIOD_H1, MODE_HIGH, lb, 2);
   int lo_idx = iLowest (_Symbol, PERIOD_H1, MODE_LOW,  lb, 2);
   if(hi_idx < 0 || lo_idx < 0) return;
   double hh = iHigh(_Symbol, PERIOD_H1, hi_idx);
   double ll = iLow (_Symbol, PERIOD_H1, lo_idx);

   int sig = 0;
   if(closePrev > hh) sig = 1;
   else if(closePrev < ll) sig = -1;
   if(sig == 0) return;
   if(sig == 1 && !InpAllowLong)  return;
   if(sig == -1 && !InpAllowShort) return;

   int openCnt = CountOurPositions();
   if(openCnt >= g_maxOpen) return;

   // size the k-th (=openCnt) position with the decay ladder
   double lot = NormLot(InpBaseLot * MathPow(g_sizeDecay, openCnt));
   if(lot <= 0) return;

   double slf = InpSLpct / 100.0;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   bool ok = false;
   if(sig == 1)
   {
      double sl = NormalizeDouble(ask * (1.0 - slf), dg);
      double tp = NormalizeDouble(ask * (1.0 + slf * InpRR), dg);
      ok = trade.Buy(lot, _Symbol, ask, sl, tp, "breakout_htf");
   }
   else
   {
      double sl = NormalizeDouble(bid * (1.0 + slf), dg);
      double tp = NormalizeDouble(bid * (1.0 - slf * InpRR), dg);
      ok = trade.Sell(lot, _Symbol, bid, sl, tp, "breakout_htf");
   }
   if(!ok)
      Print("order failed: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   else
      PrintFormat("OPEN %s #%d lot %.2f  (Donchian %d breakout)",
                  (sig==1?"LONG":"SHORT"), openCnt+1, lot, lb);
}
//+------------------------------------------------------------------+
