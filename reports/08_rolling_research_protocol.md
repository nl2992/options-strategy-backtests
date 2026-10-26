# Rolling options research protocol

This protocol extends the earlier fixed-split benchmark without replacing its historical results. It implements a rolling parameter search over the plan's first-wave defined-risk EOD strategies.

## Hypotheses and candidate structures

| Family | Strategy expressions | Signal grid |
|---|---|---|
| Implied-versus-realized volatility premium | Put/call credit spreads and iron condors | ATM IV less trailing 20/60-session realized volatility; IV percentile controls |
| Trend expressed with bounded-risk convexity | Call and put debit verticals | 20/60-session adjusted-price trend, alone or combined with the 20-session volatility premium |
| Volatility skew | Credit spreads, condors, and directional debit verticals | 25-delta put IV less call IV on the expiration nearest 30 DTE |

The grid covers five structures (`pcs`, `ccs`, `ic`, call debit `dv`, and put debit `pdv`), two deltas per structure, two target DTEs (30 and 45), and eleven fixed signal configurations: no filter; IV percentile thresholds 50/70; 20-session VRP thresholds 0/2 vol points; 60-session VRP at 0; 20-session trend; 60-session trend at 2%; combined VRP/trend; and skew thresholds of 2/4 vol points. This is a coarse, pre-registered search. Exit rules, spread widths, and costs remain fixed to avoid multiplying the search unnecessarily.

## Rolling selection and evaluation

- Provide a 126-session feature warm-up, then use fixed 252-session training windows and the following 63-session evaluation window. Advance 63 sessions per fold; retain a shorter final fold if it contains at least 20 sessions.
- Select the highest training Sharpe per structure, requiring at least 15 closed trades. If a structure has no eligible candidate, record that fold as underpowered instead of forcing a selection.
- Start each fold flat and close positions at the last eligible EOD snapshot. Signals use the prior session close; entries fill on the next eligible EOD snapshot.
- The historical sample has already been inspected in earlier work, including the 2024 period. Rolling evaluation is therefore research-stage historical OOS, not a virgin holdout.

## Portfolio and cost conventions

- Simulate integer contracts and existing cash, reserve, and risk limits at the $200,000 reference account. Report percentage returns as a normalized $1 equity curve for comparison.
- Keep only defined-risk structures, exclude META until the issuer/history issue is repaired, and exclude nonstandard option contracts under the current normalization.
- Use conservative bid/ask fills, the current $0.65 per-contract-side placeholder fee, and selected-configuration stresses at fee x2 and 1.5x spread cost.
- Report annualized excess return, volatility, Sharpe, drawdown, tail loss, trades, fold consistency, and block-bootstrap intervals. Use deflated Sharpe as a training-selection diagnostic, not as evidence from the selected OOS series.

## Deliverables

Run `python run_rolling_research.py` to create `reports/rolling_research/`: the registered grid, exact fold dates, training-only candidate scores, frozen per-fold selections, selected/control/stress OOS results, daily normalized returns, an aggregate scorecard, and a decision memo. Existing fixed-split reports remain as historical reference. Calendar spreads, earnings, protective overlays, dispersion, and intraday/0DTE are not included in this first grid; their data-quality and execution limitations remain documented in the dataset assessment.
