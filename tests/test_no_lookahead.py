import numpy as np, pandas as pd
import pytest
from options_lab.engine import run, Market
from synth import world, cfg, COLS

K = 50

def perturb(mk_seed_q, mk, k, seed=99):
    rng = np.random.default_rng(seed)
    dates = mk.dates; cut = dates[k]
    q = mk_seed_q.copy(); m = (q.date > cut).values
    fac = rng.uniform(0.3, 2.0, m.sum())
    q.loc[m, "bid"] = (q.loc[m, "bid"].values * fac).round(2); q.loc[m, "ask"] = (q.loc[m, "ask"].values * fac + 0.01).round(2)
    q.loc[m, "delta"] = rng.uniform(-1, 1, m.sum()); q.loc[m, "oi"] = rng.integers(0, 3, m.sum())
    f = mk.feats["SPY"].copy(); fm = np.array([d > cut for d in f.index])
    f.loc[fm, "spot"] = f.spot[fm].values * rng.uniform(0.7, 1.3, fm.sum())
    f.loc[fm, "ivp"] = rng.uniform(0, 100, fm.sum()); f.loc[fm, "ret60"] = rng.normal(0, .1, fm.sum())
    return Market({"SPY": q[COLS]}, {"SPY": f}, mk.rf, dates)

def entries(bl, pos, upto):
    rows = [(r.id, r.entry_date, r.n, round(r.open_px, 10), r.expiry, r.signal_date) for r in bl.itertuples()]
    rows += [(p.id, p.entry_date, p.n, round(p.open_px, 10), p.exp, p.signal_date) for p in pos]
    return sorted(r for r in rows if r[1] <= upto)

@pytest.mark.parametrize("strat,filt", [("pcs", "f1"), ("ic", "none"), ("dv", "f2")])
def test_future_changes_do_not_affect_past(strat, filt):
    mk, q = world(seed=5, ndays=80)
    c = cfg(strategy=strat, filt=filt, ivp_min=30, fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0)
    cut = mk.dates[K]
    dA, bA, rA, pA = run(mk, c)
    dB, bB, rB, pB = run(perturb(q, mk, K), c)
    pd.testing.assert_frame_equal(dA.loc[:cut], dB.loc[:cut])
    ca = bA[bA.exit_date <= cut].reset_index(drop=True); cb = bB[bB.exit_date <= cut].reset_index(drop=True)
    assert len(ca) > 0 or strat == "dv"
    pd.testing.assert_frame_equal(ca, cb)
    assert entries(bA, pA, cut) == entries(bB, pB, cut)
    assert not dA.loc[cut:].equals(dB.loc[cut:])   # sanity: perturbation did matter later

@pytest.mark.parametrize("strat", ["pcs", "ic"])
def test_end_idx_truncation_equals_full_prefix(strat):
    mk, _ = world(seed=7, ndays=80)
    c = cfg(strategy=strat, fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0)
    cut = mk.dates[K]
    dF, bF, rF, pF = run(mk, c)
    dT, bT, rT, pT = run(mk, cfg(strategy=strat, fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0, end_idx=K))
    pd.testing.assert_frame_equal(dF.loc[:cut], dT)
    pd.testing.assert_frame_equal(bF[bF.exit_date <= cut].reset_index(drop=True), bT.reset_index(drop=True))
    assert entries(bF, pF, cut) == entries(bT, pT, cut)

def test_signal_uses_prior_session_only():
    mk, _ = world(seed=11, ndays=60)
    c = cfg(strategy="pcs", start_idx=5, entry_every=3, tp=0.5, stop_mult=2.0)
    _, bl, _, pos = run(mk, c)
    for r in bl.itertuples():
        assert r.signal_date < r.entry_date
    for p in pos:
        assert p.signal_date < p.entry_date
