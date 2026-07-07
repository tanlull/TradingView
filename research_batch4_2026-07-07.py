import pandas as pd, numpy as np

FILES = {
    "12-22": "/sessions/youthful-great-bell/mnt/TradingView/data/XAUUSD_1H_real.csv",
    "20-25": "/sessions/youthful-great-bell/mnt/TradingView/data/XAUUSD_1H_2020_2025.csv",
    "22-26": "/sessions/youthful-great-bell/mnt/TradingView/data/XAUUSD_1H_MT5_export_20220408_20260703.csv",
}
COST=0.0006

def load(fp):
    df=pd.read_csv(fp); df.columns=[x.lower() for x in df.columns]
    tcol=[c for c in df.columns if 'time' in c or 'date' in c][0]
    df['time']=pd.to_datetime(df[tcol],format='mixed',utc=True)
    return df.reset_index(drop=True)

def metrics(rets):
    r=np.array(rets)
    if len(r)<20: return len(r),0,0,0,0
    eq=np.cumprod(1+r); pk=np.maximum.accumulate(eq)
    w=r[r>0]; L=r[r<=0]
    pf=w.sum()/-L.sum() if len(L) and L.sum()<0 else 99
    return len(r), len(w)/len(r)*100, pf, (eq[-1]-1)*100, (eq/pk-1).min()*100

DFS={k:load(v) for k,v in FILES.items()}

# ---------- A) SESSION BREAKOUT ----------
def quiet_block(df):
    # find 8h contiguous block with lowest mean abs return (Asian proxy) per dataset clock
    df=df.copy(); df['hr']=df['time'].dt.hour
    df['ar']=(df['close']/df['open']-1).abs()
    prof=df.groupby('hr')['ar'].mean()
    best=None; bh=0
    for s in range(24):
        hrs=[(s+k)%24 for k in range(8)]
        v=prof.reindex(hrs).mean()
        if best is None or v<best: best=v; bh=s
    return bh

def session_bt(df, rr=2.0, window=8, cost=COST):
    s0=quiet_block(df)
    o=df['open'].values; h=df['high'].values; l=df['low'].values
    hr=df['time'].dt.hour.values
    n=len(o); rets=[]; i=0
    while i<n:
        if hr[i]==s0:  # start of quiet block
            j=i; rh=-1e9; rl=1e9
            while j<n and ((hr[j]-s0)%24)<8: rh=max(rh,h[j]); rl=min(rl,l[j]); j+=1
            # breakout window: next `window` bars
            k=j; end=min(j+window,n); done=False
            while k<end and not done:
                if h[k]>rh:  # long stop order at rh
                    e=max(o[k],rh); sl=rl; risk=(e-sl)/e
                    if risk>0.02 or risk<=0: k+=1; continue
                    tp=e*(1+risk*rr); m=k
                    while m<n:
                        if l[m]<=sl: rets.append((sl-e)/e-cost); done=True; break
                        if h[m]>=tp: rets.append((tp-e)/e-cost); done=True; break
                        if m>k+48: rets.append((o[m]-e)/e-cost); done=True; break
                        m+=1
                    k=m; break
                if l[k]<rl:  # short
                    e=min(o[k],rl); sl=rh; risk=(sl-e)/e
                    if risk>0.02 or risk<=0: k+=1; continue
                    tp=e*(1-risk*rr); m=k
                    while m<n:
                        if h[m]>=sl: rets.append((e-sl)/e-cost); done=True; break
                        if l[m]<=tp: rets.append((e-tp)/e-cost); done=True; break
                        if m>k+48: rets.append((e-o[m])/e-cost); done=True; break
                        m+=1
                    k=m; break
                k+=1
            i=max(k,j)
        else: i+=1
    return metrics(rets), s0

print("=== A) SESSION BREAKOUT (quiet-8h range, break in next 8h, SL=opposite side, RR2) ===")
for name,df in DFS.items():
    (n,wr,pf,ret,dd),s0=session_bt(df)
    print(f"{name}: quietStart hr{s0:02d} | N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")

print("\n--- A variants (rr x window): PF per period ---")
for rr in [1.5,2.5]:
    for w in [6,12]:
        row=[]
        for name,df in DFS.items():
            (n,wr,pf,ret,dd),s0=session_bt(df,rr=rr,window=w)
            row.append(f"{name}:{pf:4.2f}")
        print(f"rr{rr} w{w}: " + "  ".join(row))

# ---------- B) EXIT ENGINEERING on Breakout lb20 ----------
def breakout_trades(df):
    o,h,l,c=(df[k].values for k in('open','high','low','close'))
    hh=pd.Series(h).rolling(20).max().shift(1).values
    ll=pd.Series(l).rolling(20).min().shift(1).values
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    return o,h,l,c,hh,ll,atr

def bt_exit(df, mode, rr=2.5, slf=0.01, cost=COST):
    o,h,l,c,hh,ll,atr=breakout_trades(df)
    n=len(o); rets=[]; i=21
    while i<n-1:
        d=0
        if c[i]>hh[i]: d=1
        elif c[i]<ll[i]: d=-1
        if d:
            e=o[i+1]; sl=e*(1-slf*d); a=atr[i]
            tp=e*(1+slf*rr*d)
            j=i+1; hiw=e; low=e; part=False; acc=0.0; sz=1.0
            while j<n:
                if d==1:
                    if mode=='be' and h[j]>=e*(1+slf) : sl=max(sl,e)
                    if mode=='trail':
                        hiw=max(hiw,c[j]); sl=max(sl,hiw-3*a)
                    if mode=='partial' and not part and h[j]>=e*(1+slf*1.5):
                        acc+=0.5*((e*(1+slf*1.5)-e)/e-cost); sz=0.5; part=True; sl=max(sl,e)
                    if l[j]<=sl: acc+=sz*((sl-e)/e-cost); rets.append(acc); break
                    if mode in('fixed','be') and h[j]>=tp: acc+=sz*((tp-e)/e-cost); rets.append(acc); break
                    if mode=='partial' and part and h[j]>=e*(1+slf*4): acc+=sz*((e*(1+slf*4)-e)/e-cost); rets.append(acc); break
                else:
                    if mode=='be' and l[j]<=e*(1-slf): sl=min(sl,e)
                    if mode=='trail':
                        low=min(low,c[j]); sl=min(sl,low+3*a)
                    if mode=='partial' and not part and l[j]<=e*(1-slf*1.5):
                        acc+=0.5*((e-e*(1-slf*1.5))/e-cost); sz=0.5; part=True; sl=min(sl,e)
                    if h[j]>=sl: acc+=sz*((e-sl)/e-cost); rets.append(acc); break
                    if mode in('fixed','be') and l[j]<=tp: acc+=sz*((e-tp)/e-cost); rets.append(acc); break
                    if mode=='partial' and part and l[j]<=e*(1-slf*4): acc+=sz*((e-e*(1-slf*4))/e-cost); rets.append(acc); break
                j+=1
            else: break
            i=j
        i+=1
    return metrics(rets)

print("\n=== B) EXIT ENGINEERING (Breakout lb20 SL1%) ===")
for mode in ['fixed','be','trail','partial']:
    row=[]
    for name in ['12-22','22-26']:
        n,wr,pf,ret,dd=bt_exit(DFS[name],mode)
        row.append(f"{name}: N{n:4d} WR{wr:5.1f} PF {pf:4.2f} ret{ret:+7.1f}% DD{dd:6.1f}%")
    print(f"{mode:8s} | " + " | ".join(row))

# ---------- C) SLOW TREND ----------
def bt_donchian(df, lb=55, rr=2.5, slf=0.01, cost=COST):
    o,h,l,c=(df[k].values for k in('open','high','low','close'))
    hh=pd.Series(h).rolling(lb).max().shift(1).values
    ll=pd.Series(l).rolling(lb).min().shift(1).values
    n=len(o); rets=[]; i=lb+1
    while i<n-1:
        d=1 if c[i]>hh[i] else (-1 if c[i]<ll[i] else 0)
        if d:
            e=o[i+1]; sl=e*(1-slf*d); tp=e*(1+slf*rr*d); j=i+1
            while j<n:
                if d==1:
                    if l[j]<=sl: rets.append((sl-e)/e-cost); break
                    if h[j]>=tp: rets.append((tp-e)/e-cost); break
                else:
                    if h[j]>=sl: rets.append((e-sl)/e-cost); break
                    if l[j]<=tp: rets.append((e-tp)/e-cost); break
                j+=1
            else: break
            i=j
        i+=1
    return metrics(rets)

def to_4h(df):
    g=df.set_index('time').resample('4h').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna().reset_index()
    return g

def bt_macross(df4, fast=50, slow=200, slf=0.02, cost=COST):
    o,h,l,c=(df4[k].values for k in('open','high','low','close'))
    ef=pd.Series(c).ewm(span=fast).mean().values; es=pd.Series(c).ewm(span=slow).mean().values
    n=len(o); rets=[]; pos=0; e=sl=0.0
    for i in range(slow,n-1):
        if pos==0:
            if ef[i-1]<=es[i-1] and ef[i]>es[i]: pos=1; e=o[i+1]; sl=e*(1-slf)
            elif ef[i-1]>=es[i-1] and ef[i]<es[i]: pos=-1; e=o[i+1]; sl=e*(1+slf)
        else:
            if pos==1:
                if l[i]<=sl: rets.append((sl-e)/e-cost); pos=0; continue
                if ef[i-1]>=es[i-1] and ef[i]<es[i]:
                    rets.append((o[i+1]-e)/e-cost); pos=-1; e=o[i+1]; sl=e*(1+slf)
            else:
                if h[i]>=sl: rets.append((e-sl)/e-cost); pos=0; continue
                if ef[i-1]<=es[i-1] and ef[i]>es[i]:
                    rets.append((e-o[i+1])/e-cost); pos=1; e=o[i+1]; sl=e*(1-slf)
    return metrics(rets)

print("\n=== C) SLOW TREND ===")
for name,df in DFS.items():
    n,wr,pf,ret,dd=bt_donchian(df,55)
    print(f"Donchian55 1H {name}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")
for name,df in DFS.items():
    d4=to_4h(df)
    n,wr,pf,ret,dd=bt_donchian(d4,20)
    print(f"Donchian20 4H {name}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")
for name,df in DFS.items():
    d4=to_4h(df)
    n,wr,pf,ret,dd=bt_macross(d4)
    print(f"EMA50/200x 4H {name}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")

# ---------- D) REVERSION leftovers ----------
def bt_bbrsi(df, slf=0.01, cost=COST):
    o,h,l,c=(df[k].values for k in('open','high','low','close'))
    s=pd.Series(c); mid=s.rolling(20).mean(); sd=s.rolling(20).std()
    lo=(mid-2*sd).values; up=(mid+2*sd).values; midv=mid.values
    d=s.diff(); g=d.clip(lower=0).rolling(14).mean(); ls=(-d.clip(upper=0)).rolling(14).mean()
    rsi=(100-100/(1+g/ls)).values
    n=len(o); rets=[]; i=21
    while i<n-1:
        dd_=0
        if c[i]<lo[i] and rsi[i]<30: dd_=1
        elif c[i]>up[i] and rsi[i]>70: dd_=-1
        if dd_:
            e=o[i+1]; sl=e*(1-slf*dd_); j=i+1
            while j<n:
                if dd_==1:
                    if l[j]<=sl: rets.append((sl-e)/e-cost); break
                    if c[j]>=midv[j]: rets.append((o[j+1] if j+1<n else c[j])/e-1-cost); break
                else:
                    if h[j]>=sl: rets.append((e-sl)/e-cost); break
                    if c[j]<=midv[j]: rets.append(1-(o[j+1] if j+1<n else c[j])/e-cost); break
                j+=1
            else: break
            i=j
        i+=1
    return metrics(rets)

def bt_vwap(df, x=0.004, slf=0.01, cost=COST):
    df=df.copy(); df['d']=df['time'].dt.date
    tp_=(df['high']+df['low']+df['close'])/3; v=df['volume'] if 'volume' in df and df['volume'].sum()>0 else pd.Series(1.0,index=df.index)
    df['pv']=tp_*v; df['cv']=v
    df['vwap']=df.groupby('d')['pv'].cumsum()/df.groupby('d')['cv'].cumsum()
    o,h,l,c,vw=(df[k].values for k in('open','high','low','close','vwap'))
    n=len(o); rets=[]; i=1
    while i<n-1:
        dd_=0
        if c[i]<vw[i]*(1-x): dd_=1
        elif c[i]>vw[i]*(1+x): dd_=-1
        if dd_:
            e=o[i+1]; sl=e*(1-slf*dd_); j=i+1
            while j<n:
                if dd_==1:
                    if l[j]<=sl: rets.append((sl-e)/e-cost); break
                    if h[j]>=vw[j]: rets.append(max(vw[j],l[j])/e-1-cost); break
                else:
                    if h[j]>=sl: rets.append((e-sl)/e-cost); break
                    if l[j]<=vw[j]: rets.append(1-min(vw[j],h[j])/e-cost); break
                j+=1
            else: break
            i=j
        i+=1
    return metrics(rets)

print("\n=== D) REVERSION leftovers ===")
for name,df in DFS.items():
    n,wr,pf,ret,dd=bt_bbrsi(df)
    print(f"BB+RSI    1H {name}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")
for name,df in DFS.items():
    n,wr,pf,ret,dd=bt_vwap(df)
    print(f"VWAP rev  1H {name}: N {n:4d} WR {wr:5.1f}% PF {pf:5.2f} ret {ret:+7.1f}% DD {dd:6.1f}%")
