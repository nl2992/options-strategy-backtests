"""Point-in-time features. Every series is indexed by session date and describes the
state AT THAT SESSION'S CLOSE. The engine only ever reads feature[i-1] when acting on i."""
import numpy as np, pandas as pd

def atm_iv_series(q: pd.DataFrame, target_dte=30, lo=14, hi=60) -> pd.Series:
    d = q[(q.dte >= lo) & (q.dte <= hi) & q.iv.notna() & (q.iv > 0)].copy()
    d["moneyness"] = (d.strike / d.spot - 1).abs()
    d["dd"] = (d.dte - target_dte).abs()
    best = d.groupby("date").dd.transform("min")
    d = d[d.dd == best]
    d = d.sort_values(["date", "moneyness"])
    d = d.groupby(["date", "cp"]).head(1)
    return d.groupby("date").iv.mean().rename("atm_iv")

def trailing_pct_rank(s: pd.Series, window=126, min_hist=63) -> pd.Series:
    """Percentile of s[t] within s[t-window+1..t] (inclusive of t, known at t's close)."""
    v = s.to_numpy(); out = np.full(len(v), np.nan)
    for i in range(len(v)):
        lo = max(0, i - window + 1)
        h = v[lo:i + 1]; h = h[~np.isnan(h)]
        if len(h) >= min_hist and not np.isnan(v[i]):
            out[i] = (h <= v[i]).mean() * 100
    return pd.Series(out, index=s.index, name="ivp")

def build_features(q: pd.DataFrame, spot: pd.Series, signal_spot: pd.Series | None = None) -> pd.DataFrame:
    iv = atm_iv_series(q).reindex(spot.index).ffill(limit=3)
    f = pd.DataFrame({"spot": spot, "atm_iv": iv})
    f["ivp"] = trailing_pct_rank(f.atm_iv)
    # Keep option moneyness and payoff spot on the raw price scale, but use an
    # adjusted price series for signals so stock splits/dividends do not create
    # artificial trend or realized-volatility events.
    signal_price = f.spot if signal_spot is None else signal_spot.reindex(f.index).ffill()
    f["signal_spot"] = signal_price
    r = np.log(signal_price).diff()
    f["ret20"] = signal_price / signal_price.shift(20) - 1
    f["ret60"] = signal_price / signal_price.shift(60) - 1
    f["rv20"] = r.rolling(20).std() * np.sqrt(252)
    f["rv60"] = r.rolling(60).std() * np.sqrt(252)
    f["vrp20"] = f.atm_iv - f.rv20
    f["vrp60"] = f.atm_iv - f.rv60

    # 25-delta put minus call IV on the expiration nearest 30 DTE. This is a
    # close-time surface feature; the engine consumes it only on the prior day.
    surf = q[(q.dte.between(21, 45)) & q.iv.notna() & (q.iv > 0) & q.delta.notna()].copy()
    if len(surf):
        surf["expiry_distance"] = (surf.dte - 30).abs()
        best_expiry = surf.groupby(["date", "root"]).expiry_distance.transform("min")
        surf = surf[surf.expiry_distance == best_expiry]
        surf["delta_distance"] = np.where(
            surf.cp.eq("P"), (surf.delta.abs() - 0.25).abs(), (surf.delta - 0.25).abs()
        )
        best_delta = surf.groupby(["date", "root", "cp"]).delta_distance.transform("min")
        surf = surf[surf.delta_distance == best_delta]
        surf = surf.sort_values(["date", "root", "cp", "delta_distance", "strike"])
        surf = surf.drop_duplicates(["date", "root", "cp"])
        wide = surf.pivot(index=["date", "root"], columns="cp", values="iv")
        if "P" in wide and "C" in wide:
            skew = (wide["P"] - wide["C"]).groupby(level="date").mean()
            f["skew25"] = skew.reindex(f.index)
        else:
            f["skew25"] = np.nan
    else:
        f["skew25"] = np.nan

    near = atm_iv_series(q, target_dte=21, lo=8, hi=35).reindex(f.index)
    deferred = atm_iv_series(q, target_dte=50, lo=35, hi=75).reindex(f.index)
    f["term_slope"] = near - deferred
    return f
