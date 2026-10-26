# options-strategy-backtests

Code, reduced data, outputs and analysis notebooks for a set of pre-registered backtests of option and equity strategies on US market data from 2022-01-03 to 2024-12-31. The accompanying report covers economic rationale, specifications and results for every strategy; it is kept separately.

Short version of the results:
- **No confirmed strategy.** None of the 25 specifications clears a confirmatory bar after realistic execution and fees.
- **One lead.** Delta-weighted option order flow predicting next-day stock returns.
  - 2024H2 holdout: Sharpe 3.26.
  - 2024 test with realistic fees: Sharpe 1.71.
  - Development t-statistics stay below 2.
- **Combined portfolio.** Combining the 13 primary sleeves, with idle capital in SOFR, earned 3.7–4.7% over SOFR in 2024 under shrinkage-Markowitz weights estimated on 2022–2023. Every sleeve's 2024 outcome was known when the combination was designed, so this is a basis for paper trading, not evidence.

## Layout

| Path | Contents |
|---|---|
| `src/options_lab/`, `run_grid.py`, `analyze_grid.py`, `final_eval.py`, `run_earnings.py`, `run_rolling_research.py`, `tests/` | Waves 0–1: Python EOD engine for defined-risk option spreads, fixed-split and rolling walk-forward studies, earnings study (64 tests) |
| `cpp/`, `export_cpp_inputs.py`, `audit_cpp_results.py` | C++ re-implementation and reconciliation of the wave-1 rolling study |
| `wave2/` | Wave 2 (H1–H6, F1–F2): download and reduction (`fetch*.sh`, `extract.py`, `context.py`), C++ engines (`cpp/`), inference (`analysis.py`, `scorecard.py`), pre-registration (`prereg/`), results, notebook, figures |
| `wave3/` | Wave 3 (S1–S10): inputs (`context3.py`), C++ engines with realistic fees (`cpp/`), `scorecard3.py`, pre-registration, results, notebook, figures |
| `alloc/` | Allocation across strategy sleeves with idle capital in SOFR: `allocate.py`, weights, sleeve statistics, daily portfolio returns, notebook, figures |
| `research_style.py` | Shared matplotlib style for all figures |
| `data/` | Reduced inputs needed to rerun everything except the raw tape reduction (see below) |
| `reports/` | Wave 0–1 reports and outputs, dataset audit, file manifest with download links and byte counts |

## Data

Included:
- `data/raw/context/`: daily equity, factors, rates and VIX, fundamentals, earnings dates (21 MB).
- `data/normalized/`: per-underlying EOD option panels (326 MB). `quotes_SPX.parquet` is stored with Git LFS.
- `wave2/extracts/`: every reduced input the C++ engines read (534 MB): decision-time quote snapshots, auction crosses, flow aggregates, cost atlas, and the wave-3 chains.
- `wave2/external/`: Cboe PUT index history and SOFR fixings (New York Fed).

Not included, because of size (re-download with byte-count verification against `reports/dataset_audit/file_manifest.csv`):
- Option and equity tapes, about 27 GB: `wave2/fetch_dev.sh` (2022-01 to 2024-06) and `wave2/fetch_holdout.sh` (2024H2).
- EOD option chains, 2.4 GB: `./fetch_eod_chain.sh`.

## Running

```bash
uv venv .venv && uv pip install -r requirements.txt     # or: python -m venv .venv && pip install -r requirements.txt
```

The engines read only `wave2/extracts/`, so steps 2–6 run from the included data alone. Steps 1 and 7 need the downloads above.

1. Optional: rebuild the extracts from raw tapes.
   ```bash
   wave2/fetch_dev.sh && wave2/fetch_holdout.sh && wave2/run_extracts.sh
   ```
2. Wave-2 engines, then the decision rules.
   ```bash
   wave2/cpp/build_and_run.sh
   .venv/bin/python wave2/scorecard.py
   ```
3. Wave-3 inputs (needs `data/normalized`).
   ```bash
   .venv/bin/python -I wave3/context3.py
   ```
4. Wave-3 engines over the full sample, then the decision rules.
   ```bash
   W3_END=20241231 wave3/cpp/build_and_run.sh
   .venv/bin/python wave3/scorecard3.py
   ```
5. Allocation across sleeves.
   ```bash
   .venv/bin/python alloc/allocate.py
   ```
6. Notebooks: figures and tables.
   ```bash
   .venv/bin/python -m jupyter nbconvert --to notebook --execute --inplace \
     wave2/notebooks/wave2_report.ipynb wave3/notebooks/wave3_report.ipynb alloc/notebooks/allocation_report.ipynb
   ```
7. Waves 0–1 (need the EOD chains).
   ```bash
   ./fetch_eod_chain.sh && .venv/bin/python src/options_lab/normalize.py && .venv/bin/python src/options_lab/normalize.py --single
   .venv/bin/python run_grid.py && .venv/bin/python final_eval.py
   .venv/bin/python run_rolling_research.py
   ```

C++ engines build with `clang++ -std=c++17` (wave 2) or `-std=c++20` (wave 3), with no external libraries.

## Outputs

| Wave | Outputs |
|---|---|
| Wave 2 | `wave2/results/`: per-strategy `*_trades.csv` and `*_daily.csv`, `decisions.csv`, `scorecard_*.csv`, `f2_monthly.csv` |
| Wave 3 | `wave3/results/`: per-engine trades and daily returns, `decisions3.csv`, `scorecard3_*.csv` |
| Allocation | `alloc/*.csv` |
| Waves 0–1 | `reports/` (`trade_blotter.parquet`, `daily_portfolio.parquet`, `rolling_research/`, scorecards) |
| Figures | `wave2/figures/`, `wave3/figures/`, `alloc/figures/`, plus `figure_notes.md` in each folder with the data checks behind each figure |

## Protocol

- **Pre-registration:** each wave's specifications are in `wave2/prereg/PREREGISTRATION.md` and `wave3/PREREGISTRATION.md`, with dated amendments.
- **Wave 2:** the holdout tapes were downloaded only after the specifications and code were fixed.
- **Wave 3:** the engines refuse to simulate past `W3_END`; development runs used 20231231 before the test run.
- **Data caveats:** documented in `reports/dataset_audit/ASSESSMENT.md`. The main ones are the trade-sampled option tape, share-class mixing in `sym_root`, and missing primary auction crosses for XOM and LLY.

## Licence and data

The code is provided for research use. The market data comes from a third-party vendor extract and is subject to that provider's terms.
