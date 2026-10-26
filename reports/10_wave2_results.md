# Wave-2 results: intraday-fillable options and equity strategies (2022–2024)

Prepared 2026-10-26. Specs: `wave2/prereg/PREREGISTRATION.md`, frozen at commit `d35c50e` before the 2024H2 tapes were downloaded. Engines are in C++ (`wave2/cpp/`); figures and tables are in `wave2/notebooks/wave2_report.ipynb` → `wave2/figures/`. Every number below is computed from the supplied data by that code.

## Bottom line

**No strategy clears the confirmatory bar.** One lead survives the pre-registered kill rule: H4, delta-weighted option order flow → next-day stock returns. Its dev result is not statistically distinguishable from the best of 63 trials: dev Sharpe 0.90, NW t = 1.48, deflated Sharpe 0.17, Romano–Wolf p = 0.36. The untouched 2024H2 holdout was positive: Sharpe 3.3, bootstrap CI on annual excess return [7%, 42%], Fama–MacBeth t = 2.32. That is enough to justify a fresh out-of-sample test (2025 data) and **not** enough to trade. Everything else was rejected or proved **not executable on this tape**. The second outcome is itself the most important finding about the data.

| | Strategy (primary spec) | Fills / active days | Dev ann. excess (95% CI) | Dev Sharpe / NW t | Holdout ann. excess | Holdout Sharpe | Decision |
|---|---|---|---|---|---|---|---|
| F2 | Put-write engine validation | 34 months | — | — | — | — | **Engine valid**: corr 0.97 with the Cboe PUT index, tracking error 2.3%/yr |
| H1 | 0DTE SPXW iron fly at 12:00, held to settlement | 581 | −3.1% (−7.0, +0.9) | −0.79 / −1.42 | +3.0% | 0.75 | **REJECT** (dev ≤ 0; driven by a few days) |
| H2 | Overnight short delta-hedged ATM straddle (orig.) | 10 | — | — | — | — | **UNTESTABLE** (sparse quotes) |
| H2-A1 | Same, with quoted-strike selection | 283 | −0.8% (−1.5, −0.1) | −1.39 / −2.22 | +0.9% | 2.44 | **REJECT** (significantly negative in dev, net of costs) |
| H3 | Overnight equity, close → open crosses | 616 days | +4.8% (−12.8, +22.2) | 0.29 / 0.50 | +28.8% | 2.44 | **REJECT** (gone without its top 5 days) |
| H4 | Option order flow → next-day return | 623 days | +7.8% (−2.4, +17.9) | 0.90 / 1.48 | +23.7% | 3.26 | **Survives kill rule; not significant**, a lead |
| H5 | Pre-earnings straddle (orig.) | 1 | — | — | — | — | **UNTESTABLE** |
| H5-A4 | Same, with 120 s execution windows | 75 | −0.1% | −0.18 / −0.30 | −0.5% | −2.06 | **REJECT** |
| H6 | End-of-day momentum, SPY/QQQ | 618 days | +0.8% (−0.1, +1.7) | 0.91 / 1.50 | −0.9% | −1.37 | **REJECT** (holdout ≤ 0) |

*Account-level returns are on a $1M reference account with the pre-registered risk caps (0.5% of equity at risk per trade). Option strategies therefore have small account-level magnitudes. Trade-level statistics are in `wave2/results/scorecard_events.csv`.*

## What the data can and cannot execute (fig01, fig02)

- **The option tape is a capped sample, not a full tape.** SPY/QQQ/TSLA hit ~500k prints per day. SPY options are missing on 193 of 625 dev days. In a 10-second window after a decision, only ~30–45 SPY contracts and 3–30 contracts per single name show a print with an attached NBBO. Quotes are observed **only at sampled prints**.
- **Multi-leg fills are only feasible for 0DTE SPXW.** The four-leg 0DTE SPXW iron fly filled on ~80% of days within 10 s. Two-leg straddles at a *pre-chosen* strike filled on ~1% of nights for SPY/QQQ and <1% of earnings events. Amendments A1–A4 (strike chosen among quoted contracts, 120 s windows) recovered testable samples. They are reported as amendments with dated rationale, made before looking at the corresponding results.
- **Costs (F1):** SPXW prints well inside the quoted spread. The effective/quoted half-spread ratio is 0.57 for ATM 0DTE and 0.34 for 8–30 DTE. SPY and QQQ print near the touch (0.75–0.93), and single names fall in between. The previous waves' "buy ask / sell bid" assumption is therefore conservative for SPX, roughly right for the ETFs, and moderately conservative for single names. Other traders' effective spreads are not our fills: our T2 fills still cross the full spread.
- **Equity data:** closing-cross prints match the official daily close on 100% of tested days. XOM and LLY lack primary-exchange crosses on most days, and GOOGL has no equity quotes or auctions. `sym_root` mixes share classes: JPM preferreds near $20 contaminated both the auction and the quote streams until filtered.
- **EOD snapshot timing is unresolved:** EOD-chain quotes match the tape's last NBBO before 16:00 or 16:15 only 7–21% of the time.

## Strategy-by-strategy reading

Each item runs intuition → what the data showed.

**H1 — 0DTE premium held to settlement.** The variance-premium story predicts positive short-fly returns. Holding to cash settlement did remove exit costs, and the settlement close matched the intraday parity forwards to within ~2 bp on average (mean gap at 15:00: −0.07 bp). The dev mean return on risk was −4.0% per trade (clustered t = −1.22), with large left-tail days. Later entry times (14:00, 15:00) are closer to zero, and the condor is ≈ 0. None of the 15 variants is significant after Romano–Wolf. The 2024H2 sign flip (+3%) sits inside a CI of [−9%, +16%].

**H2 — Overnight option premium.** Muravyev & Ni (2020) find that delta-hedged options lose value overnight, which should favor short sellers. Measured net of observed spreads at 15:58/09:33, the short overnight straddle *lost* 1.25% of premium per night in dev (clustered t = −4.0). The intraday leg was ≈ 0 to slightly positive. The decomposition (fig06; dev; % of premium per trade) shows why. The mid-to-mid short-option P&L is only **+0.18% overnight** but **+1.58% intraday**: in this sample option mids fall mostly *during* the session, measured from the 09:33 open quote. That runs against the Muravyev–Ni pattern, though the 09:33 open quote may carry an opening-IV premium. Crossing the spread costs ~0.77% and the hedge −0.33% (short gamma plus the stock spread), so overnight nets −1.25%. Spread cost alone exceeds the overnight premium about 4×.

**H3 — Overnight equity drift.** Overnight crosses earned +4.8%/yr in dev with a CI spanning zero, against +15.3%/yr intraday. That reverses the Lou–Polk–Skouras pattern for these 16 large caps in 2022–24. The 2024H2 overnight +28.8% coincides with a broad rally and the post-earnings gap season. The result does not survive removal of the top 5 days.

**H4 — Option-implied information.** Delta-weighted signed option flow predicts the next open-to-open return cross-sectionally:
- Fama–MacBeth slope: 3.6 bp per 1σ in dev (t = 1.63) and 12 bp in holdout (t = 2.32).
- The IV spread (Cremers–Weinbaum) is weak (t = 0.67).
- The smirk (Xing–Zhang–Zhao) is marginal in dev (t = 1.93) and absent in holdout.
- The long-short book trades only opening auctions, so costs are fees and borrow, and the fee×2 stress barely moves it.

Caveats: 15 names (~10 tradeable on a typical day: XOM, LLY and GOOGL rarely have usable opening crosses), a capped sample of prints, and a quote-rule trade sign with no open/close or customer-type information.

**H5 — Pre-earnings IV run-up.** With 120 s execution windows (A4), buying 5 sessions before and selling before the event lost 0.8% of premium per event in dev (64 events, t = −0.81) and −6.3% in holdout (11 events). Holding through the event was clearly negative. This is consistent with the earlier EOD earnings study.

**H6 — End-of-day momentum.** Positive in dev (Sharpe 0.91, t = 1.50) but negative in holdout. Displayed-size caps limited fills to ~47% of the target notional. The negative-GEX filter did not help. Against 1,000 random-sign placebos, dev P&L sits at the 99.3rd percentile and holdout at the 24th (fig10). The dev timing signal did not carry forward.

## Rigor checklist
- Pre-registration, frozen code SHA, and holdout physically absent during development (`wave2/fetch_holdout.sh` was written after the freeze).
- Amendments A1–A4 are dated and motivated only by measured fill or data availability. The original primaries are still reported.
- 63 wave-2 trials, deflated Sharpe and Romano–Wolf computed across all of them, block-bootstrap CIs, NW t-stats, and events clustered by date.
- Engine validated against a published index (F2).
- **Not addressed:** no 2025 data (no true out-of-sample beyond 2024H2); option exchange/clearing fees are placeholders; the tape's sampling scheme is undocumented, so fill-availability rates may differ from live markets; passive or price-improved fills are never assumed.

## What to do next
1. **H4 confirmation on fresh data.** Obtain 2025 option trades with NBBO and an opening-auction tape. Run the frozen `h4_info.cpp` once, unchanged, and pre-register the decision rule (FM t > 2, positive net Sharpe).
2. **Get a full option quote tape** (quote events, not trade-attached). H2 and H5 are untestable here because of quote sampling, not because of economics.
3. If a broader universe is available, rerun H4 on ≥ 100 names. Its power comes from cross-sectional breadth, and 15 names is the binding constraint.

## Reproduce
```
wave2/fetch_dev.sh && wave2/run_extracts.sh      # download + reduce dev (2022-01..2024-06)
wave2/fetch_holdout.sh                            # after the freeze commit only
wave2/cpp/build_and_run.sh                        # C++ engines -> wave2/results/*.csv
.venv/bin/python wave2/scorecard.py               # pre-registered decisions
.venv/bin/python -m jupyter nbconvert --to notebook --execute --inplace wave2/notebooks/wave2_report.ipynb
```
