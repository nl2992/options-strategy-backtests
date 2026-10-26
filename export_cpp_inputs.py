"""Export the audited normalized market to compact files for the C++ engine."""
from pathlib import Path
import struct
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from options_lab.data import load_market
from run_rolling_research import UNIVERSE, make_folds

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data/cpp_cache"
OUT.mkdir(parents=True, exist_ok=True)
market, _ = load_market(universe=UNIVERSE)
dates = market.dates
session_id = {d: i for i, d in enumerate(dates)}
und_id = {u: i for i, u in enumerate(UNIVERSE)}

with (OUT / "sessions.csv").open("w") as f:
    f.write("session,date,days_from_previous,rf_annual\n")
    for i, d in enumerate(dates):
        gap = (d - dates[i-1]).days if i else 0
        f.write(f"{i},{d},{gap},{float(market.rf.get(d, 0.0)):.17g}\n")

with (OUT / "features.csv").open("w") as f:
    f.write("session,underlying,spot,ivp,ret20,ret60,vrp20,vrp60,skew25\n")
    for u in UNIVERSE:
        feat = market.feats[u]
        for d in dates:
            row = feat.loc[d]
            vals = [row.get(k, np.nan) for k in ("spot", "ivp", "ret20", "ret60", "vrp20", "vrp60", "skew25")]
            f.write(str(session_id[d]) + "," + str(und_id[u]) + "," + ",".join("" if pd.isna(x) else f"{float(x):.17g}" for x in vals) + "\n")

# Packed little-endian record (60 bytes): uint16 session, uint8 underlying,
# 16-byte root, int32 expiry ordinal, uint8 call/put, four float64s, int32 OI.
dtype = np.dtype([("session", "<u2"), ("underlying", "u1"), ("root", "S16"),
                  ("expiry", "<i4"), ("cp", "u1"), ("strike", "<f8"),
                  ("bid", "<f8"), ("ask", "<f8"), ("delta", "<f8"), ("oi", "<i4")], align=False)
assert dtype.itemsize == 60
with (OUT / "options.bin").open("wb") as out:
    for u in UNIVERSE:
        q = pd.read_parquet(ROOT / f"data/normalized/quotes_{u}.parquet",
                            columns=["date", "exdate", "cp", "strike", "bid", "ask", "oi", "delta", "root"])
        q["date"] = pd.to_datetime(q.date).dt.date
        q["exdate"] = pd.to_datetime(q.exdate).dt.date
        q = q[q.date.isin(session_id)].copy()
        a = np.empty(len(q), dtype=dtype)
        a["session"] = q.date.map(session_id).to_numpy(dtype=np.uint16)
        a["underlying"] = und_id[u]
        a["root"] = q.root.astype(str).to_numpy(dtype="S16")
        a["expiry"] = q.exdate.map(lambda x: x.toordinal()).to_numpy(dtype=np.int32)
        a["cp"] = q.cp.map({"C": 1, "P": 0}).to_numpy(dtype=np.uint8)
        for k in ("strike", "bid", "ask", "delta"):
            a[k] = pd.to_numeric(q[k], errors="coerce").to_numpy(dtype=np.float64)
        a["oi"] = pd.to_numeric(q.oi, errors="coerce").fillna(0).to_numpy(dtype=np.int32)
        a.tofile(out)
        del q, a

pd.DataFrame([{**x, "train_start_date": str(dates[x["train_start"]]),
               "train_end_date": str(dates[x["train_end"]-1]),
               "test_start_date": str(dates[x["test_start"]]),
               "test_end_date": str(dates[x["test_end"]-1])}
              for x in make_folds(len(dates))]).to_csv(OUT / "folds.csv", index=False)
print(f"Exported {len(dates)} sessions, {len(UNIVERSE)} underlyings, {OUT / 'options.bin'}")
