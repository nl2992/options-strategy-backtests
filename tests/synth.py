"""Synthetic market builders for engine tests (no real data)."""
import datetime as dt
import math
import numpy as np
import pandas as pd
from options_lab.engine import Market

D0 = dt.date(2024, 1, 2)
COLS = ["date", "exdate", "cp", "strike", "bid", "ask", "volume", "oi", "iv", "delta", "am", "root", "spot", "dte"]

def day(i):
    return D0 + dt.timedelta(days=i)

def row(d, exd, cp, k, bid, ask, delta, spot=100.0, oi=100, root="SPY"):
    return dict(date=d, exdate=exd, cp=cp, strike=float(k), bid=bid, ask=ask, volume=100, oi=oi, iv=0.2,
                delta=delta, am=True, root=root, spot=spot, dte=(exd - d).days)

def make_market(quotes_df, spots, universe="SPY", rf=0.0, extra_feats=None):
    """spots: Series indexed by date (python date). Returns Market."""
    dates = list(spots.index)
    f = pd.DataFrame({"spot": spots.values}, index=dates)
    f["atm_iv"] = 0.2; f["ivp"] = 80.0; f["ret20"] = 0.0; f["ret60"] = 0.01; f["rv20"] = 0.15
    if extra_feats is not None:
        for c, v in extra_feats.items(): f[c] = v
    rfs = pd.Series(rf, index=dates, dtype=float)
    return Market({universe: quotes_df[COLS]}, {universe: f}, rfs, dates)

# ---------------- scripted (hand-made) market ----------------
STRIKES = [85, 90, 95, 100, 105, 110, 115]
DELTA = {("P", 85): -.05, ("P", 90): -.10, ("P", 95): -.20, ("P", 100): -.50, ("P", 105): -.80, ("P", 110): -.90, ("P", 115): -.95,
         ("C", 85): .95, ("C", 90): .90, ("C", 95): .80, ("C", 100): .50, ("C", 105): .20, ("C", 110): .10, ("C", 115): .05}
BASE = {("P", 85): (.05, .15), ("P", 90): (.25, .35), ("P", 95): (1.40, 1.60), ("P", 100): (3.0, 3.2), ("P", 105): (5.5, 5.8),
        ("P", 110): (10.0, 10.3), ("P", 115): (15.0, 15.3),
        ("C", 85): (15.0, 15.3), ("C", 90): (10.0, 10.3), ("C", 95): (5.5, 5.8), ("C", 100): (3.0, 3.2), ("C", 105): (1.40, 1.60),
        ("C", 110): (.25, .35), ("C", 115): (.05, .15)}

def scripted(ndays=40, exp_idx=31, overrides=None, drop=(), spot_over=None, strategy_spot=100.0, oi=100):
    """One expiry (day exp_idx). overrides[(day_idx, cp, strike)] = (bid, ask).
    drop = set of (day_idx, cp, strike) rows removed; (day_idx, None, None) removes the whole day.
    spot_over[day_idx] = spot on that day."""
    overrides = overrides or {}; spot_over = spot_over or {}
    exd = day(exp_idx); rows = []
    for i in range(ndays):
        if (i, None, None) in drop: continue
        for cp in "PC":
            for k in STRIKES:
                if (i, cp, k) in drop: continue
                b, a = overrides.get((i, cp, k), BASE[(cp, k)])
                rows.append(row(day(i), exd, cp, k, b, a, DELTA[(cp, k)], spot=spot_over.get(i, strategy_spot), oi=oi))
    q = pd.DataFrame(rows)
    spots = pd.Series([spot_over.get(i, strategy_spot) for i in range(ndays)], index=[day(i) for i in range(ndays)])
    return make_market(q, spots), q

# ---------------- random Black-Scholes world ----------------
def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs(cp, S, K, T, v):
    if T <= 0:
        return max(0.0, S - K) if cp == "C" else max(0.0, K - S), (1.0 if (cp == "C" and S > K) else (-1.0 if (cp == "P" and S < K) else 0.0))
    sd = v * math.sqrt(T); d1 = (math.log(S / K) + 0.5 * sd * sd) / sd; d2 = d1 - sd
    if cp == "C": return S * _ncdf(d1) - K * _ncdf(d2), _ncdf(d1)
    return K * _ncdf(-d2) - S * _ncdf(-d1), _ncdf(d1) - 1

def world(seed=0, ndays=90, vol=0.008, strikes=range(75, 126), seed_ivp=True):
    rng = np.random.default_rng(seed)
    spot = 100 * np.exp(np.cumsum(rng.normal(0, vol, ndays)))
    dates = [day(i) for i in range(ndays)]
    rows = []
    for i, d in enumerate(dates):
        S = float(spot[i])
        for m in range(0, ndays + 10, 7):
            exd = day(m); dte = (exd - d).days
            if dte < 0 or dte > 60: continue
            for k in strikes:
                for cp in "PC":
                    mid, dl = bs(cp, S, k, dte / 365.0, 0.2)
                    h = 0.02 + 0.02 * mid
                    bid = round(max(0.0, mid - h), 2); ask = round(mid + h, 2)
                    rows.append(row(d, exd, cp, k, bid, ask, dl, spot=S, oi=int(rng.integers(5, 500))))
    q = pd.DataFrame(rows)
    ivp = rng.uniform(0, 100, ndays) if seed_ivp else np.full(ndays, 80.0)
    mk = make_market(q, pd.Series(spot, index=dates), extra_feats={"ivp": ivp})
    return mk, q

from options_lab.engine import Cfg
def cfg(**kw):
    base = dict(universe=("SPY",), fee=0.0, slip=1.0, start_idx=2, entry_every=1000, tp=100.0, stop_mult=100.0,
                exit_dte=5, filt="none")
    base.update(kw)
    return Cfg(**base)

# standard fill-day (idx 2) and time-exit-day (idx 26) quotes for the scripted market
ENTRY = {(2, "P", 95): (1.50, 1.70), (2, "P", 90): (0.25, 0.35), (2, "C", 105): (1.40, 1.60), (2, "C", 110): (0.25, 0.35)}
EXIT = {(26, "P", 95): (0.50, 0.60), (26, "P", 90): (0.05, 0.10), (26, "C", 105): (0.50, 0.60), (26, "C", 110): (0.05, 0.10)}
# signal-day (idx 1) quotes are deliberately different so a wrong fill date changes the answer
SIGNAL = {(1, "P", 95): (1.00, 1.10), (1, "P", 90): (0.20, 0.30), (1, "C", 105): (1.00, 1.10), (1, "C", 110): (0.20, 0.30)}
