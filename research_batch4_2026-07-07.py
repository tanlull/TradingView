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

# ---------- E) per-trade martingale on BB+RSI (WR 55%) ----------
def raw_rets(df):
    # reuse bb+rsi engine, return per-trade returns (frac of notional, SL=1%)
    m=bt_bbrsi(df)  # just to ensure same params; recompute inline for rets
    o,h,l,c=(df[k].values for k in('open','high','low','close'))
    s=pd.Series(c); mid=s.rolling(20).mean(); sd=s.rolling(20).std()
    lo=(mid-2*sd).values; up=(mid+2*sd).values; midv=mid.values
    d=s.diff(); g=d.clip(lower=0).rolling(14).mean(); ls=(-d.clip(upper=0)).rolling(14).mean()
    rsi=(100-100/(1+g/ls)).values
    n=len(o); rets=[]; i=21; slf=0.01
    while i<n-1:
        dd_=0
        if c[i]<lo[i] and rsi[i]<30: dd_=1
        elif c[i]>up[i] and rsi[i]>70: dd_=-1
        if dd_:
            e=o[i+1]; sl=e*(1-slf*dd_); j=i+1
            while j<n:
                if dd_==1:
                    if l[j]<=sl: rets.append((sl-e)/e-COST); break
                    if c[j]>=midv[j]: rets.append((o[j+1] if j+1<n else c[j])/e-1-COST); break
                else:
                    if h[j]>=sl: rets.append((e-sl)/e-COST); break
                    if c[j]<=midv[j]: rets.append(1-(o[j+1] if j+1<n else c[j])/e-COST); break
                j+=1
            else: break
            i=j
        i+=1
    return np.array(rets)

def mg_sim(rets, mult=2.0, cap=None, base_risk=0.01):
    # size in units of base risk; R multiple = ret/0.01 (SL=1% of price)
    eq=1.0; peak=1.0; mdd=0.0; size=1.0; streak=0; wstreak=0; peak_size=1.0
    for r in rets:
        R=r/0.01
        eq*= (1+base_risk*size*R)
        peak=max(peak,eq); mdd=min(mdd,eq/peak-1)
        if eq<=0.01: return eq,mdd,wstreak,peak_size,True
        if r<=0:
            streak+=1; wstreak=max(wstreak,streak)
            size=size*mult
            if cap: size=min(size,mult**cap)
        else:
            streak=0; size=1.0
        peak_size=max(peak_size,size)
    return eq,mdd,wstreak,peak_size,False

print("\n=== E) per-trade martingale on BB+RSI (base risk 1%/ไม้) ===")
for name,df in DFS.items():
    r=raw_rets(df)
    wr=(r>0).mean()*100
    print(f"{name}: N {len(r)} WR {wr:.1f}%")
    for mult,cap,lab in [(1.0,None,'flat'),(2.0,None,'x2 no-cap'),(2.0,4,'x2 cap4'),(1.5,None,'x1.5 no-cap')]:
        eq,mdd,ws,ps,ruin=mg_sim(r,mult,cap)
        tag='💥 RUINED' if ruin else ''
        print(f"   {lab:12s}: final {eq:8.2f}x maxDD {mdd*100:6.1f}% worstStreak {ws:2d} peakSize {ps:6.0f}x {tag}")

# ---------- F) extension-priority sizing on Breakout lb20 ----------
def breakout_trades_ext(df, rr=2.5, slf=0.01, cost=COST):
    o,h,l,c=(df[k].values for k in('open','high','low','close'))
    hh=pd.Series(h).rolling(20).max().shift(1).values
    ll=pd.Series(l).rolling(20).min().shift(1).values
    sma=pd.Series(c).rolling(200).mean().values
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    n=len(o); out=[]; i=201
    while i<n-1:
        d=1 if c[i]>hh[i] else (-1 if c[i]<ll[i] else 0)
        if d:
            ext=d*(c[i]-sma[i])/atr[i]  # how extended in trend direction (ATR units)
            e=o[i+1]; sl=e*(1-slf*d); tp=e*(1+slf*rr*d); j=i+1
            while j<n:
                if d==1:
                    if l[j]<=sl: out.append(((sl-e)/e-cost,ext)); break
                    if h[j]>=tp: out.append(((tp-e)/e-cost,ext)); break
                else:
                    if h[j]>=sl: out.append(((e-sl)/e-cost,ext)); break
                    if l[j]<=tp: out.append(((e-tp)/e-cost,ext)); break
                j+=1
            else: break
            i=j
        i+=1
    return out

def eval_sizing(trades, wfun, base=0.01):
    eq=1.0; pk=1.0; mdd=0.0; gp=0.0; gl=0.0
    for r,ext in trades:
        w=wfun(ext)
        R=r/0.01
        eq*=(1+base*w*R); pk=max(pk,eq); mdd=min(mdd,eq/pk-1)
        x=w*r
        if x>0: gp+=x
        else: gl+=-x
    pf=gp/gl if gl>0 else 99
    return pf,(eq-1)*100,mdd*100,((eq-1)/-(mdd) if mdd<0 else 99)

schemes={
 'baseline w=1'        : lambda e: 1.0,
 'decay: 1/.5/.25 @10/25 ATR' : lambda e: 1.0 if e<=10 else (0.5 if e<=25 else 0.25),
 'skip if ext>25'      : lambda e: 1.0 if e<=25 else 0.0,
 'INVERSE (control)'   : lambda e: 0.25 if e<=10 else (0.5 if e<=25 else 1.0),
}
print("\n=== F) extension-priority sizing (Breakout lb20 RR2.5, ext = dist from SMA200 in ATR) ===")
for name in ['12-22','22-26']:
    tr=breakout_trades_ext(DFS[name])
    exts=np.array([e for _,e in tr])
    print(f"{name}: N {len(tr)} | ext median {np.median(exts):.0f} p75 {np.percentile(exts,75):.0f} p95 {np.percentile(exts,95):.0f}")
    for lab,f in schemes.items():
        pf,ret,dd,rdd=eval_sizing(tr,f)
        print(f"   {lab:28s}: PF {pf:4.2f} ret {ret:+7.1f}% DD {dd:6.1f}% ret/DD {rdd:5.1f}")
# correlation: does extension predict outcome?
for name in ['12-22','22-26']:
    tr=breakout_trades_ext(DFS[name])
    r=np.array([x for x,_ in tr]); e=np.array([x for _,x in tr])
    lowq=r[e<=np.percentile(e,33)]; hiq=r[e>=np.percentile(e,67)]
    print(f"{name}: winrate fresh(ext low33%) {np.mean(lowq>0)*100:.1f}% vs extended(hi33%) {np.mean(hiq>0)*100:.1f}% | avgR fresh {lowq.mean()/0.01:+.3f} vs ext {hiq.mean()/0.01:+.3f}")

# ---------- G) boost sizing when extended ----------
boost={
 'baseline w=1'          : lambda e: 1.0,
 'boost x1.5 if ext>7'   : lambda e: 1.5 if e>7 else 1.0,
 'linear 1..2x (0-15ATR)': lambda e: 1.0+min(max(e,0),15)/15,
 'only-extended (skip fresh<=4)': lambda e: 1.0 if e>4 else 0.0,
}
print("\n=== G) BOOST size when extended, all 3 periods ===")
for name in ['12-22','20-25','22-26']:
    tr=breakout_trades_ext(DFS[name])
    r=np.array([x for x,_ in tr]); e=np.array([x for _,x in tr])
    lowq=r[e<=np.percentile(e,33)]; hiq=r[e>=np.percentile(e,67)]
    print(f"{name}: N {len(tr)} | avgR fresh {lowq.mean()/0.01:+.3f} vs extended {hiq.mean()/0.01:+.3f}")
    for lab,f in boost.items():
        pf,ret,dd,rdd=eval_sizing(tr,f)
        print(f"   {lab:30s}: PF {pf:4.2f} ret {ret:+7.1f}% DD {dd:6.1f}% ret/DD {rdd:5.1f}")

# ---------- H) win-streak anti-martingale on Breakout lb20 ----------
print("\n=== H) consecutive-win exploitation ===")
for name in ['12-22','20-25','22-26']:
    tr=breakout_trades_ext(DFS[name])
    r=np.array([x for x,_ in tr])
    win=(r>0).astype(int)
    # conditional: P(win | prev win) vs P(win | prev loss), avgR conditional
    pw_w=win[1:][win[:-1]==1].mean()*100
    pw_l=win[1:][win[:-1]==0].mean()*100
    aR_w=r[1:][win[:-1]==1].mean()/0.01
    aR_l=r[1:][win[:-1]==0].mean()/0.01
    # streak of 2 wins
    w2=(win[:-2]==1)&(win[1:-1]==1)
    pw_ww=win[2:][w2].mean()*100 if w2.sum()>20 else float('nan')
    print(f"{name}: P(win|prevW) {pw_w:.1f}% vs P(win|prevL) {pw_l:.1f}% | avgR afterW {aR_w:+.3f} vs afterL {aR_l:+.3f} | P(win|WW) {pw_ww:.1f}%")

def streak_sim(rets, mult, cap, base=0.01):
    eq=1.0; pk=1.0; mdd=0.0; sz=1.0; st=0; gp=0; gl=0
    for r in rets:
        R=r/0.01
        eq*=(1+base*sz*R); pk=max(pk,eq); mdd=min(mdd,eq/pk-1)
        x=sz*r
        gp+= x if x>0 else 0; gl+= -x if x<=0 else 0
        if r>0: st+=1; sz=min(mult**st, mult**cap)
        else: st=0; sz=1.0
    pf=gp/gl if gl>0 else 99
    return pf,(eq-1)*100,mdd*100,((eq-1)/-(mdd) if mdd<0 else 99)

for name in ['12-22','20-25','22-26']:
    tr=breakout_trades_ext(DFS[name])
    r=np.array([x for x,_ in tr])
    print(f"{name}:")
    for lab,mult,cap in [('baseline',1.0,0),('winx1.5 cap3',1.5,3),('winx2 cap3',2.0,3),('winx1.25 cap5',1.25,5)]:
        pf,ret,dd,rdd=streak_sim(r,mult,cap)
        print(f"   {lab:14s}: PF {pf:4.2f} ret {ret:+7.1f}% DD {dd:6.1f}% ret/DD {rdd:5.1f}")
