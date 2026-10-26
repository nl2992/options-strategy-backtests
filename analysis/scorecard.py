"""Performance tables for the three strategies -> results/scorecard_daily.csv, scorecard_events.csv, flow_fama_macbeth.csv.

Fitting period = 2022-2023, out-of-sample = 2024 (the earlier option-flow version uses Jan 2022-Jun 2024 and Jul-Dec 2024).
"""
import sys, pathlib, numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from stats import perf, nw_t, deflated_sharpe, fama_macbeth

RES = ROOT / "results"
N_TRIALS = 88  # variants run across the two research rounds that produced these strategies (deflated Sharpe denominator)
period = lambda d, end: np.where(np.asarray(d) <= end, "fitting", "out-of-sample")
spy = pd.read_csv(ROOT / "data/extracts/ctx_equity.csv").query("ticker == 'SPY'").set_index("date").sort_index()
spy_r = (spy.close_raw / spy.close_raw.shift() * spy.share_adj.shift() / spy.share_adj - 1 + spy.div_ret).rename("spy")

rows = []
for engine, end in [("option_flow", 20231231), ("earnings_events", 20231231), ("option_flow_v1", 20240628)]:
    d = pd.read_csv(RES / f"{engine}_daily.csv")
    d["period"] = period(d.date, end)
    for (v, p), g in d.groupby(["variant", "period"]):
        x = perf(g.ret.values)
        sr = g.ret.mean() / g.ret.std() if g.ret.std() > 0 else 0
        j = g.set_index("date").ret.to_frame().join(spy_r, how="inner").dropna()
        beta = np.polyfit(j.spy, j.ret, 1)[0] if len(j) > 30 else np.nan
        rows.append(dict(engine=engine, variant=v, period=p, beta_spy=beta,
                         dsr=deflated_sharpe(sr, len(g), N_TRIALS) if p == "fitting" else np.nan, **x))
sc = pd.DataFrame(rows)

# per-event returns (beta-hedged), t-statistic on returns averaged by exit date
t = pd.read_csv(RES / "earnings_events_trades.csv").query("status == 'filled'")
t["period"] = period(t.d_out, 20231231)
ev = []
for (v, p), g in t.groupby(["variant", "period"]):
    y = g.r_hedged.dropna(); yc = g.groupby("d_out").r_hedged.mean().dropna()
    ev.append(dict(variant=v, period=p, events=len(y), mean=y.mean(), median=y.median(), hit=(y > 0).mean(), t_clustered=nw_t(yc.values, lags=0)))
ev = pd.DataFrame(ev)

# Fama-MacBeth slope of next open-to-open return on the standardized flow signal (earlier version's panel)
pan = pd.read_csv(RES / "option_flow_v1_trades.csv"); pan["period"] = period(pan.date, 20240628)
fm = pd.DataFrame([dict(period=p, **fama_macbeth(g, "r_next", "z_flow")[0]) for p, g in pan.groupby("period")])

sc.to_csv(RES / "scorecard_daily.csv", index=False); ev.to_csv(RES / "scorecard_events.csv", index=False); fm.to_csv(RES / "flow_fama_macbeth.csv", index=False)
with pd.option_context("display.width", 200, "display.max_columns", 20):
    print(sc[["engine", "variant", "period", "ann_ret", "ann_vol", "sharpe", "nw_t", "max_dd", "ann_ret_ex_top5", "beta_spy", "dsr"]].round(4).to_string(index=False))
    print(ev.round(4).to_string(index=False)); print(fm.round(6).to_string(index=False))
