"""Frozen evaluation. Selection uses ONLY dev rows of the registry; test slice computed once here."""
import sys, pickle, json, dataclasses, os; sys.path.insert(0,'src')
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from options_lab.data import load_market
from options_lab.engine import run, Cfg
from options_lab.analytics import perf, trade_stats, block_boot_ci, newey_west_t, deflated_sharpe
MKT, eq = load_market(); dates = MKT.dates; n = len(dates); a, b_ = int(0.6*n), int(0.8*n)
rf = MKT.rf; idx = pd.Index(dates)
gap = pd.Series([(dates[i]-dates[i-1]).days if i else 0 for i in range(n)], index=idx)
rfd = rf.shift(1).fillna(rf.iloc[0]) * gap / 360.0
reg = pd.read_csv('reports/experiment_registry.csv')
os.makedirs('reports/figures', exist_ok=True)
def job(cfg):
    d, b, r, pos = run(MKT, cfg); return d, b, r
def runmany(cfgs):
    with ProcessPoolExecutor(max_workers=8, mp_context=mp.get_context('fork')) as ex: return list(ex.map(job, cfgs))
def sl(bl, lo, hi):
    if not len(bl): return bl
    e = pd.to_datetime(bl.entry_date); return bl[(e >= pd.Timestamp(dates[lo+1])) & (e <= pd.Timestamp(dates[hi]))]
TEST = (b_-1, n-1); DEV=(0,a-1); VAL=(a-1,b_-1)
# ---- frozen selection: per strategy, max dev Sharpe with >=30 dev trades (dev only) ----
sel = {}
for s, g in reg.groupby('strategy'):
    g = g[g.dev_trades >= 30]
    r = g.sort_values('dev_sharpe', ascending=False).iloc[0]; sel[s] = r
selcfg = {s: Cfg(strategy=s, delta=float(r.delta), dte_target=int(r.dte), filt=r.filt) for s, r in sel.items()}
ctrl = {s: dataclasses.replace(c, filt='none') for s, c in selcfg.items()}
json.dump({s: dataclasses.asdict(c) for s, c in selcfg.items()}, open('reports/frozen_selection.json','w'), default=str, indent=1)
order = list(selcfg)
cfgs = [selcfg[s] for s in order] + [ctrl[s] for s in order]
stress_defs = {'fee2x': dict(fee_mult=2.0), 'slip1.5': dict(slip=1.5), 'slip2.0': dict(slip=2.0), 'slip0.5_optimistic': dict(slip=0.5), 'delay1': dict(entry_delay=1)}
for s in order:
    for k, kw in stress_defs.items(): cfgs.append(dataclasses.replace(selcfg[s], **kw))
SC = {50_000: (('SPY',2.0),('QQQ',2.0),('SPX',5.0)), 100_000: (('SPY',5.0),('QQQ',5.0),('SPX',5.0)), 200_000: None, 300_000: None}
for s in order:
    for eqv, w in SC.items():
        kw = dict(equity0=float(eqv)); 
        if w: kw['widths'] = w
        cfgs.append(dataclasses.replace(selcfg[s], **kw))
# placebo: shuffled filter for selected filtered configs (20 seeds)
plc = []
for s in order:
    if selcfg[s].filt != 'none':
        for sd in range(20): plc.append((s, dataclasses.replace(selcfg[s], shuffle_seed=sd)))
cfgs += [c for _, c in plc]
print(len(cfgs), 'runs', flush=True)
out = runmany(cfgs)
k = 0
main = {s: out[i] for i, s in enumerate(order)}; k = len(order)
ctl = {s: out[k+i] for i, s in enumerate(order)}; k += len(order)
stress = {}
for s in order:
    for key in stress_defs: stress[(s, key)] = out[k]; k += 1
scen = {}
for s in order:
    for eqv in SC: scen[(s, eqv)] = out[k]; k += 1
placebo = {}
for (s, c), o in zip(plc, out[k:]): placebo.setdefault(s, []).append(o)
# ---- benchmark SPY + cash ----
spy = eq[eq.ticker=='SPY'].set_index('date').total_return; spy.index = [x.date() if hasattr(x,'date') else x for x in spy.index]
spy = spy.reindex(dates).fillna(0.0); spy_eq = 200000*(1+spy).cumprod(); cash_eq = 200000*(1+rfd).cumprod()
def P(d, w, eq0=200000): return perf(d.equity, rfd, *w)
rows = []; 
for s in order:
    d, bl, rj = main[s]; dc, bc, _ = ctl[s]
    r = d.equity.pct_change().iloc[1:]; ex = (r - rfd.reindex(r.index)).iloc[TEST[0]:TEST[1]].values
    ci = block_boot_ci(ex); nw = newey_west_t(ex)
    pt, pd_, pv = P(d, TEST), P(d, DEV), P(d, VAL)
    pc = P(dc, TEST)
    st = {key: P(stress[(s,key)][0], TEST) for key in stress_defs}
    pl = [P(o[0], TEST)['ex_ann'] for o in placebo.get(s, [])]
    ts = trade_stats(sl(bl, *TEST)); tc = trade_stats(sl(bc, *TEST))
    gate = dict(
        test_pos=pt.get('ex_ann', -1) > 0, ci_pos=ci[0] > 0, dev_pos=pd_.get('ex_ann', -1) > 0, val_pos=pv.get('ex_ann', -1) > 0,
        beats_ctrl=pt.get('ex_ann', -1) > pc.get('ex_ann', 9), stress_ok=st['fee2x'].get('ex_ann', -1) > 0 and st['slip1.5'].get('ex_ann', -1) > 0,
        n_ok=ts.get('trades', 0) >= 30)
    dec = 'PROMOTE' if all(gate.values()) else ('WATCHLIST' if gate['test_pos'] and gate['dev_pos'] else 'REJECT')
    rows.append(dict(strategy=s, config=f"d={selcfg[s].delta} dte={selcfg[s].dte_target} filt={selcfg[s].filt}",
        dev_ex=pd_.get('ex_ann'), val_ex=pv.get('ex_ann'), test_ex=pt.get('ex_ann'), test_ci_lo=ci[0], test_ci_hi=ci[1], test_nw_t=nw,
        test_sharpe=pt.get('sharpe'), test_maxdd=pt.get('maxdd'), test_es95=pt.get('es95'), test_total=pt.get('total'),
        test_trades=ts.get('trades'), test_hit=ts.get('hit'), test_pnl=ts.get('pnl'), test_fees=ts.get('fees'), test_spread_cost=ts.get('spread_cost'),
        ctrl_test_ex=pc.get('ex_ann'), ctrl_test_pnl=tc.get('pnl'), ctrl_trades=tc.get('trades'),
        fee2x=st['fee2x'].get('ex_ann'), slip1_5=st['slip1.5'].get('ex_ann'), slip2=st['slip2.0'].get('ex_ann'), slip0_5_opt=st['slip0.5_optimistic'].get('ex_ann'), delay1=st['delay1'].get('ex_ann'),
        placebo_mean=np.mean(pl) if pl else np.nan, placebo_p90=np.quantile(pl, .9) if pl else np.nan, **{f'gate_{k2}': v for k2, v in gate.items()}, decision=dec))
sc = pd.DataFrame(rows); sc.to_csv('reports/05_strategy_scorecard.csv', index=False)
# DSR across all 72 trials (dev Sharpe per-day units)
srs = reg.dev_sharpe.values / np.sqrt(252)
sc['dsr_dev'] = [deflated_sharpe(sel[s].dev_sharpe/np.sqrt(252), srs, a-63) for s in order]
sc.to_csv('reports/05_strategy_scorecard.csv', index=False)
# capital scenarios
cap = []
for (s, eqv), (d, bl, rj) in scen.items():
    pt = P(d, TEST); pa = P(d, (0, n-1)); ts = trade_stats(sl(bl, *TEST))
    cap.append(dict(strategy=s, equity0=eqv, trades_full=len(bl), trades_test=ts.get('trades'), test_ex_ann=pt.get('ex_ann'), test_maxdd=pt.get('maxdd'),
                    test_pnl=ts.get('pnl'), contracts_avg=bl.n.mean() if len(bl) else 0, rej_size=rj.get('risk_cap_or_size_lt_1', 0), rej_all=json.dumps(rj)))
pd.DataFrame(cap).to_csv('reports/04_capital_capacity.csv', index=False)
# benchmark
bm = dict(spy_test=perf(spy_eq, rfd, *TEST), cash_test=perf(cash_eq, rfd, *TEST), spy_dev=perf(spy_eq, rfd, *DEV), spy_val=perf(spy_eq, rfd, *VAL))
json.dump(bm, open('reports/benchmarks.json','w'), default=float, indent=1)
# ledgers
bl_all = pd.concat([main[s][1].assign(variant='selected') for s in order] + [ctl[s][1].assign(variant='control') for s in order])
bl_all.to_parquet('reports/trade_blotter.parquet')
pd.concat([main[s][0].assign(strategy=s, variant='selected') for s in order]).to_parquet('reports/daily_portfolio.parquet')
# figures
fig, ax = plt.subplots(2, 2, figsize=(13, 8))
for axx, s in zip(ax.ravel(), order):
    d = main[s][0]; axx.plot(d.index, d.equity, label=f'{s} selected'); axx.plot(ctl[s][0].index, ctl[s][0].equity, label='unfiltered control', alpha=.7)
    axx.plot(cash_eq.index, cash_eq.values, label='cash (rf)', ls=':'); axx.plot(spy_eq.index, spy_eq.values, label='SPY B&H', alpha=.4)
    for x in (dates[a], dates[b_]): axx.axvline(x, color='k', lw=.6, ls='--')
    axx.set_title(f'{s} {selcfg[s].delta}/{selcfg[s].dte_target}/{selcfg[s].filt} — dev | val | test'); axx.legend(fontsize=7)
plt.tight_layout(); plt.savefig('reports/figures/equity_curves.png', dpi=110); plt.close()
fig, ax = plt.subplots(1, 4, figsize=(15, 3.5))
for axx, s in zip(ax, order):
    b = main[s][1]; axx.hist(b.pnl, bins=30); axx.set_title(f'{s} trade P&L (all, n={len(b)})')
plt.tight_layout(); plt.savefig('reports/figures/pnl_hist.png', dpi=110); plt.close()
fig, ax = plt.subplots(4, 3, figsize=(10, 11))
for r_, s in enumerate(order):
    for c_, f in enumerate(('none', 'f1', 'f2')):
        g = reg[(reg.strategy == s) & (reg.filt == f)].pivot(index='dte', columns='delta', values='dev_ex_ann')
        im = ax[r_, c_].imshow(g.values, aspect='auto'); ax[r_, c_].set_xticks(range(len(g.columns)), g.columns); ax[r_, c_].set_yticks(range(len(g.index)), g.index)
        ax[r_, c_].set_title(f'{s} {f} dev excess ann', fontsize=8)
        for (i, j), v in np.ndenumerate(g.values): ax[r_, c_].text(j, i, f'{v:.3f}', ha='center', va='center', fontsize=7, color='w')
plt.tight_layout(); plt.savefig('reports/figures/param_heatmap_dev.png', dpi=110); plt.close()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
print(sc.T.to_string()); print(pd.DataFrame(cap).drop(columns='rej_all').to_string()); print(json.dumps(bm, default=float, indent=1)[:1500])
