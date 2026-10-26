import math
import pytest
from options_lab.engine import run
from synth import scripted, cfg, ENTRY, EXIT, SIGNAL, day

OV = {**SIGNAL, **ENTRY, **EXIT}

def n_expected(px, W, legs=0, fee=0.0):
    return math.floor(0.005 * 200_000 / ((W - px) * 100 + 2 * fee * legs))

def test_put_credit_spread_time_exit():
    mk, _ = scripted(ndays=40, overrides=OV)
    daily, bl, rej, pos = run(mk, cfg(strategy="pcs", exit_dte=5))
    assert len(bl) == 1 and not pos
    r = bl.iloc[0]
    credit = 1.50 - 0.35           # sell short put @bid, buy wing @ask (fill day idx 2)
    cost = 0.60 - 0.05             # buy short @ask, sell wing @bid (idx 26 = exp-5)
    n = n_expected(credit, 5.0)
    assert n == 2 and r.n == n
    assert r.entry_date == day(2) and r.exit_date == day(26) and r.reason == "time"
    assert r.open_px == pytest.approx(credit) and r.close_cost == pytest.approx(cost)
    assert bl.pnl.sum() == pytest.approx((credit - cost) * 100 * n)

def test_put_credit_spread_intrinsic_expiry():
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 92.0})
    daily, bl, rej, pos = run(mk, cfg(strategy="pcs", exit_dte=0))
    r = bl.iloc[0]
    credit = 1.15; n = n_expected(credit, 5.0)
    assert r.reason == "expiry_intrinsic" and r.exit_date == day(31)
    assert bl.pnl.sum() == pytest.approx((credit - 3.0) * 100 * n)   # short 95P worth 3, wing 90P worth 0

def test_put_credit_spread_max_loss_both_wings_itm():
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 80.0})
    _, bl, _, _ = run(mk, cfg(strategy="pcs", exit_dte=0))
    r = bl.iloc[0]
    assert bl.pnl.sum() == pytest.approx((1.15 - 5.0) * 100 * r.n)   # = -(W - credit)*100*n

def test_call_debit_spread_time_exit():
    mk, _ = scripted(ndays=40, overrides=OV)
    _, bl, _, pos = run(mk, cfg(strategy="dv", exit_dte=5))
    r = bl.iloc[0]
    debit = 1.60 - 0.25            # buy long 105C @ask, sell short 110C @bid
    cost = 0.10 - 0.50             # buy short @ask, sell long @bid  (negative = receive)
    n = math.floor(1000 / (debit * 100))
    assert r.n == n == 7
    assert r.open_px == pytest.approx(-debit) and r.close_cost == pytest.approx(cost)
    assert bl.pnl.sum() == pytest.approx((-debit - cost) * 100 * n)

def test_call_debit_spread_intrinsic_expiry():
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 108.0})
    _, bl, _, _ = run(mk, cfg(strategy="dv", exit_dte=0))
    r = bl.iloc[0]
    debit = 1.35
    assert bl.pnl.sum() == pytest.approx((-debit + 3.0) * 100 * r.n)

def test_call_debit_spread_full_loss_and_cap():
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 90.0})
    _, bl, _, _ = run(mk, cfg(strategy="dv", exit_dte=0))
    assert bl.pnl.sum() == pytest.approx(-1.35 * 100 * bl.iloc[0].n)
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 130.0})
    _, bl, _, _ = run(mk, cfg(strategy="dv", exit_dte=0))
    assert bl.pnl.sum() == pytest.approx((5.0 - 1.35) * 100 * bl.iloc[0].n)   # max gain = (W - debit)

def test_iron_condor_time_exit():
    mk, _ = scripted(ndays=40, overrides=OV)
    _, bl, _, _ = run(mk, cfg(strategy="ic", exit_dte=5))
    r = bl.iloc[0]
    credit = (1.50 - 0.35) + (1.40 - 0.35)
    cost = (0.60 - 0.05) + (0.60 - 0.05)
    n = n_expected(credit, 5.0)
    assert n == 3 and r.n == n
    assert r.open_px == pytest.approx(credit) and r.close_cost == pytest.approx(cost)
    assert bl.pnl.sum() == pytest.approx((credit - cost) * 100 * n)

@pytest.mark.parametrize("spot,intrinsic", [(100.0, 0.0), (92.0, 3.0), (108.0, 3.0), (80.0, 5.0), (120.0, 5.0)])
def test_iron_condor_intrinsic_expiry(spot, intrinsic):
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: spot})
    _, bl, _, _ = run(mk, cfg(strategy="ic", exit_dte=0))
    r = bl.iloc[0]; credit = 2.20
    assert r.n == n_expected(credit, 5.0)
    assert bl.pnl.sum() == pytest.approx((credit - intrinsic) * 100 * r.n)
