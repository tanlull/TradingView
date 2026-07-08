import pandas as pd, numpy as np
H=pd.read_csv('/sessions/youthful-great-bell/mnt/TradingView/data/XAUUSD_1H_MT5_export_20220408_20260703.csv')
H['time']=pd.to_datetime(H['time'],format='%Y.%m.%d %H:%M',utc=True)
hc=H['close'].values; ht=H['time'].values
M=pd.read_csv('/sessions/youthful-great-bell/mnt/TradingView/data/XAUUSD_1m_MT5_export.csv')
M['time']=pd.to_datetime(M['time'],format='%Y.%m.%d %H:%M',utc=True)
mo,mh,ml,mc=(M[k].values for k in('open','high','low','close'))
mt=M['time'].values
idx=np.searchsorted(ht,mt,side='right')-1

def run(tr_h, mult, step=0.01, tp=0.005, maxlv=15, cost_side=0.0042/100, warm=201):
    trend=np.zeros(len(mt),dtype=int)
    ok=idx>=warm
    trend[ok]=tr_h[idx[ok]-1]
    eq=0.0; peak=0.0; mdd=0.0; lots=[]; prices=[]; side=0; wl=0
    def close(px):
        nonlocal eq,peak
        eq+=sum(q*(px-p)/p*side for p,q in zip(prices,lots))-sum(lots)*cost_side*2
        peak=max(peak,eq)
    for i in range(len(mt)):
        if trend[i]==0: continue
        if side==0:
            side=trend[i]; lots=[1.0]; prices=[mc[i]]; continue
        while len(lots)<maxlv:
            if side==1 and ml[i]<=prices[-1]*(1-step): prices.append(prices[-1]*(1-step)); lots.append(lots[-1]*mult)
            elif side==-1 and mh[i]>=prices[-1]*(1+step): prices.append(prices[-1]*(1+step)); lots.append(lots[-1]*mult)
            else: break
        wl=max(wl,len(lots))
        L=sum(lots); be=sum(p*q for p,q in zip(prices,lots))/L
        px=ml[i] if side==1 else mh[i]
        u=sum(q*(px-p)/p*side for p,q in zip(prices,lots))-L*cost_side*2
        mdd=min(mdd,eq+u-peak)
        tp_px=be*(1+tp) if side==1 else be*(1-tp)
        if (mh[i]>=tp_px) if side==1 else (ml[i]<=tp_px):
            close(tp_px); side=0; lots=[]; prices=[]; continue
        if trend[i]!=side:
            close(mc[i]); side=0; lots=[]; prices=[]
    return eq*100,mdd*100,wl

inds={
 'SMA200': np.where(hc>pd.Series(hc).rolling(200).mean().values,1,-1),
 'EMA50' : np.where(hc>pd.Series(hc).ewm(span=50).mean().values,1,-1),
 'EMA9'  : np.where(hc>pd.Series(hc).ewm(span=9).mean().values,1,-1),
}
print("1M intrabar replay 22-26, trend-grid close-on-flip, cost จริง $0.35:")
for ind,tr in inds.items():
    for mult in [1.5]:
        eq,dd,wl=run(tr,mult)
        rdd=eq/abs(dd) if dd<0 else 99
        print(f"{ind:7s} x{mult}: profit {eq:+7.0f}%ofBase maxDD {dd:7.0f}% maxLv {wl:2d} ret/DD {rdd:4.2f}")
