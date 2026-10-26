import sys; sys.path.insert(0,'src')
import pandas as pd, numpy as np
from options_lab import earnings
from options_lab.analytics import block_boot_ci
frames=[]
for s in ('long_straddle','long_strangle','short_condor'):
    for slip in (1.0,0.5,1.5):
        d=earnings.run(s,slip=slip); d['slip']=slip; frames.append(d)
al=pd.concat(frames); al.to_parquet('reports/earnings_trades.parquet')
rows=[]
for (s,sl),g in al.groupby(['structure','slip']):
    r=g.ret_on_risk.values; rng=np.random.default_rng(0)
    bs=[rng.choice(r,len(r)).mean() for _ in range(2000)]
    n=len(g); cut=g.announce.sort_values().iloc[int(.6*n)]; cut2=g.announce.sort_values().iloc[int(.8*n)]
    rows.append(dict(structure=s,slip=sl,events=n,mean_ret_on_risk=r.mean(),ci_lo=np.quantile(bs,.025),ci_hi=np.quantile(bs,.975),hit=(g.ret_on_risk>0).mean(),
        median=np.median(r), dev=g[g.announce<cut].ret_on_risk.mean(), val=g[(g.announce>=cut)&(g.announce<cut2)].ret_on_risk.mean(), test=g[g.announce>=cut2].ret_on_risk.mean(),
        implied_move=g.implied_move.mean(), realized_move=g.move.mean(), usd_pnl_200k=g.pnl.sum(), size0=(g.n<1).mean()))
res=pd.DataFrame(rows); res.to_csv('reports/earnings_results.csv',index=False)
pd.set_option('display.width',250); print(res.round(4).to_string())
e=al[(al.structure=='long_straddle')&(al.slip==1.0)]
print(e.groupby('ticker').agg(n=('ret_on_risk','size'),ret=('ret_on_risk','mean'),imp=('implied_move','mean'),mv=('move','mean')).round(3).to_string())
