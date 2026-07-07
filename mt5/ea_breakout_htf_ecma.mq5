//+------------------------------------------------------------------+
//|  ea_breakout_htf_ecma.mq5                                        |
//|  XAUUSD Breakout HTF + EC-MA anti-martingale filter              |
//|                                                                  |
//|  Same core as ea_breakout_htf.mq5 (Donchian lb20, RR2.5, SL1%,   |
//|  multi-position + size-decay) PLUS an equity-curve filter:       |
//|                                                                  |
//|  EC-MA FILTER (validated 2026-07-07, research_batch4):           |
//|    Build a "shadow equity" from closed trades, normalized        |
//|    per-lot (so the filter itself doesn't feed back into the      |
//|    curve). When shadow equity < MA(InpEcmaWindow) of itself      |
//|    -> trade at InpEcmaFactor x BaseLot (default half size).      |
//|    Back above the MA -> full size again.                        |
//|                                                                  |
//|  Effect in backtest (3 regimes 2012-2026, windows 5-50 all       |
//|  green): max DD reduced 20-30% relative, PF neutral-to-better.   |
//|  It is a DD-reducer, NOT a profit booster.                       |
//|                                                                  |
//|  ⚠️ TEST ON DEMO FIRST. Past results do not guarantee future.   |
//+------------------------------------------------------------------+
#property copyright "TradingView->Bot project"
#property version   "1.10"
#property strict

#include <Trade/Trade.mqh>

enum EPreset { PRESET_CONSERVATIVE, PRESET_BALANCED, PRESET_AGGRESSIVE, PRESET_CUSTOM };

//------------------------------------------------------------------ inputs
input EPreset InpPreset      = PRESET_BALANCED; // pick a preset (Custom uses the fields below)
input long    InpMagic       = 20260707;   // magic number (use one distinct from the plain EA!)
input int     InpLookback    = 20;         // Donchian lookback (bars)
input double  InpRR          = 2.5;        // reward:risk (TP = RR * SL)
input double  InpSLpct       = 1.0;        // stop-loss in % of entry price
input int     InpMaxOpen     = 3;          // [CUSTOM] max concurrent positions (1 = flat)
input double  InpSizeDecay   = 0.4;        // [CUSTOM] k-th position lot = BaseLot * decay^k
input double  InpBaseLot     = 0.10;       // first-position lot size
input bool    InpAllowLong   = true;
input bool    InpAllowShort  = true;
input int     InpSlippage    = 20;         // max deviation (points)
// --- EC-MA filter ---
input bool    InpEcmaEnable  = true;       // enable equity-curve filter
input int     InpEcmaWindow  = 10;         // MA window over closed-trade shadow equity
input double  InpEcmaFactor  = 0.5;        // lot multiplier while below the MA

CTrade   trade;
datetime lastBarTime = 0;
int      g_maxOpen;
double   g_sizeDecay;
bool     g_reducedPrev = false;   // for state-change logging

//------------------------------------------------------------------ init
int OnInit()
{
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
   PrintFormat("ea_breakout_htf_ecma on %s %s | preset=%s -> MaxOpen=%d SizeDecay=%.2f | ECMA %s win=%d factor=%.2f",
               _Symbol, EnumToString(_Period), EnumToString(InpPreset),
               g_maxOpen, g_sizeDecay,
               (InpEcmaEnable ? "ON" : "OFF"), InpEcmaWindow, InpEcmaFactor);
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

//------------------------------------------------------------------ EC-MA filter
// Shadow equity = cumulative per-lot PnL of our closed trades (deal profit
// normalized by volume). Per-lot normalization removes the filter's own
// size changes from the curve — this mirrors the shadow-equity method
// used in the validation backtest (no feedback loop).
// Returns true when we should trade reduced size.
bool EcmaReduced()
{
   if(!InpEcmaEnable) return false;

   if(!HistorySelect(0, TimeCurrent())) return false;
   int total = HistoryDealsTotal();

   double eqArr[];                 // shadow equity after each closed trade
   ArrayResize(eqArr, 0);
   double cum = 0.0;
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double vol = HistoryDealGetDouble(tk, DEAL_VOLUME);
      if(vol <= 0) continue;
      double pnl = HistoryDealGetDouble(tk, DEAL_PROFIT)
                 + HistoryDealGetDouble(tk, DEAL_SWAP)
                 + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      cum += pnl / vol;            // per-lot PnL -> size-independent curve
      int n = ArraySize(eqArr);
      ArrayResize(eqArr, n + 1);
      eqArr[n] = cum;
   }

   int n = ArraySize(eqArr);
   if(n < InpEcmaWindow) return false;   // not enough history -> full size (matches backtest)

   double ma = 0.0;
   for(int i = n - InpEcmaWindow; i < n; i++) ma += eqArr[i];
   ma /= InpEcmaWindow;

   return (eqArr[n - 1] < ma);
}

//------------------------------------------------------------------ main
void OnTick()
{
   datetime t0 = iTime(_Symbol, PERIOD_H1, 0);
   if(t0 == lastBarTime) return;
   lastBarTime = t0;

   int lb = InpLookback;
   if(Bars(_Symbol, PERIOD_H1) < lb + 3) return;

   double closePrev = iClose(_Symbol, PERIOD_H1, 1);
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

   // EC-MA filter: half size while our own (shadow) equity is below its MA
   bool reduced = EcmaReduced();
   if(reduced != g_reducedPrev)
   {
      PrintFormat("ECMA state change -> %s size", (reduced ? "REDUCED" : "FULL"));
      g_reducedPrev = reduced;
   }
   double ecmaMul = (reduced ? InpEcmaFactor : 1.0);

   double lot = NormLot(InpBaseLot * ecmaMul * MathPow(g_sizeDecay, openCnt));
   if(lot <= 0) return;

   double slf = InpSLpct / 100.0;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double spreadPts = (ask - bid) / _Point;   // log real spread at entry

   bool ok = false;
   if(sig == 1)
   {
      double sl = NormalizeDouble(ask * (1.0 - slf), dg);
      double tp = NormalizeDouble(ask * (1.0 + slf * InpRR), dg);
      ok = trade.Buy(lot, _Symbol, ask, sl, tp, "breakout_htf_ecma");
   }
   else
   {
      double sl = NormalizeDouble(bid * (1.0 + slf), dg);
      double tp = NormalizeDouble(bid * (1.0 - slf * InpRR), dg);
      ok = trade.Sell(lot, _Symbol, bid, sl, tp, "breakout_htf_ecma");
   }
   if(!ok)
      Print("order failed: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   else
      PrintFormat("OPEN %s #%d lot %.2f%s (Donchian %d) | spread %.0f pts",
                  (sig==1?"LONG":"SHORT"), openCnt+1, lot,
                  (reduced ? " [ECMA-reduced]" : ""), lb, spreadPts);
}
//+------------------------------------------------------------------+
