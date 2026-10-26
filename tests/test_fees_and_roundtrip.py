import math
import pytest
from options_lab.engine import run
from synth import scripted, cfg, ENTRY, EXIT, SIGNAL

OV = {**SIGNAL, **ENTRY, **EXIT}
LEGS = {"pcs": 2, "dv": 2, "ic": 4}
GROSS_PS = {"pcs": 1.15 - 0.55, "dv": -1.35 - (0.10 - 0.50), "ic": 2.20 - 1.10}

@pytest.mark.parametrize("strat", ["pcs", "dv", "ic"])
@pytest.mark.parametrize("fee,mult", [(0.65, 1.0), (0.65, 2.0), (1.0, 0.0)])
def test_roundtrip_fees(strat, fee, mult):
    mk, _ = scripted(ndays=40, overrides=OV)
    _, bl, _, _ = run(mk, cfg(strategy=strat, fee=fee, fee_mult=mult))
    r = bl.iloc[0]; legs = LEGS[strat]
    assert r.reason == "time"
    expect_fees = fee * mult * legs * r.n * 2
    assert r.fees == pytest.approx(expect_fees)
    assert r.pnl == pytest.approx(GROSS_PS[strat] * 100 * r.n - expect_fees)

def test_sizing_accounts_for_roundtrip_fees():
    mk, _ = scripted(ndays=40, overrides=OV)
    fee, mult = 0.65, 2.0
    _, bl, _, _ = run(mk, cfg(strategy="ic", fee=fee, fee_mult=mult))
    ml = (5 - 2.20) * 100 + fee * mult * 4 * 2
    assert bl.iloc[0].n == math.floor(1000 / ml)
    assert bl.iloc[0].max_loss == pytest.approx(ml * bl.iloc[0].n)

def test_intrinsic_expiry_charges_entry_fee_only():
    mk, _ = scripted(ndays=32, overrides={**SIGNAL, **ENTRY}, spot_over={31: 92.0})
    _, bl, _, _ = run(mk, cfg(strategy="pcs", fee=0.65, exit_dte=0))
    r = bl.iloc[0]
    assert r.fees == pytest.approx(0.65 * 2 * r.n)    # no exit commission on cash settlement
