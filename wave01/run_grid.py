"""Pre-registered grid. Computes ONLY dev/val slices for the registry; test slice is untouched here."""
import sys, itertools, pickle, time, json, os; sys.path.insert(0, 'src')
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from options_lab.data import load_market
from options_lab.engine import run, Cfg
from options_lab.analytics import perf, trade_stats
MKT = None
def split_idx(n):  # positional indices into returns (len n-1)
    a = int(0.6 * n); b = int(0.8 * n); return a, b
def job(cfg):
    d, b, r, pos = run(MKT, cfg)
    return cfg, d, b, r
if __name__ == "__main__":
    MKT, eq = load_market(); n = len(MKT.dates)
    a, b_ = split_idx(n)
    grid = [Cfg(strategy=s, delta=dl, dte_target=dt, filt=f) for s in ('pcs', 'ccs', 'ic', 'dv')
            for dl in ((0.15, 0.20, 0.30) if True else ()) for dt in (30, 45) for f in ('none', 'f1', 'f2')]
    # dv: delta = long-leg delta, grid 0.50/0.60/0.70
    grid = [replace if False else c for c in grid]
    import dataclasses
    grid = [dataclasses.replace(c, delta={0.15: 0.50, 0.20: 0.60, 0.30: 0.70}[c.delta]) if c.strategy == 'dv' else c for c in grid]
    print(len(grid), 'trials', flush=True)
    ctx = mp.get_context('fork'); t = time.time(); res = []
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 4), mp_context=ctx) as ex:
        for k, out in enumerate(ex.map(job, grid, chunksize=1)):
            res.append(out)
            if k % 12 == 0: print(k, round(time.time() - t), flush=True)
    rf = MKT.rf
    rows = []
    for k, (cfg, d, bl, rj) in enumerate(res):
        row = dict(trial=k, strategy=cfg.strategy, delta=cfg.delta, dte=cfg.dte_target, filt=cfg.filt, equity0=cfg.equity0, seed=0,
                   code_sha='no-git', ts=pd.Timestamp.now().isoformat(), reject_json=json.dumps(rj))
        for name, (lo, hi) in dict(dev=(0, a - 1), val=(a - 1, b_ - 1)).items():
            pm = perf(d.equity, rf, lo, hi)
            sub = bl[(pd.to_datetime(bl.entry_date) >= pd.Timestamp(MKT.dates[lo + 1])) & (pd.to_datetime(bl.entry_date) <= pd.Timestamp(MKT.dates[min(hi, n - 1)]))] if len(bl) else bl
            row.update({f'{name}_{k2}': v for k2, v in {**pm, **trade_stats(sub)}.items()})
        rows.append(row)
    reg = pd.DataFrame(rows); os.makedirs('reports', exist_ok=True)
    reg.to_csv('reports/experiment_registry.csv', index=False)
    pickle.dump([(c, d, b) for c, d, b, r in res], open('data/derived_grid.pkl', 'wb'))
    print(reg[['strategy', 'delta', 'dte', 'filt', 'dev_trades', 'dev_sharpe', 'dev_pnl', 'val_sharpe', 'val_pnl']].to_string())
