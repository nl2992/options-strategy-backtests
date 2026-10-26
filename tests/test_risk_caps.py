import pytest
from options_lab.engine import run
from synth import world, cfg, scripted, ENTRY, SIGNAL

def concurrent_max(bl, pos, end):
    ev = [(r.entry_date, r.exit_date, r.max_loss) for r in bl.itertuples()] + [(p.entry_date, end, p.max_loss_pc * p.n) for p in pos]
    days = sorted({e[0] for e in ev})
    return max((sum(m for a, b, m in ev if a <= d < b) for d in days), default=0.0)

def test_single_trade_risk_cap_exact():
    mk, _ = scripted(ndays=40, overrides={**SIGNAL, **ENTRY})
    for rt in (0.001, 0.005, 0.02):
        _, bl, _, _ = run(mk, cfg(strategy="pcs", fee=0.65, risk_trade=rt))
        if bl.empty: continue
        assert bl.iloc[0].max_loss <= rt * 200_000 + 1e-9
        # one more contract would breach
        ml1 = bl.iloc[0].max_loss / bl.iloc[0].n
        assert (bl.iloc[0].n + 1) * ml1 > rt * 200_000

def test_tiny_risk_budget_rejects():
    mk, _ = scripted(ndays=40, overrides={**SIGNAL, **ENTRY})
    _, bl, rej, pos = run(mk, cfg(strategy="pcs", risk_trade=0.0005))
    assert bl.empty and not pos and rej == {"risk_cap_or_size_lt_1": 1}

def test_per_trade_and_aggregate_caps_random_world():
    mk, _ = world(seed=8, ndays=90)
    c = cfg(strategy="pcs", fee=0.65, start_idx=5, entry_every=1, tp=0.5, stop_mult=2.0, risk_trade=0.005, risk_agg=0.012, risk_und=0.02)
    daily, bl, rej, pos = run(mk, c)
    eq_hi = max(c.equity0, daily.equity.max()) * 1.01
    assert len(bl) + len(pos) >= 3
    assert (bl.max_loss <= c.risk_trade * eq_hi).all()
    assert all(p.max_loss_pc * p.n <= c.risk_trade * eq_hi for p in pos)
    assert concurrent_max(bl, pos, mk.dates[-1]) <= c.risk_agg * eq_hi
    assert rej.get("risk_cap_or_size_lt_1", 0) > 0     # the aggregate cap actually bound

def test_underlying_cap_binds_before_aggregate():
    mk, _ = world(seed=8, ndays=90)
    c = cfg(strategy="pcs", fee=0.65, start_idx=5, entry_every=1, risk_trade=0.005, risk_und=0.006, risk_agg=0.05, tp=0.5, stop_mult=2.0)
    daily, bl, rej, pos = run(mk, c)
    eq_hi = max(c.equity0, daily.equity.max()) * 1.01
    assert concurrent_max(bl, pos, mk.dates[-1]) <= c.risk_und * eq_hi

def test_risk_at_entry_column_matches_open_positions():
    mk, _ = world(seed=8, ndays=60)
    c = cfg(strategy="pcs", fee=0.65, start_idx=5, entry_every=2, tp=0.5, stop_mult=2.0)
    daily, bl, rej, pos = run(mk, c)
    eq_hi = max(c.equity0, daily.equity.max()) * 1.01
    assert (daily.risk_at_entry <= c.risk_agg * eq_hi).all()
