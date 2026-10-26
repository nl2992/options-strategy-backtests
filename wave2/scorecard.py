"""Apply the pre-registered decision rules to the frozen engine outputs -> results/scorecard*.csv.

Primary specs (prereg): F2 eod_bid | H1 fly_t12_L2000 | H2 overnight_L2000 (A1: a1_overnight_L2000) | H3 overnight
| H4 flow | H5 pre_L2000 (A4: a4_pre_chase) | H6 all_L2000.
"""
import numpy as np, pandas as pd
from analysis import RES, perf, nw_t, block_boot_ci, deflated_sharpe, romano_wolf, fama_macbeth, daily, trades, period

PRIMARY = {"h1": ["fly_t12_L2000"], "h2": ["overnight_L2000", "a1_overnight_L2000"], "h3": ["overnight"], "h4": ["flow"],
           "h5": ["pre_L2000", "a4_pre_chase"], "h6": ["all_L2000"]}
EVENT = {"h1": "ret_on_risk", "h2": "ret_on_premium", "h5": "ret_on_premium"}  # trade-level test statistic
MIN_FILLS = 30

rows, ev_rows = [], []
n_trials = sum(daily(h).variant.nunique() for h in PRIMARY)
for h, prims in PRIMARY.items():
    d = daily(h)
    # Romano-Wolf across all variants of the family, dev period only
    wide = d[d.period == "dev"].pivot(index="date", columns="variant", values="ret")
    rw = romano_wolf(wide, draws=1000)
    for (v, p), g in d.groupby(["variant", "period"]):
        x = perf(g.ret.values)
        if not x: continue
        lo, hi = block_boot_ci(g.ret.values, draws=2000) if v in prims else (np.nan, np.nan)
        sr_d = g.ret.mean() / g.ret.std() if g.ret.std() > 0 else 0
        rows.append(dict(strategy=h, variant=v, period=p, primary=v in prims, ci_lo_daily=lo, ci_hi_daily=hi,
                         rw_p_dev=rw.get(v, np.nan), dsr=deflated_sharpe(sr_d, len(g), n_trials) if p == "dev" else np.nan, **x))
    if h in EVENT:
        t = trades(h)
        st = t.status.astype(str)
        t = t[st.str.startswith("filled")]
        for (v, p), g in t.groupby(["variant", "period"]):
            y = g[EVENT[h]].dropna()
            # events clustered by date: average per exit date first
            dcol = {"h1": "date", "h2": "d1", "h5": "d_out"}[h]
            yc = g.groupby(dcol)[EVENT[h]].mean().dropna()
            ev_rows.append(dict(strategy=h, variant=v, period=p, primary=v in prims, fills=len(y), mean=y.mean(), median=y.median(),
                                hit=(y > 0).mean(), t_clustered=nw_t(yc.values, lags=0) if len(yc) >= 10 else np.nan))

sc = pd.DataFrame(rows); ev = pd.DataFrame(ev_rows)

# H4 Fama-MacBeth on the panel (next open-to-open return on each z-signal)
pan = trades("h4").rename(columns={"date": "d"}); pan["date"] = pan.d; pan["period"] = period(pan.d)
fm = []
for p, g in pan.groupby("period"):
    for s in ["z_flow", "z_ivspread", "z_neg_smirk", "z_comp"]:
        r, _ = fama_macbeth(g, "r_next", s)
        fm.append(dict(period=p, signal=s, **r))
fm = pd.DataFrame(fm)

# decision per primary (kill rule)
dec = []
for h, prims in PRIMARY.items():
    for v in prims:
        a = sc[(sc.strategy == h) & (sc.variant == v)].set_index("period")
        e = ev[(ev.strategy == h) & (ev.variant == v)].set_index("period") if h in EVENT else None
        fills = int(e.fills.sum()) if e is not None and len(e) else np.nan
        if e is not None and not (fills >= MIN_FILLS):
            verdict = f"UNTESTABLE (fills={fills})"
        elif "dev" not in a.index or "holdout" not in a.index:
            verdict = "MISSING PERIOD"
        else:
            dv, hv = a.loc["dev"], a.loc["holdout"]
            fails = [n for n, bad in [("dev mean<=0", dv.ann_ret <= 0), ("holdout mean<=0", hv.ann_ret <= 0),
                                      ("dev ex-top5<=0", dv.ann_ret_ex_top5 <= 0)] if bad]
            verdict = "REJECT: " + "; ".join(fails) if fails else ("PASS (dev NW t=%.2f)" % dv.nw_t)
        dec.append(dict(strategy=h, variant=v, fills=fills, verdict=verdict,
                        dev_ann=a.ann_ret.get("dev"), dev_sharpe=a.sharpe.get("dev"), dev_nw_t=a.nw_t.get("dev"), dev_dsr=a.dsr.get("dev"),
                        hold_ann=a.ann_ret.get("holdout"), hold_sharpe=a.sharpe.get("holdout"), rw_p_dev=a.rw_p_dev.get("dev")))
dec = pd.DataFrame(dec)

sc.to_csv(RES / "scorecard_daily.csv", index=False); ev.to_csv(RES / "scorecard_events.csv", index=False)
fm.to_csv(RES / "scorecard_h4_fm.csv", index=False); dec.to_csv(RES / "decisions.csv", index=False)
print(f"wave-2 trials (variants) = {n_trials}")
with pd.option_context("display.width", 250, "display.max_columns", 30):
    print(dec.round(4).to_string(index=False)); print(fm.round(5).to_string(index=False))
    print(ev[ev.primary].round(4).to_string(index=False))
