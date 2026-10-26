# Phase A — Strategy feasibility matrix

Generated: 2026-10-15. This is a data-capability assessment, not a performance result or a recommendation.

## Evidence used

The verified EOD chain contains 57,600,631 rows from 2022-01-03 through 2024-12-31. It contains bid, offer, volume, open interest, IV, delta, gamma, vega, theta, expiration, put/call, AM-settlement flag, contract size, and adjustment factor fields. Across the full chain, 53,668,324 rows (93.17%) have `best_bid > 0` and `best_offer > best_bid`; 21,669 rows are locked or crossed; 3,910,638 rows have non-positive or null bids; 1,186,390 valid two-sided rows have a quoted spread exceeding 100% of midpoint. No quote-size fields or intraday observation timestamps are present.

`root` is null in the inspected chain, so universe membership must be joined by `option_security_id` and separated for SPX/SPXW with the `am_settlement` and symbol fields. The three chain files together cover the 20 mapped option underlyings. The local equity panel covers 18 tickers, with SPX/SPXW absent from that panel.

## Classification

`SUPPORTED` means the required data is present for the stated EOD, next-eligible-session simulation once contract and timing gates are implemented. `PROXY ONLY` means a simplified EOD study is possible but cannot substantiate intraday execution, queue position, or unverified lifecycle assumptions. `NOT TESTABLE` means essential data is absent.

| Candidate strategy | Classification | Available support | Gaps / minimum viable restriction |
|---|---|---|---|
| Put credit vertical | PROXY ONLY | Same-date put quotes, strikes, expiries, IV/Greeks, volume/OI, contract size | EOD snapshots without timestamp or quote size; require next-session conservative fill, positive two-sided quotes, and forced close before expiry until settlement/exercise is verified |
| Call credit vertical | PROXY ONLY | Same as put vertical | Same restrictions; no naked calls |
| Iron condor | PROXY ONLY | Same-date call and put chains permit candidate four-leg construction | No intraday synchronization or leg size; reject asynchronous/unquoted legs and apply four-leg conservative costs |
| Long directional debit vertical | PROXY ONLY | Same-date chains, underlying daily history for 18 tickers, IV/Greeks | Use lagged daily signals and next-session EOD execution only; separate index products without an equivalent local underlying panel |
| Long/short volatility regime rotation | PROXY ONLY | IV and daily underlying returns; factor and overlay panels | Forward-price support not yet verified; snapshot timing and point-in-time OI semantics remain unknown |
| Calendar spread / diagonal | PROXY ONLY | Multiple maturities and strikes appear in EOD chain | Assignment, exercise style, dividend, and carry inputs not verified; close prior to front-leg expiry |
| Butterfly / broken-wing fly | PROXY ONLY | Dense chain rows, bid/ask, strikes, expiries | Four-leg execution and same-snapshot synchronization are not observable; use conservative fills only |
| Earnings volatility | PROXY ONLY | Earnings actuals include announcement date and time; option and equity data exist | Need point-in-time verification of event timestamps and a pre-event execution-time rule; do not use any data published after entry |
| Collar / protective put | PROXY ONLY | Equity daily panel and option quotes for 18 equity/ETF tickers | Dividends, stock borrow, assignment, and contract deliverables are not yet modeled |
| Covered call | PROXY ONLY | Equity daily panel and call quotes for 18 equity/ETF tickers | Same lifecycle/dividend restrictions; no claim about assignment outcomes |
| Cash-secured put | PROXY ONLY | Put quotes, strikes, contract size, daily stock closes | Require verified multiplier/deliverable and cash reservation; force close before expiry initially |
| Delta-hedged straddle / gamma scalping | NOT TESTABLE | EOD option and underlying data could support a separate EOD-marked proxy | No intraday hedge-time spot, timestamp, or quote size; cannot test gamma scalping or intraday hedge execution |
| Skew relative value / risk reversal | PROXY ONLY | Cross-strike IV and Greeks are present | Needs bounded-risk construction; no intraday rehedging claim and no naked short-option exposure |
| Cross-underlying volatility ranking | PROXY ONLY | 20 mapped option underlyings, IV, daily factor and market panels | Must standardize the SPX/SPXW mapping and prove chain-quality/liquidity filters before portfolio results |
| Dispersion / correlation | NOT TESTABLE | SPX/SPXW and component options are present; DSPX context exists | Requires synchronized index/component quotes, reliable hedge-time inputs, and scalable multi-leg execution; absent from EOD-only evidence |

## First permitted benchmark scope

The earliest defensible implementation is a **daily EOD proxy simulator** for defined-risk verticals and condors. Signals must use information available no later than the prior session; candidate orders are selected from that session's snapshot and filled at a conservative price from the next eligible snapshot. The baseline excludes short positions held through expiry, contracts with nonstandard adjustments, zero/non-positive bids, locked/crossed markets, and missing legs.

Before the first historical simulation, implement the quote-quality gates, stable contract normalization, option/underlying mapping, data-availability policy, and tests for multi-leg payoff, fills, cash accounting, and look-ahead prevention. Forward-price support files, contract delivery/exercise details, and source snapshot timing must be verified before any Black-76 valuation, assignment, or intraday claim.
