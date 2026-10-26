import pytest
import options_lab.engine as E
from options_lab.engine import run, select, Cfg
from synth import world, cfg, scripted, ENTRY, SIGNAL

def check_legs(legs, W, strategy):
    assert len(legs) in (2, 4)
    longs = [l for l in legs if l[4] > 0]; shorts = [l for l in legs if l[4] < 0]
    assert len(longs) == len(shorts) >= 1
    assert len({l[1] for l in legs}) == 1                       # single expiry
    for s in shorts:
        wings = [l for l in longs if l[2] == s[2] and l[1] == s[1]]
        assert len(wings) == 1                                  # one wing of same cp/expiry
        w = wings[0]; width = abs(w[3] - s[3])
        assert 0.5 * W <= width <= 2 * W
        if strategy != "dv":                                    # credit spread: wing further OTM
            assert (w[3] < s[3]) if s[2] == "P" else (w[3] > s[3])
        else:                                                   # call debit: long lower strike
            assert w[3] < s[3]

@pytest.mark.parametrize("strat", ["pcs", "ccs", "ic", "dv"])
def test_every_created_position_is_defined_risk(strat, monkeypatch):
    created = []
    orig = E.Pos
    def Rec(*a, **k):
        p = orig(*a, **k); created.append(p); return p
    monkeypatch.setattr(E, "Pos", Rec)
    mk, _ = world(seed=2, ndays=80)
    c = cfg(strategy=strat, fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0)
    daily, bl, rej, pos = run(mk, c)
    assert len(created) >= 3 and len(created) == len(bl) + len(pos)
    for p in created:
        check_legs(p.legs, c.width("SPY"), strat)
        assert 0 < p.max_loss_pc <= p.width * 100 + c.fee * len(p.legs) * 2 + 1e-9
        assert p.n >= 1

@pytest.mark.parametrize("strat", ["pcs", "ccs", "ic", "dv"])
def test_select_all_dates(strat):
    mk, _ = world(seed=4, ndays=40)
    c = cfg(strategy=strat)
    got = 0
    for d in mk.dates:
        legs = select(mk, "SPY", d, c)
        if legs is not None:
            got += 1; check_legs(legs, 5.0, strat)
    assert got > 0

def test_blotter_max_loss_bounded_by_width():
    mk, _ = world(seed=2, ndays=80)
    _, bl, _, _ = run(mk, cfg(strategy="ic", fee=0.65, start_idx=5, entry_every=2))
    assert len(bl) > 0
    assert (bl.max_loss <= bl.width * 100 * bl.n + 0.65 * 4 * 2 * bl.n + 1e-9).all()
    assert (bl.max_loss > 0).all()
    # realized loss never exceeds the max loss (width - credit)*100*n plus fees (stops execute at next close)
    assert (bl.pnl >= -(bl.width * 100 * bl.n + bl.fees) - 1e-6).all()

def test_missing_wing_means_no_trade():
    # wing row absent at signal date -> nearest remaining wing is outside [0.5W,2W]  => no candidate
    mk, _ = scripted(ndays=40, overrides={**SIGNAL, **ENTRY}, drop={(1, "P", 90), (1, "P", 85)})
    _, bl, rej, pos = run(mk, cfg(strategy="pcs"))
    assert bl.empty and not pos
