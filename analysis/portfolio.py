"""Combine the three strategies in one account; idle capital earns SOFR -> results/portfolio/.

Sleeves are the daily excess-return series (over cash) written by the C++ engines.
Weights use 2022-01-03..2023-12-29 only; 2024 is out-of-sample. Two schedules: static (estimated once at 2023-12-29)
and walk-forward (re-estimated at each 2024 month start on an expanding window).
Portfolio total return_t = SOFR accrual_t + sum_i w_i * x_i,t   with  sum_i w_i <= 1, w_i >= 0  (no leverage unless stated).
"""
import sys, pathlib, numpy as np, pandas as pd
from scipy.optimize import minimize
R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "analysis"))
from stats import nw_t

OUT = R / "results/portfolio"
EST_END = 20231231
SLEEVES = {  # label -> (engine output, variant)
    "S1 pre-earn premium": ("earnings_events", "S1_hedged_5"),
    "S2 EAR drift": ("earnings_events", "S2_hedged_h20"),
    "S3 option flow (1d)": ("option_flow", "S3_all_h1"),
}
CAP = 0.5  # no strategy above 50% (with three strategies, weights must still reach 100%)
MKW = f"Markowitz (Bayes-Stein, cap {CAP:.0%})"

# ---------- data ----------
sess = pd.read_csv(R / "data/extracts/ctx_sessions.csv").date.values
X = pd.DataFrame(index=sess, dtype=float)
for lab, (f, v) in SLEEVES.items():
    d = pd.read_csv(R / f"results/{f}_daily.csv"); d = d[d.variant == v].set_index("date").ret
    X[lab] = d.reindex(sess).fillna(0.0)  # outside a sleeve's coverage it holds cash (excess 0)
sofr = pd.read_csv(R / "data/sofr.csv"); sofr["date"] = pd.to_datetime(sofr.date)
dt = pd.to_datetime(pd.Series(sess).astype(str))
rate = sofr.set_index("date").sofr.reindex(pd.date_range(dt.min() - pd.Timedelta(days=10), dt.max())).ffill()
# act/360 accrual from the prior session to this one, at the prior session's fixing
cash = pd.Series([0.0] + [rate[dt[i - 1]] / 100 * (dt[i] - dt[i - 1]).days / 360 for i in range(1, len(dt))], index=sess)

# ---------- estimators ----------
def lw_cov(Y):
    """Ledoit-Wolf shrinkage of the sample covariance toward a scaled identity."""
    Y = Y - Y.mean(0); T, N = Y.shape; S = Y.T @ Y / T; mu = np.trace(S) / N
    d2 = np.sum((S - mu * np.eye(N)) ** 2); b2 = min(d2, sum(np.sum((np.outer(y, y) - S) ** 2) for y in Y) / T ** 2)
    return (b2 / d2) * mu * np.eye(N) + (1 - b2 / d2) * S

def jorion_mean(Y, C):
    """Bayes-Stein (Jorion 1986) shrinkage of means toward the minimum-variance portfolio mean."""
    T, N = Y.shape; m = Y.mean(0); Ci = np.linalg.pinv(C); one = np.ones(N)
    m0 = one @ Ci @ m / (one @ Ci @ one); dlt = m - m0 * one
    lam = (N + 2) / ((N + 2) + T * dlt @ Ci @ dlt)
    return lam * m0 + (1 - lam) * m

def solve(obj, N, cap, full=False):
    # full=True: fully invested (sum = 1); otherwise sum <= 1 with the remainder in SOFR
    cons = [{"type": "eq" if full else "ineq", "fun": lambda w: 1 - w.sum()}]
    r = minimize(obj, np.full(N, 1 / N), bounds=[(0, cap)] * N, constraints=cons, method="SLSQP", options={"maxiter": 500})
    return r.x if r.success else np.full(N, 1 / N)

def weights(method, Y, names, dev_t=None):
    Y = Y.values; N = Y.shape[1]; C = lw_cov(Y); vol = np.sqrt(np.diag(C))
    if method == "1/N": return np.full(N, 1 / N)
    if method == "inverse vol": w = 1 / vol; return w / w.sum()
    if method == MKW:
        m = jorion_mean(Y, C)
        # max-Sharpe is scale-free, so fix the budget (sum = 1) inside the solver; renormalizing afterwards would break the cap
        return solve(lambda w: -(w @ m) / np.sqrt(w @ C @ w + 1e-18), N, CAP, full=True)
    raise ValueError(method)

METHODS = ["1/N", "inverse vol", MKW]
names = list(SLEEVES)
dev = X.index <= EST_END

# ---------- static and walk-forward schedules ----------
W_static, W_wf = {}, {}
for m in METHODS:
    W_static[m] = pd.Series(weights(m, X[dev], names), index=names)
    rows = {}
    for d in X.index[~dev]:
        key = d // 100
        if key not in rows: rows[key] = weights(m, X[X.index < d], names)
    W_wf[m] = rows

def portfolio(m, sched):
    p = pd.Series(0.0, index=X.index)
    for d in X.index:
        w = W_static[m].values if (sched == "static" or d <= EST_END) else W_wf[m][d // 100]
        p[d] = X.loc[d].values @ w
    return p  # excess over cash

def stats(x, c):
    x = x.dropna(); tot = x + c.reindex(x.index); eq = (1 + tot).cumprod()
    return dict(days=len(x), ann_total=(eq.iloc[-1] ** (252 / len(x)) - 1), ann_excess=x.mean() * 252, ann_vol=x.std() * np.sqrt(252),
                sharpe=x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan, nw_t=nw_t(x.values),
                max_dd=(eq / eq.cummax() - 1).min(), sofr_ann=c.reindex(x.index).mean() * 252)

rows, curves = [], {}
for m in METHODS:
    for sched in ["static", "walk-forward"]:
        x = portfolio(m, sched); curves[f"{m} | {sched}"] = x
        for per, msk in [("2022-23 (in-sample)", dev), ("2024 (out-of-sample)", ~dev)]:
            if sched == "walk-forward" and per.startswith("2022"): continue
            rows.append(dict(method=m, schedule=sched, period=per, **stats(x[msk], cash)))
# vol-targeted variants: scale the static weights so in-sample vol = 5%, leverage <= 3 (excess returns scale; financing at SOFR)
for m in ["1/N"]:
    x0 = portfolio(m, "static"); k = min(3.0, 0.05 / (x0[dev].std() * np.sqrt(252)))
    x = k * x0; curves[f"{m} | static, 5% vol target (x{k:.2f})"] = x
    for per, msk in [("2022-23 (in-sample)", dev), ("2024 (out-of-sample)", ~dev)]:
        rows.append(dict(method=f"{m}, 5% vol target", schedule=f"static x{k:.2f}", period=per, **stats(x[msk], cash)))
summ = pd.DataFrame(rows)
cash_only = stats(pd.Series(0.0, index=X.index)[~dev], cash)

# ---------- outputs ----------
OUT.mkdir(parents=True, exist_ok=True)
pd.DataFrame(W_static).to_csv(OUT / "weights_static.csv")
pd.DataFrame({m: pd.DataFrame(W_wf[m], index=names).mean(axis=1) for m in METHODS}).to_csv(OUT / "weights_walkforward_mean.csv")
pd.DataFrame(curves).assign(sofr=cash).to_csv(OUT / "portfolio_daily_excess.csv")
X.to_csv(OUT / "sleeves_daily_excess.csv")
X[dev].corr().to_csv(OUT / "sleeve_corr_dev.csv")
sl = pd.DataFrame({lab: {**{f"dev_{k}": v for k, v in stats(X.loc[dev, lab], cash).items() if k in ("ann_excess", "ann_vol", "sharpe", "nw_t")},
                         **{f"oos_{k}": v for k, v in stats(X.loc[~dev, lab], cash).items() if k in ("ann_excess", "ann_vol", "sharpe", "nw_t")}} for lab in names}).T
sl.to_csv(OUT / "sleeve_stats.csv"); summ.to_csv(OUT / "allocation_summary.csv", index=False)
with pd.option_context("display.width", 250, "display.max_columns", 20):
    print(sl.round(3).to_string()); print(pd.DataFrame(W_static).round(3).to_string())
    print(summ.round(4).to_string(index=False)); print("SOFR only 2024:", {k: round(v, 4) for k, v in cash_only.items()})

# self-check: weights are long-only and fully or partly invested
for m, w in W_static.items(): assert (w >= -1e-9).all() and w.sum() <= 1 + 1e-6, m
assert W_static[MKW].max() <= CAP + 1e-6
for w in W_wf[MKW].values(): assert w.max() <= CAP + 1e-6
