import numpy as np, pandas as pd

def perf(equity: pd.Series, rf_daily: pd.Series, lo=None, hi=None, ppy=252):
    """equity: daily series; metrics over slice [lo:hi] of positional indices (returns dated at i use eq[i]/eq[i-1])."""
    r = equity.pct_change().iloc[1:]
    ex = r - rf_daily.reindex(r.index).fillna(0.0)
    if lo is not None or hi is not None: r, ex = r.iloc[lo:hi], ex.iloc[lo:hi]
    if len(r) < 20: return dict(n=len(r))
    eq = (1 + r).cumprod(); dd = eq / eq.cummax() - 1
    down = ex[ex < 0]
    es = np.sort(r.values)[: max(1, int(0.05 * len(r)))].mean()
    return dict(n=len(r), cagr=eq.iloc[-1] ** (ppy / len(r)) - 1, ex_ann=ex.mean() * ppy, vol=r.std() * np.sqrt(ppy),
                sharpe=ex.mean() / ex.std() * np.sqrt(ppy) if ex.std() > 0 else np.nan,
                sortino=ex.mean() / np.sqrt((down ** 2).sum() / len(ex)) * np.sqrt(ppy) if len(down) else np.nan,
                maxdd=dd.min(), es95=es, total=eq.iloc[-1] - 1)

def block_boot_ci(x: np.ndarray, stat=lambda a: a.mean() * 252, B=2000, block=10, seed=0, alpha=0.05):
    rng = np.random.default_rng(seed); n = len(x)
    if n < 2 * block: return (np.nan, np.nan)
    nb = int(np.ceil(n / block)); out = np.empty(B)
    for b in range(B):
        st = rng.integers(0, n - block + 1, nb)
        s = np.concatenate([x[j:j + block] for j in st])[:n]
        out[b] = stat(s)
    return tuple(np.quantile(out, [alpha / 2, 1 - alpha / 2]))

def newey_west_t(x: np.ndarray, lags=10):
    n = len(x); m = x.mean(); e = x - m
    g0 = (e @ e) / n; s = g0
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1); s += 2 * w * (e[l:] @ e[:-l]) / n
    return m / np.sqrt(s / n)

def deflated_sharpe(sr_obs, sr_trials: np.ndarray, n_obs, skew=0.0, kurt=3.0):
    """Bailey & Lopez de Prado DSR (per-period SR units). Returns probability SR_obs beats expected-max under null."""
    from scipy.stats import norm
    N = len(sr_trials); v = np.nanvar(sr_trials)
    if N < 2 or not v > 0: return np.nan
    em = np.sqrt(v) * ((1 - np.euler_gamma) * norm.ppf(1 - 1 / N) + np.euler_gamma * norm.ppf(1 - 1 / (N * np.e)))
    den = np.sqrt(1 - skew * sr_obs + (kurt - 1) / 4 * sr_obs ** 2)
    return norm.cdf((sr_obs - em) * np.sqrt(n_obs - 1) / den)

def trade_stats(b: pd.DataFrame):
    if b is None or len(b) == 0: return dict(trades=0)
    w = b.pnl > 0
    return dict(trades=len(b), pnl=b.pnl.sum(), hit=w.mean(), mean=b.pnl.mean(), median=b.pnl.median(),
                avg_win=b.pnl[w].mean() if w.any() else 0, avg_loss=b.pnl[~w].mean() if (~w).any() else 0,
                fees=b.fees.sum(), spread_cost=b.spread_cost.sum(), hold=b.hold_days.mean(),
                worst=b.pnl.min(), pnl_per_risk=(b.pnl.sum() / b.max_loss.sum()) if b.max_loss.sum() else np.nan)
