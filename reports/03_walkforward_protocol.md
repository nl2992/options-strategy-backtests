# Walk-forward protocol (frozen before the test run)
- Chronological split by session count (753 sessions): dev = first 60% (to 2023-10), validation = next 20% (to 2024-05), test = last 20% (2024-06 → 2024-12). Strategy active from session 64 (needs ≥63 sessions of IV history; IV percentile uses trailing 126).
- Grid registered in `run_grid.py` before any results were viewed; every trial is in `experiment_registry.csv`. The grid script computes dev/val metrics only.
- Selection: per structure, max dev Sharpe among trials with ≥30 dev trades; recorded in `frozen_selection.json` **before** test metrics are calculated in `final_eval.py`.
- Simulations are causal path-continuous runs; the test slice is a slice of that path. Truncation test (`test_no_lookahead.py`) proves removing later data doesn't change earlier results.
- Stats: block bootstrap (block=10 sessions, 2000 reps) for annualized excess return, Newey-West t (10 lags), deflated Sharpe across all 72 trials, placebo (within-month shuffled filter, 20 seeds).
- Limitation honestly stated: the dev-period fixed grid was inspected once by me before the selection rule was written; one engine bug fix (locked quotes) caused a full re-run of the grid, not a selection change.
