import pytest
from options_lab.engine import run
from synth import scripted, cfg, ENTRY, SIGNAL

BASE = {**SIGNAL, **ENTRY}

def go(overrides=None, drop=(), strategy="pcs", **kw):
    ov = dict(BASE); ov.update(overrides or {})
    mk, _ = scripted(ndays=40, overrides=ov, drop=drop)
    return run(mk, cfg(strategy=strategy, **kw))

def test_control_trades():
    _, bl, rej, _ = go()
    assert len(bl) == 1 and rej == {}

def test_crossed_short_leg_rejected():
    _, bl, rej, pos = go({(2, "P", 95): (1.70, 1.50)})
    assert bl.empty and not pos and rej == {"bad_quote_t": 1}

def test_crossed_long_wing_rejected():
    _, bl, rej, pos = go({(2, "P", 90): (0.40, 0.30)})
    assert bl.empty and not pos and rej == {"bad_quote_t": 1}

def test_zero_zero_locked_rejected():
    _, bl, rej, pos = go({(2, "P", 90): (0.0, 0.0)})
    assert bl.empty and not pos and rej == {"bad_quote_t": 1}

def test_zero_bid_short_leg_rejected():
    _, bl, rej, pos = go({(2, "P", 95): (0.0, 0.05)})
    assert bl.empty and not pos and rej == {"zero_bid_short_t": 1}

def test_missing_wing_at_fill_date_rejected():
    _, bl, rej, pos = go(drop={(2, "P", 90)})
    assert bl.empty and not pos and rej == {"missing_leg_t": 1}

def test_missing_short_at_fill_date_rejected():
    _, bl, rej, pos = go(drop={(2, "P", 95)})
    assert bl.empty and rej == {"missing_leg_t": 1}

def test_no_snapshot_at_fill_date_rejected():
    _, bl, rej, pos = go(drop={(2, None, None)})
    assert bl.empty and rej == {"no_snapshot_t": 1}

def test_iron_condor_one_bad_wing_rejects_whole_structure():
    _, bl, rej, pos = go({(2, "C", 110): (0.40, 0.30)}, strategy="ic")
    assert bl.empty and rej == {"bad_quote_t": 1}

def test_missing_short_at_signal_date_no_candidate():
    _, bl, rej, _ = go(drop={(1, "P", 95)})
    # next best |delta| (90P: 0.10) is 0.10 away from 0.20 > 0.07 tolerance, 100P is 0.30 away
    assert bl.empty and rej == {"no_candidate": 1}

def test_credit_too_small_rejected():
    _, bl, rej, _ = go({(2, "P", 95): (0.40, 0.50), (2, "P", 90): (0.25, 0.35)})
    assert bl.empty and rej == {"credit_too_small": 1}

def test_zero_bid_long_wing_floor_not_negative_pnl_error():
    # long wing bid = 0 at exit is fine (worthless); fill_px floors at 0, pnl finite
    mk, _ = scripted(ndays=40, overrides={**BASE, (26, "P", 90): (0.0, 0.05), (26, "P", 95): (0.0, 0.05)})
    _, bl, rej, _ = run(mk, cfg(strategy="pcs"))
    assert len(bl) == 1 and bl.pnl.isna().sum() == 0
    assert bl.iloc[0].close_cost == pytest.approx(0.05 - 0.0)

def test_locked_positive_quote_rejected():
    # bid == ask > 0 is a locked quote; treated as untradable (documented conservative treatment).
    _, bl, rej, _ = go({(2, "P", 90): (0.30, 0.30)})
    assert len(bl) == 0 and rej.get("bad_quote_t", 0) >= 1
