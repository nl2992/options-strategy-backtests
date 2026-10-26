import pytest
from options_lab.engine import run, MULT
from synth import scripted, world, cfg, ENTRY, EXIT, SIGNAL

def check(daily, bl, pos, equity0):
    realized = bl.pnl.sum() if len(bl) else 0.0
    unreal = sum((p.open_px - p.last_cost) * MULT * p.n - p.entry_fees for p in pos)
    assert daily.equity.iloc[-1] == pytest.approx(equity0 + realized + unreal, abs=1e-6)
    assert (daily.cash + daily.liq_value - daily.equity).abs().max() < 1e-9

def test_scripted_closed_trade():
    mk, _ = scripted(ndays=40, overrides={**SIGNAL, **ENTRY, **EXIT})
    daily, bl, _, pos = run(mk, cfg(strategy="ic", fee=0.65))
    assert not pos and len(bl) == 1
    assert daily.equity.iloc[-1] == pytest.approx(200_000 + bl.pnl.sum())
    assert daily.cash.iloc[-1] == pytest.approx(daily.equity.iloc[-1])

def test_scripted_open_at_end():
    mk, _ = scripted(ndays=15, overrides={**SIGNAL, **ENTRY})
    daily, bl, _, pos = run(mk, cfg(strategy="pcs", fee=0.65))
    assert len(pos) == 1 and bl.empty
    check(daily, bl, pos, 200_000.0)

@pytest.mark.parametrize("strat", ["pcs", "ccs", "ic", "dv"])
def test_random_world(strat):
    mk, _ = world(seed=3, ndays=80)
    c = cfg(strategy=strat, fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0, exit_dte=5, filt="f1", ivp_min=40)
    daily, bl, rej, pos = run(mk, c)
    assert len(bl) + len(pos) >= 3, rej
    check(daily, bl, pos, c.equity0)
