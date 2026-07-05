//+------------------------------------------------------------------+
//|  ExportBarsCSV.mq5                                                |
//|  Export the current chart symbol's bars (any timeframe) to CSV.  |
//|  Output format matches the TradingView backtest pipeline:        |
//|      time,open,high,low,close,volume                             |
//|                                                                  |
//|  HOW TO USE (macOS or Windows MT5):                              |
//|   1. MT5 > open MetaEditor (Tools > MetaQuotes Language Editor). |
//|   2. Put this file in  MQL5/Scripts/  then Compile (F7).         |
//|   3. Open an XAUUSD chart.                                       |
//|   4. Navigator > Scripts > double-click ExportBarsCSV.           |
//|      A dialog appears (script_show_inputs): pick InpTF and bars. |
//|   5. Output:  <SYMBOL>_<TF>_export.csv  in  MQL5/Files/          |
//|      (File > Open Data Folder > MQL5 > Files).                   |
//|                                                                  |
//|  TIP: For deep 1-minute history, first open the M1 chart and    |
//|  press Home / scroll left until MT5 finishes downloading bars,  |
//|  then raise InpMaxBars (1m needs ~1.5M bars for ~5 years).       |
//+------------------------------------------------------------------+
#property script_show_inputs
#property strict

enum EExportTF { TF_M1, TF_M5, TF_M15, TF_H1, TF_H4, TF_D1 };

input EExportTF InpTF      = TF_M1;      // timeframe to export
input int       InpMaxBars = 1500000;    // max most-recent bars (1m needs a lot)

ENUM_TIMEFRAMES ResolveTF(EExportTF e)
{
   switch(e)
   {
      case TF_M1:  return PERIOD_M1;
      case TF_M5:  return PERIOD_M5;
      case TF_M15: return PERIOD_M15;
      case TF_H1:  return PERIOD_H1;
      case TF_H4:  return PERIOD_H4;
      case TF_D1:  return PERIOD_D1;
   }
   return PERIOD_H1;
}

string TFName(EExportTF e)
{
   switch(e)
   {
      case TF_M1:  return "M1";
      case TF_M5:  return "M5";
      case TF_M15: return "M15";
      case TF_H1:  return "H1";
      case TF_H4:  return "H4";
      case TF_D1:  return "D1";
   }
   return "TF";
}

void OnStart()
{
   string          sym = Symbol();
   ENUM_TIMEFRAMES tf  = ResolveTF(InpTF);

   MqlRates rates[];
   ArraySetAsSeries(rates, false);        // oldest -> newest
   int copied = CopyRates(sym, tf, 0, InpMaxBars, rates);
   if(copied <= 0)
   {
      Print("ExportBarsCSV: no data for ", sym, " ", TFName(InpTF),
            " err=", GetLastError(),
            "  (open that timeframe's chart, scroll left to load history, retry)");
      return;
   }

   string fn = sym + "_" + TFName(InpTF) + "_export.csv";
   int handle = FileOpen(fn, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("ExportBarsCSV: cannot open file err=", GetLastError());
      return;
   }

   FileWrite(handle, "time", "open", "high", "low", "close", "volume");
   for(int i = 0; i < copied; i++)
      FileWrite(handle,
                TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES),
                DoubleToString(rates[i].open,  3),
                DoubleToString(rates[i].high,  3),
                DoubleToString(rates[i].low,   3),
                DoubleToString(rates[i].close, 3),
                (long)rates[i].tick_volume);
   FileClose(handle);

   PrintFormat("ExportBarsCSV: wrote %d %s bars of %s to MQL5/Files/%s  (%s -> %s)",
               copied, TFName(InpTF), sym, fn,
               TimeToString(rates[0].time, TIME_DATE|TIME_MINUTES),
               TimeToString(rates[copied-1].time, TIME_DATE|TIME_MINUTES));
}
//+------------------------------------------------------------------+
