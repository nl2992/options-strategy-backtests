import pathlib
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]

@pytest.mark.slow
@pytest.mark.skipif(not (ROOT / "data" / "normalized").exists(), reason="data/normalized missing")
def test_real_data_smoke():
    from options_lab.data import load_market
    from options_lab.engine import run
    from synth import cfg
    mk, _ = load_market(("SPY",))
    d, bl, rej, pos = run(mk, cfg(strategy="pcs", universe=("SPY",), fee=0.65, start_idx=63, entry_every=5, end_idx=130, tp=0.5, stop_mult=2.0))
    assert len(d) > 0 and d.equity.notna().all()
