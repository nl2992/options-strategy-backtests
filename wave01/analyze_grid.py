import sys, pickle, json; sys.path.insert(0,'src')
import numpy as np, pandas as pd
from options_lab.data import load_market
from options_lab.analytics import perf, trade_stats
MKT, eq = load_market(); dates = MKT.dates; n = len(dates)
a, b_ = int(0.6*n), int(0.8*n)
rf = MKT.rf; idx = pd.Index(dates)
gap = pd.Series([(dates[i]-dates[i-1]).days if i else 0 for i in range(n)], index=idx)
rfd = (rf.shift(1).fillna(rf.iloc[0]) * gap / 360.0)
res = pickle.load(open('data/derived_grid.pkl','rb'))
def sl(bl, lo, hi):
    if not len(bl): return bl
    e = pd.to_datetime(bl.entry_date); return bl[(e >= pd.Timestamp(dates[lo+1])) & (e <= pd.Timestamp(dates[hi]))]
rows=[]
for k,(cfg,d,bl) in enumerate(res):
    row=dict(trial=k,strategy=cfg.strategy,delta=cfg.delta,dte=cfg.dte_target,filt=cfg.filt)
    for name,(lo,hi) in dict(dev=(0,a-1),val=(a-1,b_-1)).items():
        pm=perf(d.equity,rfd,lo,hi); ts=trade_stats(sl(bl,lo,hi))
        row.update({f'{name}_{k2}':v for k2,v in {**pm,**ts}.items()})
    rows.append(row)
reg=pd.DataFrame(rows); reg.to_csv('reports/experiment_registry.csv',index=False)
pd.set_option('display.width',250)
print(reg[['strategy','delta','dte','filt','dev_trades','dev_ex_ann','dev_sharpe','dev_pnl','dev_pnl_per_risk','val_trades','val_ex_ann','val_sharpe','val_pnl']].round(3).to_string())
