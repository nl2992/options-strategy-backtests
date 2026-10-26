# Wave-3 pre-registration

Written 2026-10-26, before any wave-3 engine has run. Wave-2 conventions (`wave2/prereg/PREREGISTRATION.md`) apply unless overridden here.

## Sample split and freeze
- **Confirmatory strategies** (S1, S2, S5, S6, S8, S9, S10): development 2022-01-03 → 2023-12-29, test 2024-01-02 → 2024-12-31.
- Engines read `W3_END` and refuse to simulate past it. Development runs use `W3_END=20231231`. The test run happens only after the freeze commit, with `W3_END=20241231`, once.
- **Caveat:** 2024 is not a virgin holdout. Wave-2 results for 2024 were seen, but none of these signals were computed on it. S8 is closest to wave-2 H3 (overnight returns), so its test is marked "partially informed".
- **Exploratory strategies** (S3, S4, S7) were derived from wave-2 results (H4, H1). They run on the full 2022–2024 sample and **cannot be confirmed here**. Confirmation requires 2025 data.

## Realistic transaction costs (replaces the wave-2 placeholders)

| Item | Assumption (per unit) |
|---|---|
| Option commission | $0.65 per contract per side |
| SPX/SPXW exchange + OCC + ORF | $0.66 + $0.025 + $0.003 |
| ETF/single-name option taker + OCC + ORF | $0.50 + $0.025 + $0.003 |
| Option exercise/assignment | $0 broker fee (OCC fee negligible) |
| Stock commission + clearing | $0.0035 + $0.0002 per share |
| Exchange fee | auction $0.0010/share; continuous taker $0.0030/share |
| SEC fee (sells) | $27.80 per $1M notional |
| FINRA TAF (sells) | $0.000166 per share, capped at $8.30 per trade |
| Short borrow | 0.40%/yr on short notional |

Fill tiers are as in wave 2: T0 settlement, T1 auction, T2 observed NBBO, T3 EOD bid/ask (buy ask / sell bid). **Equity closes:** the official close (`close_raw`) equals the closing-cross print on 100% of tested days, so closes fill at `close_raw` for all names. **Equity opens** use the primary-exchange opening cross only; if it is missing, the order is not filled at the open.

**Daily accounting:** stock positions are marked to the official close each day. Option positions are marked to the EOD mid and realized at settlement or exercise. The account is $1M; returns are excess of the T-bill.

**Inference:** Newey–West t, stationary block bootstrap, events clustered by date, Romano–Wolf within each strategy, and deflated Sharpe over all wave-2 + wave-3 trials. **Kill rule:** the primary fails if the dev mean is ≤ 0, the test mean is ≤ 0, or the dev result disappears without its top-5 days.

**Beta hedge** (S1, S2, S4): short SPY at the same auction, with the ratio set to the 60-session OLS beta of daily close-to-close returns ending the day before entry, capped to [0.5, 2].

---

## S1 — Pre-earnings announcement premium (confirmatory)
- **Intuition:** Expected returns rise into scheduled announcements, as compensation for announcement risk and an attention-driven buying pressure (Frazzini & Lamont 2007; Barber, De George, Lehavy & Trueman 2013).
- **Signal:** the earnings calendar. X is the last session before the announcement (as in wave-2 H5). Calendar dates are assumed known ≥ 7 sessions ahead.
- **Rule:** buy at the close of X − 5 and sell at the close of X, before the announcement. Beta-hedge with SPY.
- **Portfolio:** 10% of equity per event; overlapping events allowed.
- **Execution:** T1 closing prices.
- **Test:** mean hedged event return (clustered by date) and the account Sharpe. Secondaries: unhedged; 10-session window.

## S2 — Earnings-announcement-return drift (confirmatory)
- **Intuition:** Prices under-react to earnings news. The market's own reaction (the announcement return) is a surprise measure that needs no analyst consensus, which we don't have (Brandt, Kishore, Santa-Clara & Venkatachalam 2008; Chan, Jegadeesh & Lakonishok 1996).
- **Signal:** EAR = stock return minus β × SPY return over the reaction window. For after-close announcers (AMC) the window is close(A) → close(A+1); for before-open announcers (BMO) it is close(A−1) → close(A).
- **Rule:** take sign(EAR) the next session at the opening cross and hold 20 sessions, exiting at the close. Beta-hedge with SPY.
- **Portfolio:** 10% of equity per event.
- **Secondaries:** only events with |EAR| > 2%; a 40-session hold.

## S3 — Option-flow refinements (exploratory; derived from H4)
H4's cross-sectional rank book, rebuilt with realistic fees. Signals (day t, traded at the t+1 open):
- `all` (= H4)
- `open`: flow on contracts whose OI rises. **Assumption:** the next EOD record's OI is as of t's close and is published before the t+1 open.
- `short_otm`: DTE ≤ 30 and |δ| < 0.4.

Holding periods: 1 day and 5 days (5 overlapping sub-books). No primary; exploratory only.

## S4 — Pre-announcement option flow → announcement return (exploratory; derived from H4)
- **Intuition:** Informed trading concentrates in options before scheduled news (Roll, Schwartz & Subrahmanyam 2010; Johnson & So 2012).
- **Signal:** Σ num / Σ den of delta-weighted flow over sessions X−5 … X−1.
- **Rule:** buy or sell at the close of X in the direction of sign(signal). Exit at the first opening cross after the announcement; if that is missing, exit at that day's close. Beta-hedge with SPY.
- **Portfolio:** 10% of equity per event.

## S5 — SPXW premium held to settlement, timed by the VIX term structure (confirmatory)
- **Intuition:** The variance risk premium is larger and safer to harvest when the implied-volatility term structure is in contango. Inversion signals stress, when short-volatility positions lose (Carr & Wu 2009; Bollerslev, Tauchen & Zhou 2009; Johnson 2017). Holding to cash settlement crosses the spread once, and at 8–30 DTE that costs ~0.6% of premium (wave-2 F1).
- **Signal:** primary: trade when VIX3M / VIX > 1 on the entry date (EOD). Secondaries: unconditional; VIX − RV21(SPX) > 0.
- **Rule:** every Friday, sell an SPXW iron fly at the EOD bid/ask. The short strike is nearest to spot, the wings sit at the strikes nearest ± 1.5 × the straddle mid, and the expiry is the Friday expiry with DTE in [26, 30] (otherwise the nearest in [21, 35]). Hold to PM settlement on `sp500_cash_level`.
- **Portfolio:** max loss ≤ 1% of equity per position; up to ~4 overlapping positions.
- **Execution:** T3 entry, T0 exit.
- **Test:** account Sharpe, NW t, and **alpha** from a regression of daily returns on SPY daily returns. Report beta.

## S6 — Realized-minus-implied volatility straddles, exited by exercise (confirmatory)
- **Intuition:** When trailing realized volatility exceeds implied volatility, options are cheap, and straddles on those names outperform straddles on names where implied exceeds realized (Goyal & Saretto 2009). Holding to expiry and exercising swaps the option exit spread for a stock auction trade.
- **Signal:** on each monthly expiry Friday, for each name, gap = RV21 (from closes) − ATM IV of the next monthly expiry (mean IV of the call and put nearest spot).
- **Rule:** buy ATM straddles on the top 3 names by gap and sell straddles on the bottom 3. Enter at EOD (buy ask / sell bid) and hold to expiry. At expiry, ITM legs are exercised or assigned at the official close; delivered shares are closed at the next opening cross (or the close if that is missing), paying stock fees.
- **Portfolio:** premium-neutral, 2% of equity of premium per side, split equally across names.
- **Secondary:** long top-3 only.
- **Risk:** early assignment of short legs is not modelled (known limitation).

## S7 — 0DTE pin at the maximum-OI strike (exploratory; derived from H1)
- **Intuition:** Delta-hedging of large open interest pins prices to heavily traded strikes at expiry (Ni, Pearson & Poteshman 2005).
- **Rule:** identical to H1's iron fly at 15:00 and 14:00, but centered on the strike with the largest call+put OI from the last record before expiry, among strikes within ±1 straddle of F. Fills are T2; settlement is T0. Realistic fees.

## S8 — Overnight returns and daytime reversals (confirmatory, partially informed)
- **Intuition:** Overnight noise-trader demand pushes prices up overnight, and intraday arbitrageurs push back. Akbas, Boehmer, Jiang & Koch (2022) relate the monthly frequency of negative daytime reversals (overnight > 0 and intraday < 0) to future returns. The sign is pre-registered as **positive (high NR → higher next-month return)**, following that paper; the citation is to be verified against the source.
- **Signal:** NR = the fraction of the last 21 sessions with overnight return > 0 and intraday return < 0, computed from auction prints.
- **Rule:** at the month-end close, go long the top third and short the bottom third by NR; dollar neutral; hold one month.
- **Execution:** T1 closes.
- **Universe:** names with ≥ 15 valid sessions.

## S9 — FOMC pre-announcement drift (confirmatory, underpowered)
- **Intuition:** US equities earn most of their excess return in the 24 hours before scheduled FOMC announcements (Lucca & Moench 2015).
- **Rule:** buy SPY at the close of the session before the announcement and sell at the close of announcement day. The data has no 14:00 price, so the post-announcement reaction is included (a known dilution).
- **Portfolio:** 100% of equity. 24 events.

## S10 — Turn-of-the-month (confirmatory, underpowered)
- **Intuition:** Returns concentrate around month turns, consistent with payment-flow timing (Ariel 1987; Lakonishok & Smidt 1988).
- **Rule:** buy SPY at the close of the second-to-last session of the month and sell at the close of the third session of the next month.
- **Portfolio:** 100% of equity.

## Amendment B1 (2026-10-26, after seeing S5 dev aggregate P&L; disclosed)
A single 28-DTE SPXW iron fly often risks more than 1% of the $1M reference account, so 64% of S5 entries were skipped as `size_lt1`. These skips are concentrated in high-volatility weeks, which biases the account-level result. S5's per-trade test therefore uses **every** entry at one contract (`status` filled or size_lt1; return on max loss). The account-level series is reported as written. This amendment changes the denominator of the per-trade test, not the trading rule.
