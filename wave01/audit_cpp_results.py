"""Reconcile the dependency-free C++ scorecard to the saved Python result tape."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/rolling_research"
cpp = pd.read_csv(OUT / "cpp_oos_scorecard.csv").set_index("strategy")
py = pd.read_csv(OUT / "oos_scorecard.csv").set_index("strategy")
metrics = ["total_return", "excess_ann", "vol_ann", "sharpe", "maxdd", "es95"]
mapping = {"total_return": "oos_total_return", "excess_ann": "oos_excess_ann",
           "vol_ann": "oos_vol_ann", "sharpe": "oos_sharpe", "maxdd": "oos_maxdd", "es95": "oos_es95"}
rows = []
for strategy in cpp.index:
    for metric in metrics:
        a, b = float(cpp.loc[strategy, metric]), float(py.loc[strategy, mapping[metric]])
        rows.append({"strategy": strategy, "metric": metric, "cpp": a, "python": b,
                     "difference": a-b, "matches_1e-9": bool(np.isclose(a, b, atol=1e-9, rtol=1e-9))})
audit = pd.DataFrame(rows)
audit.to_csv(OUT / "cpp_python_reconciliation.csv", index=False)
print(audit.to_string(index=False))
if not audit["matches_1e-9"].all():
    raise SystemExit("C++ and Python scorecards differ; inspect reconciliation CSV")
