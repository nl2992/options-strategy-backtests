"""Wave-3 decisions under the pre-registered rules (wave3/PREREGISTRATION.md) -> wave3/results/decisions3.csv etc."""
import sys, pathlib, numpy as np, pandas as pd
W = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(W.parent / "wave2"))
from analysis import perf, nw_t, block_boot_ci, deflated_sharpe, romano_wolf

RES, DEV_END = W / "results", 20231231
per = lambda d: np.where(np.asarray(d) <= DEV_END, "dev", "test")
FILES = {"S1": "s_events", "S2": "s_events", "S4": "s_events", "S3": "s3", "S5": "s5", "S6": "s6", "S7": "s7", "S8": "s_calendar", "S9": "s_calendar", "S10": "s_calendar"}
PRIMARY = {"S1": "S1_hedged_5", "S2": "S2_hedged_h20", "S5": "S5_contango", "S6": "S6_ls", "S8": "S8_nr", "S9": "S9_fomc", "S10": "S10_tom"}
EXPLORATORY = {"S3": "S3_all_h5", "S4": "S4_hedged", "S7": "S7_pin_t15"}

daily = {f: pd.read_csv(RES / f"{f}_daily.csv").assign(period=lambda x: per(x.date)) for f in set(FILES.values())}
n_trials = 63 + sum(d.variant.nunique() for d in daily.values())

# SPY daily close-to-close returns for the S5 alpha regression
eq = pd.read_csv(W.parent / "wave2/extracts/ctx_equity.csv")
spy = eq[eq.ticker == "SPY"].set_index("date").sort_index()
spy_r = (spy.close_raw / spy.close_raw.shift() * spy.share_adj.shift() / spy.share_adj - 1 + spy.div_ret).rename("spy")

rows = []
for s, f in FILES.items():
    d = daily[f][daily[f].variant.str.startswith(s + "_")]
    rw = romano_wolf(d[d.period == "dev"].pivot(index="date", columns="variant", values="ret"), draws=1000)
    for (v, p), g in d.groupby(["variant", "period"]):
        x = perf(g.ret.values)
        if not x: continue
        sr = g.ret.mean() / g.ret.std() if g.ret.std() > 0 else 0
        j = g.set_index("date").ret.to_frame().join(spy_r, how="inner").dropna()
        b, a = np.polyfit(j.spy, j.ret, 1) if len(j) > 30 else (np.nan, np.nan)
        rows.append(dict(strategy=s, variant=v, period=p, role="primary" if PRIMARY.get(s) == v else "exploratory" if EXPLORATORY.get(s) == v else "secondary",
                         rw_p_dev=rw.get(v, np.nan), dsr=deflated_sharpe(sr, len(g), n_trials) if p == "dev" else np.nan,
                         beta_spy=b, alpha_ann=a * 252, alpha_nw_t=nw_t((j.ret - b * j.spy).values) if len(j) > 30 else np.nan, **x))
sc = pd.DataFrame(rows)

# trade-level tests
ev = []
def add(s, v, g, col, dcol):
    for p, h in g.assign(period=per(g[dcol])).groupby("period"):
        y = h[col].dropna(); yc = h.groupby(dcol)[col].mean().dropna()
        ev.append(dict(strategy=s, variant=v, period=p, n=len(y), mean=y.mean(), median=y.median(), hit=(y > 0).mean(),
                       t_clustered=nw_t(yc.values, lags=0) if len(yc) >= 10 else np.nan))
te = pd.read_csv(RES / "s_events_trades.csv"); te = te[te.status == "filled"]
for v, g in te.groupby("variant"): add(v.split("_")[0], v, g, "r_hedged", "d_out")
t5 = pd.read_csv(RES / "s5_trades.csv"); t5 = t5[t5.status.isin(["filled", "size_lt1"])]
for v, g in t5.groupby("variant"): add("S5", v, g, "ret_on_risk", "exp")
t6 = pd.read_csv(RES / "s6_trades.csv"); t6 = t6[t6.status == "settled"]
for v, g in t6.groupby("variant"): add("S6", v, g, "ret_on_premium", "exp")
t7 = pd.read_csv(RES / "s7_trades.csv"); t7 = t7[t7.status == "filled"]
for v, g in t7.groupby("variant"): add("S7", v, g, "ret_on_risk", "date")
ev = pd.DataFrame(ev)
# S7 paired: pin minus ATM on days both filled
pair = []
for tau in ["t14", "t15"]:
    a = t7[t7.variant == f"S7_pin_{tau}"].set_index("date").ret_on_risk; b = t7[t7.variant == f"S7_atm_{tau}"].set_index("date").ret_on_risk
    dd = (a - b).dropna()
    pair.append(dict(tau=tau, days=len(dd), mean_diff=dd.mean(), nw_t=nw_t(dd.values)))
pair = pd.DataFrame(pair)

dec = []
for s, v in {**PRIMARY, **EXPLORATORY}.items():
    a = sc[(sc.strategy == s) & (sc.variant == v)].set_index("period")
    if s in EXPLORATORY: verdict = "EXPLORATORY (needs 2025 data)"
    elif not {"dev", "test"} <= set(a.index): verdict = "MISSING PERIOD"
    else:
        fails = [n for n, bad in [("dev mean<=0", a.ann_ret["dev"] <= 0), ("test mean<=0", a.ann_ret["test"] <= 0), ("dev ex-top5<=0", a.ann_ret_ex_top5["dev"] <= 0)] if bad]
        verdict = "REJECT: " + "; ".join(fails) if fails else "PASS"
    e = ev[(ev.variant == v)].set_index("period")
    dec.append(dict(strategy=s, variant=v, verdict=verdict, dev_ann=a.ann_ret.get("dev"), dev_sharpe=a.sharpe.get("dev"), dev_nw_t=a.nw_t.get("dev"),
                    dev_dsr=a.dsr.get("dev"), rw_p_dev=a.rw_p_dev.get("dev"), test_ann=a.ann_ret.get("test"), test_sharpe=a.sharpe.get("test"),
                    test_nw_t=a.nw_t.get("test"), alpha_dev=a.alpha_ann.get("dev"), beta_dev=a.beta_spy.get("dev"),
                    ev_n_dev=e.n.get("dev"), ev_mean_dev=e["mean"].get("dev"), ev_t_dev=e.t_clustered.get("dev"),
                    ev_n_test=e.n.get("test"), ev_mean_test=e["mean"].get("test"), ev_t_test=e.t_clustered.get("test")))
dec = pd.DataFrame(dec)
sc.to_csv(RES / "scorecard3_daily.csv", index=False); ev.to_csv(RES / "scorecard3_events.csv", index=False)
pair.to_csv(RES / "scorecard3_s7_pair.csv", index=False); dec.to_csv(RES / "decisions3.csv", index=False)
print(f"trials (wave2+wave3 variants) = {n_trials}")
with pd.option_context("display.width", 300, "display.max_columns", 40):
    print(dec.round(4).to_string(index=False)); print(pair.round(4).to_string(index=False))
