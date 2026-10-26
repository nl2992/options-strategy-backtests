"""Statistics used by the scorecard, the portfolio and the figures."""
import numpy as np, pandas as pd
from scipy import stats



def nw_t(x, lags=5):
    """Newey-West t-stat of the mean."""
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 10: return np.nan
    e = x - x.mean(); v = e @ e / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def block_boot_ci(x, stat=np.mean, block=10, draws=5000, seed=0, alpha=.05):
    """Stationary (Politis-Romano) bootstrap percentile CI."""
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 20: return (np.nan, np.nan)
    rng = np.random.default_rng(seed); out = np.empty(draws)
    for b in range(draws):
        idx = np.empty(n, int); i = rng.integers(n)
        for j in range(n):
            idx[j] = i
            i = rng.integers(n) if rng.random() < 1 / block else (i + 1) % n
        out[b] = stat(x[idx])
    return tuple(np.quantile(out, [alpha / 2, 1 - alpha / 2]))


def perf(r, ann=252):
    """Daily excess-return series -> summary row."""
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    if len(r) < 2: return {}
    eq = np.cumprod(1 + r); dd = eq / np.maximum.accumulate(eq) - 1
    q = np.quantile(r, .025)
    srt = np.sort(r)
    return dict(days=len(r), ann_ret=r.mean() * ann, ann_vol=r.std(ddof=1) * np.sqrt(ann),
                sharpe=r.mean() / r.std(ddof=1) * np.sqrt(ann) if r.std() > 0 else np.nan,
                nw_t=nw_t(r), max_dd=dd.min(), es975=r[r <= q].mean(), worst_day=r.min(),
                ann_ret_ex_top5=(r.sum() - srt[-5:].sum()) / len(r) * ann, active_days=int((r != 0).sum()))


def deflated_sharpe(sr_daily, n_obs, n_trials, skew=0., kurt=3., sr_var_trials=None):
    """Bailey & Lopez de Prado (2014) DSR: P(true SR > E[max SR of n_trials null trials])."""
    g = 0.5772156649
    v = sr_var_trials if sr_var_trials is not None else 1.0 / n_obs
    emax = np.sqrt(v) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    den = np.sqrt((1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2) / (n_obs - 1))
    return stats.norm.cdf((sr_daily - emax) / den)


def fama_macbeth(panel, y, x, date="date", lags=5):
    """Per-date OLS slope of y on x (cross-section), NW t on the slope series."""
    sl = []
    for d, g in panel.dropna(subset=[y, x]).groupby(date):
        if len(g) >= 5 and g[x].std() > 0:
            sl.append((d, np.polyfit(g[x], g[y], 1)[0]))
    s = pd.Series(dict(sl)).sort_index()
    return dict(mean_slope=s.mean(), nw_t=nw_t(s.values, lags), n_dates=len(s)), s


if __name__ == "__main__":  # self-checks
    rng = np.random.default_rng(1)
    z = rng.normal(0, 1, 5000)
    assert abs(nw_t(z)) < 4 and nw_t(z + .2) > 8
    lo, hi = block_boot_ci(rng.normal(1, 1, 500), draws=500)
    assert lo < 1 < hi
    assert deflated_sharpe(0.0, 750, 100) < .05 and deflated_sharpe(0.3, 750, 1) > .99
    print("analysis self-checks ok")
