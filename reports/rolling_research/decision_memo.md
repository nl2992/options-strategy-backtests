# Rolling strategy research: decision memo

This memo summarizes the first-wave parameter search. These are historical walk-forward results on 2022-2024 data; the period has been inspected previously and is not a virgin holdout.

- Candidate configurations registered before the search: 220.
- Rolling folds: 6; each uses 252 trailing training sessions and up to 63 next-session evaluation days, stepped 63 sessions.
- Universe: SPY, QQQ, SPX, AAPL, MSFT, NVDA, TSLA, GOOGL, AMZN, AVGO, NFLX, AMD, CRM, JPM, LLY, UNH, XOM, WMT. META excluded pending audited identity/history repair.
- Training selection: maximum Sharpe with at least 15 closed trades. Each fold starts flat and closes positions at its final eligible EOD snapshot.
- Main selection results are $1-NAV normalized; $200,000 integer sizing is used inside the existing risk/cash constraints.
- Fee x2 and 1.5x spread-cost stress are reported for selected configurations.

## Aggregate rolling OOS scorecard

```text
 oos_sessions  oos_folds  oos_total_return  oos_excess_ann  oos_vol_ann  oos_sharpe  oos_maxdd  oos_es95  oos_ci95_excess_lo  oos_ci95_excess_hi  oos_newey_west_t strategy  selected_folds  positive_oos_folds  control_ex_ann_mean  fee2x_ex_ann_mean  slip1_5_ex_ann_mean  oos_trades
          375          6            0.0679         -0.0098       0.0280     -0.3517    -0.0205   -0.0046             -0.0385              0.0193           -0.6648      pcs               6                   2              -0.0197            -0.0119              -0.0099         150
          375          6            0.0522         -0.0201       0.0111     -1.8369    -0.0128   -0.0020             -0.0383             -0.0030           -2.2133      ccs               6                   0              -0.0746            -0.0206              -0.0209          72
          375          6            0.0662         -0.0112       0.0137     -0.8254    -0.0107   -0.0023             -0.0333              0.0074           -1.0916       ic               6                   3              -0.0295            -0.0123              -0.0159          58
          375          6            0.0453         -0.0229       0.0576     -0.3983    -0.0604   -0.0089             -0.1002              0.0586           -0.5918       dv               6                   2              -0.0719            -0.0317              -0.0755         233
          375          6            0.0257         -0.0371       0.0173     -2.1530    -0.0284   -0.0028             -0.0747              0.0022           -1.8503      pdv               6                   1              -0.3208            -0.0378              -0.0434          53
```

## Interpretation

A positive point estimate is a research lead, not evidence of a deployable edge. Require stable results across folds, realistic cost stress, adequate closed-trade counts, and uncertainty intervals that account for serial dependence and the grid search. The grid is deliberately coarse; any refinement must be pre-registered as a new iteration and evaluated in later rolling windows, not chosen from the same OOS results.

## Files

- `candidate_registry.csv`: full parameter grid registered before computation.
- `rolling_folds.csv`: exact chronological fold boundaries.
- `fold_candidate_scores.csv`: training-only candidate metrics per fold.
- `fold_selections.json`: selected parameters frozen before that fold's OOS run.
- `fold_oos_results.csv`: selected, matched no-signal control, and cost-stress results.
- `oos_daily_returns.csv`: normalized daily returns for reproducible aggregate metrics.
