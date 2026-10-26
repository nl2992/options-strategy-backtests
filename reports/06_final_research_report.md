# Final research report — EOD defined-risk options study (SPY, QQQ, SPX/SPXW), 2022-01 → 2024-12

Prepared 2026-10-15. Everything below is computed by the code in this folder from the supplied files; nothing is quoted from outside.

## Bottom line
**No strategy passed the promotion gate. All four reference structures are REJECT on the untouched test window.** Under conservative fills (buy ask / sell bid), per-leg fees, daily conservative marks and the pre-registered risk limits, none produced a positive, statistically distinguishable net excess return out of sample. This is a negative result on a short, single-regime sample (3 years, 753 sessions); it is *not* evidence that these structures can never work.

| Strategy | Frozen config (dev-selected) | Dev ex-ret (ann) | Val | **Test** | Test 95% block-boot CI | Test trades | Control (unfiltered) test | fee×2 | slip×1.5 | delay+1 | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Call credit spread | d=0.15 dte=30 filt=f2 | 0.48% | -1.37% | **-0.36%** | [-1.20%, 0.08%] | 1 | -2.61% | -0.36% | -0.37% | -1.16% | **REJECT** |
| Call debit vertical | d=0.5 dte=30 filt=f1 | -1.25% | 0.56% | **-4.50%** | [-12.52%, 1.69%] | 34 | -9.13% | -4.95% | -5.56% | -7.90% | **REJECT** |
| Iron condor | d=0.2 dte=30 filt=f1 | 0.91% | -2.52% | **-3.56%** | [-11.03%, 1.03%] | 33 | -6.49% | -3.89% | -4.49% | -2.63% | **REJECT** |
| Put credit spread | d=0.2 dte=30 filt=f1 | 0.33% | -0.30% | **-2.53%** | [-9.24%, 1.72%] | 19 | -2.09% | -2.60% | -2.98% | -0.73% | **REJECT** |

*Excess return = account return over the 1-month T-bill, on full account equity ($200,000 reference). Cash earns T-bill on idle balance.* Benchmarks on the same test window (2024-06 → 2024-12, 151 sessions): SPY buy-and-hold total return 11.77%, excess ann 14.22%, max DD -8.41%.

## What was run
- **Data**: 3 annual EOD option-chain Parquet files (57.6M rows, OptionMetrics-style columns: bid/offer, IV, delta, OI, volume, `contract_size`, `cfadj`, `am_settlement`) + context panels. Universe tested: SPY, QQQ, SPX+SPXW (the only index/ETF underlyings with matching spot data). Single names were not tested.
- **Normalization** (`src/options_lab/normalize.py`): contract_size==100, cfadj==1, DTE 1–75, 0.75≤K/S≤1.25, ask>0, no crossed quotes → 12.9M rows.
- **Engine** (`src/options_lab/engine.py`): signal from session t-1 snapshot; fill at session t EOD, same snapshot all legs; buy ask / sell bid; $0.65/contract/side placeholder fee; marks at bid/ask liquidation value (stale fallbacks counted); targets/stops observed at close t executed at close t+1; forced exit ≤5 calendar days before expiry (no assignment model needed); SPY/QQQ short leg ITM at prior close → exit (early-assignment control); all-cash defined risk, 0.5% trade / 5% aggregate / 2% per-underlying risk caps, 25% cash reserve; cash earns T-bill.
- **Trials**: 72 pre-registered configs (4 structures × delta{3} × DTE{30,45} × filter{none, IV-pct≥60, IV-pct≥60+trend}), all logged in `reports/experiment_registry.csv`. Splits: first 60% dev, next 20% validation, last 20% test (chronological).
- **Selection**: per structure, max dev Sharpe with ≥30 dev trades (dev rows only); test evaluated once on that frozen choice.

## Key findings (observed)
1. Of 72 trials, only 23 had positive dev excess return, and just **1** had positive dev *and* validation excess with ≥30 trades. Filters (IV percentile / trend) reduced losses relative to the unfiltered control on dev, but the IV-rank filter fired rarely (few trades) and did not carry into validation.
2. **Short premium unfiltered lost money after conservative costs in dev** (2022 sell-off and rate shock) for put spreads, call spreads and condors; call credit spreads and condors lost heavily in 2023-24 up-trend. Call debit verticals lost in dev and were mixed in validation.
3. **Transaction costs are material.** Entry+exit spread crossing alone was larger than fees in every selected test book (e.g. debit vertical: $3,065 spread cost vs $268 fees on $-5,748 net P&L). Optimistic half-crossing (slip 0.5) still did not turn any test book positive.
4. **Placebo**: shuffled-signal filters (20 seeds, within-month) averaged -2.15% test excess, similar to the selected filters, i.e. the filters showed no distinguishable timing value out of sample.
5. **Capital**: at $50k the 0.5% trade risk ($250) cannot fund $5-wide SPY/QQQ or any SPX spread; with $2-wide SPY/QQQ spreads the system trades 1–2 contracts and 6–16 entries are rejected for size<1. A $10-wide SPX spread (~$900 max loss) exceeds the 0.5% cap at $100k and below, so SPX uses $5-wide spreads there (not separately attributed in these tables). Larger accounts only scale the same (negative) expectancy.
6. DSR on dev Sharpe across 72 trials is ~0 for all four selections: nothing is distinguishable from the best of many noisy trials.

## What cannot be established from this dataset
- Behaviour outside 2022–2024; only one up-trend + one bear + one low-vol recovery path. No 2008/2020 stress.
- Intraday fills, true multi-leg/NBBO-inside-spread execution, quote sizes (none in the EOD file), intraday stops.
- Early assignment/dividend risk: only controlled by exit rules, not modelled. Option EOD quote timestamp vs equity close is vendor-defined and not verified.
- Forward price files were not staged; Black-76 valuation was not used (vendor IV/delta used for selection only, ~10% of rows have missing delta/IV).
- Intraday NBBO/trade/auction folders were not inspected; gamma scalping, dispersion, 0DTE strategies remain untested.
- The flagged earnings/event strategies, calendars, butterflies, covered/collar structures were not run.
- Test window is only 151 sessions; CIs are wide and positive edges smaller than ~±5% annual would be undetectable.

## Reproduce
```
uv venv .venv && uv pip install duckdb pyarrow pandas numpy scipy pytest matplotlib
.venv/bin/python src/options_lab/normalize.py
.venv/bin/python run_grid.py && .venv/bin/python analyze_grid.py && .venv/bin/python final_eval.py
.venv/bin/python -m pytest tests -q   # 64 tests
```
Not a git repo: code_sha not recorded; seeds fixed (placebo seeds 0–19).
