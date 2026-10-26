# Wave-2 pre-registration (frozen before any wave-2 result is computed)

Written 2026-10-25. **Dev period:** 2022-01-03 → 2024-06-28 (all walk-forward/specification work). **Holdout:** 2024-07-01 → 2024-12-31. Holdout tapes are not downloaded until this file and the code are committed. Then each primary spec runs **once** on the holdout, with no changes.

Every strategy is specified in the same order: **economic intuition → signal → portfolio construction → execution (fill tier) → risk → evaluation**. "Primary" is the single confirmatory test. "Secondary" items are exploratory and are corrected for multiplicity inside their family (Romano–Wolf) and reported as such.

## Data facts measured before writing this (not results)
- Option tape clock is US/Eastern: SPY trades begin at ms_of_day 34,200,000 = 09:30.
- The tape behaves like a capped sample. SPY/QQQ/TSLA have ~500k trades per day while covering every expiry and the full session, and SPY is missing 11 of 62 days in 2022Q1. **Consequences:** flow signals use ratios only, never levels; fill rates are measured, not assumed; days without tape coverage are no-trade days, not zero-return days.
- Equity NBBO covers 09:29–09:35 and 15:55–16:01 for 17 names (no GOOGL). The equity tape is quote events, so it is dense.
- EOD chain forwards are null; the SPX close is `sp500_cash_level` in market_overlays.

## Common conventions
- **Fill tiers.** T0 = cash settlement at the SPX close (SPXW PM only). T1 = primary-exchange auction print, participation ≤ 1% of the trailing-20-session median print size. T2 = marketable order against the **first observed NBBO strictly after τ+L**; reject if no observation within A = 10 s of arrival, if bid ≤ 0, or if bid > ask; order size ≤ displayed size. T3 = EOD bid/ask.
- **Latency:** L = 2 s is primary; 0.5 s and 10 s are sensitivities.
- **Fees** (per contract per side): SPX/SPXW $0.65 commission + $0.60 exchange; ETF and single-name options $0.65 + $0.10; stock $0.0035/share. All fees ×2 as a stress.
- **Multi-leg orders:** every leg must fill under T2 or the trade is skipped (no partial or legging fills). Skips are counted.
- **Account:** $1,000,000 reference account; idle cash earns the 1-month T-bill (`risk_free_rate_1m`). Returns are excess of the T-bill.
- **Inference:** Newey–West (5 lags) t-statistics on daily returns; stationary block bootstrap (mean block 10, 5,000 draws) CIs; events clustered by date; panels use Fama–MacBeth with NW. Deflated Sharpe uses the full count of wave-2 trials.
- **Kill rule** (applies to every strategy): the primary is rejected if the dev-period net mean is ≤ 0 at L = 2 s, **or** the holdout net mean is ≤ 0, **or** the result disappears with the top-5 P&L days removed.

---

## F1 — Option execution-cost atlas (measurement, no alpha)
- **Intuition:** Quoted spreads overstate the costs that liquidity takers actually pay (Muravyev & Pearson 2020). The prior wave assumed full spread crossing.
- **Measurement:** for each trade with a valid NBBO, compute the effective half-spread ratio |p − m| / ((a − b)/2), the relative quoted spread (a − b)/m, and displayed size. Bucket by root × DTE {0, 1–7, 8–30, 31–90, >90} × |K/S − 1| {<1%, 1–3%, 3–7%, >7%} × half-hour. S is the prior close.
- **Snapshot timing check:** compare EOD-chain bid/offer to the tape's last NBBO before 16:00 and before 16:15 for SPY, SPXW and AAPL, to learn when the EOD snapshot is taken.
- **Output:** cost tables and fill-availability rates (fraction of target contracts with an observation within A after τ+L).

## F2 — Engine validation: put-write replication
- **Intuition:** If the engine can't reproduce a published, mechanically defined index, its strategy P&L is not credible.
- **Rule:** on each third-Friday expiry, sell 1 SPXW PM third-Friday put expiring next month. The strike is the listed strike nearest to and ≤ the SPX close. The fill is the EOD bid (T3; mid as sensitivity). Collateral is the full strike notional in T-bills. Hold to expiry; settle on the SPX close (T0).
- **Evaluation:** monthly-return correlation and tracking error versus the Cboe PUT index, if obtainable; otherwise report the series alone. Differences are expected because PUT uses AM SOQ settlement and a VWAP sell window, and those differences are documented rather than fit.

## H1 — 0DTE SPXW premium held to settlement
- **Intuition:** Short-dated index options carry a variance risk premium, since demand for same-day convexity from retail traders and hedgers exceeds the risk dealers are compensated for (Bandi, Fusari & Renò 2023; Beckmeyer, Branger & Gayda 2023; Vilkov 2023). Holding to cash settlement collects the premium without paying a second spread.
- **Signal:** primary is unconditional (every day with a 0DTE SPXW expiry and valid quotes). The secondary is a VRP filter: trade only when the implied move (ATM straddle mid / F) at τ exceeds the trailing-20-session median realized move |SPX_close − F_τ| / F_τ measured at the same τ on prior days.
- **Forward F_τ:** K* + C_mid − P_mid at the strike minimizing |C_mid − P_mid|, using each contract's last quote in [τ − 120 s, τ). This uses information known at τ only.
- **Portfolio:** short iron fly. Sell the call and put at K* and buy the wings at K* ± w, where w is the listed strike nearest 1.5 × straddle mid (minimum 5 points). Contracts are sized so that max loss (w − credit) × 100 × n ≤ 0.5% of equity. One trade per day.
- **Primary τ:** 12:00. Secondaries: 10:00, 14:00, 15:00, and a short iron condor (shorts at K* ± 1 × straddle, wings at K* ± 2 × straddle).
- **Execution:** T2 entry (sell at bid, buy at ask) and T0 exit at `sp500_cash_level`.
- **Risk:** defined by construction. Report the worst day, ES97.5, and the share of P&L from the best 5 days.
- **Evaluation:** mean net return on max loss per trade (event-level test, NW), plus the account Sharpe.

## H2 — Overnight option premium (SPY, QQQ)
- **Intuition:** Delta-hedged option returns are strongly negative overnight and near zero intraday (Muravyev & Ni 2020). Option prices seem to spread expected variance over calendar time while most variance arrives during the session. Weekends/non-trading periods show the same pattern (Jones & Shemesh 2018). Short sellers of overnight variance are paid.
- **Signal:** primary is unconditional, every session pair (t close → t+1 open). The secondary restricts to weekends (Friday → Monday).
- **Portfolio:** short 1 ATM straddle (strike nearest F, the first expiry with DTE ≥ 7), delta-hedged with shares at entry using Black–Scholes delta from IV inverted at the mid. Size n so that the straddle's gamma loss on a 3% gap is ≤ 0.5% of equity: n = floor(0.005E / (0.5 Γ (0.03S)² · 100)), summed over SPY and QQQ independently.
- **Execution:** option entry at τ = 15:58:00 and exit at τ = 09:33:00 next session (both T2); stock hedge at the same τ against the equity NBBO (T2, buy at ask / sell at bid).
- **Risk:** gap risk is bounded by the sizing rule, not by construction. Report the worst nights.
- **Evaluation:** mean delta-hedged net P&L / straddle premium per night (Muravyev–Ni units), NW t, and the account Sharpe. **Mechanical comparison:** the same trade held 09:33 → 15:58 intraday, which the theory predicts is ≈ 0 or positive for longs.

## H3 — Overnight equity drift with auction fills
- **Intuition:** A large share of the equity premium accrues overnight, through a "tug of war" between overnight and intraday clienteles (Lou, Polk & Skouras 2019; Cliff, Cooper & Gulen 2008). Auctions let you enter and exit at a single price without crossing a spread.
- **Signal:** primary is an always-on long overnight position. The secondary is overnight momentum: rank names on their trailing-21-session mean overnight return and hold only the top third.
- **Portfolio:** equal weight across eligible names (16 singles + SPY + QQQ, excluding META and GOOGL, which lack auction coverage), 100% gross, rebuilt daily.
- **Execution:** buy at the closing auction print and sell at the next opening auction print (T1); fees each side. Sensitivity: cross the spread at 15:59 and 09:31 in the window NBBO instead of using auctions. Splits are handled with `share_adj_factor`; ex-dividend nights are credited the dividend from `total_return − price_return_ex_div`.
- **Evaluation:** daily net excess return, NW t, and Sharpe. **Contrast:** the intraday (open → close) leg.

## H4 — Option-implied information → next-day stock returns
- **Intuition:** Informed traders use options for leverage and concealment, so option order flow and implied-volatility asymmetries lead stock prices (Easley, O'Hara & Srinivas 1998; Pan & Poteshman 2006; Cremers & Weinbaum 2010; Xing, Zhang & Zhao 2010).
- **Signals** (from day-t data only; traded at the t+1 open):
  - *Primary:* **delta-weighted order imbalance** OI_flow = Σ δ·size·side / Σ |δ|·size over regular-hours trades, where side = +1 if price > mid and −1 if price < mid. δ is the same-day EOD delta. This is a ratio, so it is robust to the sampling cap.
  - *Secondary:* IV spread (OI-weighted mean of IV_call − IV_put over matched strike/expiry pairs, 10–60 DTE); smirk (OTM-put IV at K/S nearest 0.95 within [0.80, 0.95] minus ATM-call IV nearest K/S = 1, 10–60 DTE, negative sign expected); and an equal-weight z-composite.
- **Portfolio:** 15 single names (16 minus META), cross-sectional demeaned ranks scaled to 100% gross, dollar neutral, held from the t+1 open to the t+2 open.
- **Execution:** T1 opening-auction prints, fees, and short borrow at 0.30%/yr. GOOGL has no auction data, so it is ranked but traded at the 09:31 window NBBO (crossing the spread).
- **Evaluation:** Fama–MacBeth slope of the next open-to-open return on the cross-sectionally z-scored signal (NW t) and the long-short Sharpe.

## H5 — Pre-earnings implied-volatility run-up
- **Intuition:** Uncertainty about an upcoming announcement is priced gradually, so implied volatility rises into the event. Straddles bought days before and **sold before** the announcement earn the run-up without bearing the event jump (Gao, Xing & Zhang 2018).
- **Signal:** a calendar of earnings dates from earnings_actuals. The assumption that announcement dates are known ≥ 7 sessions ahead is labelled. The exit session X is the announce date if the announcement is after the close (≥ 16:00), otherwise the session before it. Entry is at session X − 5.
- **Portfolio:** long 1 ATM straddle (strike nearest F from put–call parity), using the first expiry after the announce date. Premium budget is 0.5% of equity per event; events may overlap.
- **Execution:** T2 at τ = 15:55 on both entry and exit (buy at ask, sell at bid).
- **Evaluation:** mean net return on premium per event, date-clustered t. Secondary: the same trade held through the event (exit 15:55 on the session after the announcement), which replicates the rejected EOD design under intraday fills.

## H6 — End-of-day momentum (SPY, QQQ)
- **Intuition:** Negative-gamma dealer hedging and late-informed trading push the day's move further into the close (Gao, Han, Li & Zhou 2018; Baltussen, Da, Lammers & Martens 2021).
- **Signal:** r = mid(15:55) / close_{t−1} − 1, where close_{t−1} is the official closing auction print. Primary: position = sign(r) on every day. Secondary: only on days when the prior-day EOD gamma exposure is negative, GEX = Σ_calls Γ·OI·100·S²·0.01 − Σ_puts (same), using the **assumption** that dealers are long calls and short puts.
- **Portfolio:** 50% of equity in SPY and 50% in QQQ, each signed independently.
- **Execution:** entry at 15:55 + L against the equity NBBO (T2); exit at the closing auction print (T1).
- **Evaluation:** daily net return, NW t, hit rate, and a placebo with randomized signs (1,000 draws).

## Explicitly not run
Dispersion (non-synchronous legs, partial basket), intraday gamma scalping (no full-day equity quotes), passive-fill strategies, and further EOD VRP grids (already exhausted in waves 0/1).

---

## Amendment A1 (2026-10-26, before any H2/H5 performance analysis; motivated only by measured fill availability)
**Measured:** at A = 10 s, the tape shows ~30–45 SPY/QQQ contracts and 3–30 single-name contracts with a post-arrival quote per window. SPY options are present on only 432 of 625 dev days. Under the original rule (a fixed ATM strike at the first expiry with DTE ≥ 7), H2 filled ~1% of nights (5 of ~900; their P&L is immaterial and was not used). The cause is the trade-sampled tape: in live markets every NBBO is visible, but here quotes are observed only at sampled prints.

The original H2/H5 primaries are kept and reported as written; their expected outcome is "untestable: insufficient fills". The amended rules are reported alongside them as **A1 variants**:
1. **Strike/expiry choice from contracts with observed post-arrival quotes.** H2: any expiry with DTE in [7, 21]; take the (expiry, strike) pair with both legs quoted that minimizes |K/F − 1|, subject to |K/F − 1| ≤ 1%. H5: the first expiry after the announcement, |K/F − 1| ≤ 2.5%. F is the parity forward from the pre-arrival snapshot of that expiry.
2. **Exit chase.** The exit uses the first quote in [τ+L, τ+L+10 s]. If none, it uses the first quote in [τ+L, τ+L+120 s] (status `exit_chase`). If still none, the trade is dropped and counted (`exit_unfilled`).
3. H1 (fill rate ~80%) is unchanged.

## Amendment A2 (2026-10-26, data availability)
The equity NBBO window opens at 15:55:00, so no quote exists before τ = 15:55. The H6 signal therefore uses the mid of the first quote in [15:55:00.5, 15:55:10.5], which is observable at 15:55:00.5. The fill uses the first quote after 15:55 + L. At L = 0.5 s the signal quote and the fill quote coincide.

## Amendment A3 (2026-10-26, data availability)
- **H5:** for single names, the 120 s pre-arrival window often lacks a call/put pair at the same strike, which left no parity forward for 61 of ~150 events. When parity is unavailable, the ATM reference is the stock mid at 15:55:00.5 from the equity NBBO; K* is the listed strike nearest to it. GOOGL has no equity NBBO, so it keeps the parity-only rule.
- **F2 tape sensitivity:** the 15:55 sale uses the first bid within 120 s. The primary EOD variant is unchanged.
- **Equity quote filter** (all strategies): quotes whose mid is more than 20% away from the prior close are dropped, because `sym_root` mixes share classes (JPM preferreds trade near $20).

## Amendment A4 (2026-10-26, data availability; exploratory only)
Even with A1, ~90% of H5 entries go unfilled: single-name straddles rarely have both legs printed within 10 s. A4 uses A1's strike rule but takes both entry and exit quotes from the first print within 120 s of 15:55:02. This is a slow-execution proxy. It is **labelled exploratory**, and the pre-registered H5 primary is reported as untestable if its fill count is < 30.
