# Data_to_share: verified inventory and backtesting assessment

Audit date: October 25, 2026 (America/New_York). Source: the shared Dropbox folder supplied by the data provider. This is an audit of the supplied files, not a completed strategy backtest.

## Decision

**There is substantial usable options and equity research data, but no Level 2 order-book dataset in the supplied schemas.** The strongest execution input is the option trade tape with an attached National Best Bid and Offer (NBBO). This supports historical spreads and trade-time liquidity observations. It cannot reconstruct multiple price levels, cancellation flow, queue position, or the price/size actually available after a simulated order's latency.

A defensible first backtest can use cleaned options trades/NBBO, realistic spread crossing, fees, conservative size limits, and sensitivity scenarios. Its output must be described as an **execution model**, not a replay of executable fills. Passive-order fill probabilities and large-order market impact remain assumptions.

**Do not use the current macro labels, META ticker joins, or auction summary as-is.** Confirmed issues materially affect validity.

## What was inspected

- **21 logical datasets, 152 Parquet files, 267 dataset-specific column definitions.** Total compressed size: **88,539,715,845 bytes (88.54 GB)**. Files contain **4,744,297,699 rows** in total; this mixes trades, quotes, daily records and reference rows and is not a count of unique market events.
- Read every file's Parquet metadata, including exact row counts, physical column types, row groups and available null/min/max statistics. No within-family name/type schema drift was found.
- Fully downloaded/read all 13 top-level reference/daily tables, all 36 auction-summary files, the option ID mapping, and all three forward-price files: **53 full-file scans**.
- Scanned the first 2022Q1 row group from each option tape (1,048,576 rows apiece), the first January 2022 equity trade row group (85,350 rows), and the first January equity quote row group (551,880 rows). Samples are not random and are not representative estimates of full-tape quality or symbol coverage.
- Read current remote metadata for the three large EOD chains. Existing local chain files matched the remote byte sizes, row counts and schemas; inspected five local records. This is **not** full-file checksum verification or a complete EOD row scan.
- Full-file SHA-256 hashes are provided for the 53 downloaded Parquet files. Remote-only files have metadata-footer hashes, not whole-file hashes. A footer hash does not establish full data integrity.
- The supplier's `_data_dictionary.md` was read. Its completeness, point-in-time and survivorship claims are treated as claims, not guarantees. Several are contradicted by measured records.

The expected main observation window is 2022–2024. Reference histories can extend outside that window; in particular quarterly fundamentals reach 2026. Expiration dates can naturally extend beyond observation dates.

## Confirmed issues and their consequences

| Priority | Finding | Evidence | Required handling |
|---|---|---|---|
| Critical | META ticker collision and missing predecessor history | Equity `META` has 19 rows for security 21413, `LISTED FUNDS TRUST`, Jan 3–28, 2022, and 644 rows for security 13407, `META PLATFORMS INC`, Jun 9, 2022–Dec 31, 2024. There are 663 META-labelled rows, versus 753 calendar days. | Exclude the unrelated fund from Meta Platforms research; resolve permanent IDs and recover FB predecessor history. A ticker-only join to META options can hedge with the wrong instrument. |
| Critical | Macro names/availability do not match supplied description | `cpi_yoy` spans 282.543–317.604; `ism_pmi` spans 12,564–12,903. Each has 36 non-null values dated to the first of its month. | Quarantine these fields. Obtain source series IDs, units, genuine publication timestamps and historical vintages. CPI-like index levels are not YoY inflation, and month-start observation labels are not release dates. Do not simply forward-fill them into a PIT backtest. |
| High | No L2, order identifiers or depth event stream | All inspected execution schemas contain a single bid/ask pair or trades; none contains multiple levels, order add/modify/delete messages, or order IDs. `tr_id` identifies a trade, not an order. | Limit execution claims to L1/print-based modelling. Acquire depth or order-event data for depth/queue replay. |
| High | Option quote observations are attached to trades | The 13-column NBBO tape has trade date/time, prices and sizes but no independent quote timestamp, quote-event sequence or quote-only records. | Quotes are observed at trade times. Do not treat forward-filled attached quotes as continuously refreshed or directly observed at arbitrary decision times; age and sequencing uncertainty remain. |
| High | Greeks and NBBO tapes are not one-to-one | Greeks: 2,258,715,280 rows; NBBO: 1,808,163,203 rows, a difference of 450,552,077. No shared unique trade ID is supplied. | Reconcile dates, sessions and filtering. Normalize contract/date/time/venue/price/size and audit duplicate multiplicity and match coverage. Do not concatenate as separate economic trades or perform an unchecked many-to-many join. |
| High | Missing/invalid model inputs | Greeks metadata reports 5,057,516 null trade timestamps and implied-volatility maxima of 214748.3646. First sampled Greeks row group has 1,022 missing timestamps and 3,223 zero IVs. EOD IV/delta/gamma/vega each have 6,605,418 nulls; theta has 6,605,419. | Quarantine missing trade times for sequencing; establish sentinel rules and recompute only with a justified model and contemporaneously available inputs. Zero IV is not automatically valid. |
| High | Invalid/locked quotes occur | First sampled NBBO row group: 24 crossed quotes, 1,434 locked quotes, 10,616 nonpositive bids and 176 nonpositive asks, out of 1,048,576 rows. These categories overlap. | Apply explicit quote eligibility, crossed/locked handling and minimum-price rules. Sample counts are not full-dataset estimates. |
| High | Auction summary is incomplete | Only 17 distinct symbols; GOOGL is absent. XOM has 163 MOC and 311 MOO days; LLY 335/404. Most complete symbols have 747 MOC versus 753 MOO days. Summary size can be as low as one share. | Rebuild from eligible primary-exchange auction prints, validate sale/correction codes and coverage, and do not assume selected-print totals equal official auction capacity. |
| High | Early closing auctions are absent from normal close windows | AAPL MOC missing on 2022-11-25, 2023-07-03, 2023-11-24, 2024-07-03, 2024-11-29 and 2024-12-24. Fixed supplied close windows are around 16:00. | Use a session calendar with early closes and obtain the missing earlier close-window data. A calendar alone cannot recover omitted prints. |
| High | EOD forward field is unusable | EOD `forward_price` is physically a string and null in all 57,600,631 rows. `root` and `suffix` are also entirely null. | Use the separate numeric forward tables. Do not use EOD forwards as if known earlier that day. |
| High | Nonstandard contracts exist | In 2022, `contract_size` spans 7–172 and `cfadj` spans 1–20. Complete OCC deliverable/corporate-action history is absent. | Resolve contract specifications and adjustment history; restrict initial tests to verified standard contracts if necessary. Never hardcode a universal 100-share deliverable. |
| High | Point-in-time/survivorship safety is unproven | Daily fundamentals satisfy `as_of_date <= date` for non-null observations, but contain no announcement intraday time or revision/vintage history. Classification has one row per security, not a demonstrated GICS history. Selected ticker universe is fixed and mapping notes include 2026 expansions. | Treat the sample as a selected universe. Use next-session availability for date-only releases unless exact timing is established; inspect revisions, predecessor symbols and historical selection. Membership intervals alone do not make this fixed price universe survivorship-free. |
| Medium | Fundamentals have an all-null issuer panel | All 753 daily rows for security 21413 have missing as-of dates/accounting data. The panel has 17 security IDs; 16 have data. | Do not impute from future observations or confuse row existence with available accounting history. Resolve the unrelated META fund identity first. |
| Medium | Earnings require normalization | 157 exactly duplicated rows, 2,521 missing tickers, 10,670 missing EPS values; 33 currency categories, including `BPN`. EPS range is -5,604,800,000 to 3,270,326.4. | Deduplicate with source semantics, resolve issuer/time/currency and investigate extreme split-adjusted or erroneous values. Do not assume all earnings are USD or forecast surprises are present. |
| Medium | Additional missingness and clocks | Equity NBBO has 106,903 missing best bids, 107,011 missing best asks, and all 553,094,031 `nbbo_qu_cond` values null. Timestamps have no timezone metadata; option NBBO clock values span almost 24 hours. | Use the remaining eligibility fields with the vendor codebook. Confirm timezones, trade-date conventions and sessions; extended-hours timestamps are not automatically errors. |

## Data coverage and row meaning

The catalogue below gives exact file/row/column counts for each logical dataset. Detailed physical schemas and field meanings follow it. `column_dictionary.csv` also contains all-partition min/max/null counts; `file_manifest.csv` lists each of the 152 physical files separately. Raw metadata and first-row samples remain in this audit folder.

Expected supplier option universe: SPX, SPXW, SPY, QQQ, AAPL, MSFT, NVDA, TSLA, GOOGL, AMZN, META, AVGO, NFLX, AMD, CRM, JPM, LLY, UNH, XOM, WMT. The mapping confirms 20 labels and 19 option-system underlying IDs. **That mapping alone does not establish per-ticker/day coverage of either intraday tape.** First sampled tape row groups contain AAPL, QQQ, SPX, SPXW, SPY and TSLA; complete symbol/day counts require full-column scans and remain unverified.

Equity daily has 18 ticker labels and 19 security IDs. All ticker labels other than META have 753 rows. META identity and coverage are defective as described above. The daily fundamentals panel has 12,801 rows (17 IDs × 753 dates); one ID has no accounting values. Sector returns cover 11 groups × 753 days; industry returns cover 72 × 753.

Fundamentals quarterly is not limited to 2022–2024: report dates run 1990-01-31 through 2026-05-31; announcement dates through 2026-06-11, with 9,564 missing. Filtering by announcement availability is mandatory. Sector classification contains 1,996 securities and 1,886 company IDs. Ticker mapping contains 8,391 effective-dated records for 2,181 security IDs and 1,307 ticker labels. S&P membership has 557 security IDs and 60 missing ticker labels; use permanent IDs rather than dropping those rows.

## Which backtests are supported?

| Research or execution question | Feasibility from supplied data | Practical limit |
|---|---|---|
| Daily options selection, carry, volatility or dispersion research | Feasible after cleaning EOD chain, forwards, identities and risk inputs | EOD bid/ask marks are not guaranteed fills; adjusted contracts, settlement, corporate actions and data timing remain material. |
| Intraday options trade/volume/VWAP analysis | Feasible on a cleaned, selected tape | Need cancellations/corrections/condition provenance and completeness validation. Calculate per contract and window; do not pool unlike strikes or expiries into a purported executable VWAP. |
| Spread crossing around observed option trades | Feasible as a conservative model | Attached NBBO has no independent quote clock; later available prices after latency are unknown without quote-event data. Displayed size cannot be reused indefinitely. |
| Passive option limit-order fills | Low confidence | A print at a limit price does not prove your order filled; queue, venue allocation, cancellations, hidden liquidity and routing are absent. Use bounded scenarios, not deterministic fills. |
| Multi-leg option strategies | Research feasible; execution uncertain | No complex-order-book data, package IDs or simultaneous executable leg quotes. Model legging risk, leg liquidity and fees; do not assume a net mid-price fill. |
| Equity opening/closing auction studies | Partly feasible after summary rebuild and coverage checks | Supplied windows omit early closing auctions; no auction imbalance/order-submission/rejection records. Auction print size does not guarantee order acceptance. |
| Intraday equity hedging near open/close | Partly feasible with quote/trade windows | Outside windows there is no full-day equity quote/trade history. Cannot claim continuous delta-hedge execution realism. |
| Full-day equity VWAP or equity VWAP scheduling | Not supported | Daily OHLCV and a typical-price proxy cannot reconstruct full-day trade VWAP or its volume curve. |
| L2 depth consumption / queue-position replay | Not supported | No market-depth or order-event feed. |
| Exact expiry/assignment P&L | Incomplete | No dedicated final settlement series, complete deliverables, exercise/assignment events, borrow or broker policies. SPX cash level is not the AM settlement value. |

The supplied schemas are trade/quote/reference data, not a simulator. Greeks are model estimates, not observed positions. Open interest cannot identify dealer ownership, dealer gamma sign, or whether trades opened or closed positions.

## VWAP: what can actually be calculated

For eligible executed trades **of the same instrument** in window W:

`VWAP(W) = sum(price_i × size_i) / sum(size_i)`

Use a fully specified option key (root/underlying identity, expiration, normalized strike, call/put, adjusted-contract specification) or an effective-dated equity security ID. Apply original/correction/cancellation policy before summing. A zero total quantity produces no valid VWAP.

- Option tapes: calculate trade VWAP by contract and observed window. Establish that the chosen tape represents the intended venue/session universe. When combining Greeks and NBBO, reconcile trades rather than summing both tapes. Exclude or separately analyze complex/late/corrected trades if their status can be established; option condition flags are not present in these extracts, so this may require upstream data.
- Equity auction-window tape: calculate eligible-print VWAP for supplied windows. This is not necessarily the official opening/closing cross price and is not full-day VWAP. The auction summary's `vwap_price` is a precomputed VWAP over selected prints; regenerate and reconcile it before use.
- Equity `vwap_proxy`: supplier defines `(H+L+C)/3`. It is a typical-price estimate with no trade-volume weighting. Sampled `dollar_volume` equals close × daily volume, so `dollar_volume / volume_raw` is a close, not an independent trade VWAP.
- Quotes: midpoint, quote-size-weighted midpoint and time-weighted quote measures are different statistics. They do not become executed VWAP just because bid/ask sizes are available.
- For options, premium VWAP weights by contract quantity. Dollar exposure/P&L must additionally use the correct premium multiplier and deliverables. Across nonstandard contracts, explicitly distinguish contract-weighted from exposure-weighted aggregation.

A realized day's VWAP and auction volume are **ex-post benchmarks**. Using them to decide order timing or a participation cap before they are known creates lookahead. Forecast capacity from lagged information, then report realized participation separately.

## Required normalization and joins

1. Create an instrument master that distinguishes equity security IDs, company IDs, option-system underlying IDs and individual option IDs. Preserve zero-padded company/classification IDs as strings. Validate integral floats before converting numeric IDs to integers.
2. Normalize option strike: EOD `strike_price / 1000`, NBBO `strike / 1000`, Greeks `strike` already in dollars. Normalize `CALL/PUT` to `C/P`. Parse each source's date encoding explicitly.
3. Confirm clock timezone with source documentation. The files do not encode it. An America/New_York market-clock interpretation is a working hypothesis, not verified metadata. Use timezone-aware instants after confirmation and respect DST, product sessions and early closes. Stored nanosecond type does not imply nanosecond source precision.
4. Equity → daily fundamentals: `(security_id, date)`, verified unique on both tables. Exclude the unrelated META fund and repair predecessor history first.
5. Equity → quarterly fundamentals: effective-date-qualified security/company linkage, then backward as-of on **availability**, not report period. For date-only availability, next-session use is a conservative default; revisions still require vintage provenance.
6. EOD chain → forwards: `(option_security_id, date, exdate=expiration, am_settlement=amsettlement)`. Validate right-side uniqueness. The EOD chain's own forward field is all null. SPX/SPXW share an underlying ID; keep contract symbol and settlement distinctions. Avoid joining the ticker mapping on underlying ID without handling its deliberate SPX/SPXW duplication.
7. Greeks ↔ NBBO: candidate normalized contract + trade date/time + exchange + price + size, after session reconciliation. Test key uniqueness, duplicate multiplicity and unmatched buckets. Multiple trades can share a millisecond; no unchecked nearest-time or many-to-many merge.
8. Ticker history and membership: date-qualified interval joins. Do not infer issuer from a ticker without date. Confirm interval endpoints; sample-end `out_date` can be censoring rather than a real deletion date.
9. Earnings: resolve effective ticker/issuer, period, announcement date/time/timezone, currency and duplicate policy. The table contains actuals, not analyst expectations or the historical schedule known in advance.
10. Macro/factors/overlays: align to an explicit strategy calendar and availability time. Factors and daily closing data are known after their observation period. Do not inner-join away days merely because mixed-frequency macro observations are missing.

## Execution model to build first

Start with a verified liquid subset and standard contracts. Fix strategy decision time and information cutoff independently of observed future fills. Establish whether signals are available before selecting a quote or trade.

For aggressive orders, use ask for buys and bid for sells at an eligible observation, charge actual broker/exchange/clearing fees where available, and stress additional slippage. Record the lack of independently timestamped quotes. For latency, do not invent the quote at arrival: use a quote-event feed when acquired, or report explicit optimistic/base/conservative scenarios with unobserved arrival liquidity marked as assumed. Reject zero, crossed or missing quotes under a documented policy; assess locked quotes separately. Keep a no-fill outcome.

Cap size conservatively using information available at order time and sensitivity ranges. Attached displayed size gives limited evidence and cannot model replenishment, depth beyond best prices, hidden orders or impact. Do not assume each historical trade/quote is an independent refill of available liquidity. For passive orders, require an explicit probabilistic or pessimistic fill model; a touch or print alone is insufficient.

For auction orders, model submission cutoffs, eligibility, potential rejection and participation before observing the auction result. Use the primary auction price after conditions/corrections are reconciled. Regenerate the summary and obtain early-close coverage first.

For portfolios, include cash, financing, borrow where relevant, margin constraints, contract multipliers, dividends, corporate actions and exercise/assignment. Use product-appropriate models: a European forward-based formula is not a universal replacement for American-style equity/ETF option valuation. EOD forward prices must not leak into same-day intraday Greeks. Separate theoretical mark P&L from liquidation P&L.

Validate on calendar-based holdouts and report sensitivity to spread costs, latency, no-fills, size caps, data filters, hedge frequency and settlement. Capacity estimates should be ranges, not precision claims.

## Additional data for greater realism

- **Full quote-event history for options** with quote timestamps, sizes, venue attribution, sequence/tie-breaking information and conditions. This resolves the current trade-time-only quote sampling limit.
- **Venue-specific L2 market-by-price depth** with sufficient levels and snapshots plus add/change/delete updates for aggressive depth consumption. For queue estimates, seek **market-by-order** events with order IDs and venue matching/allocation rules. Even an order-event replay does not eliminate hidden liquidity or the counterfactual market response to our own orders.
- **Full-day equity trades and quotes**, including early-close sessions, for delta hedging, full-day VWAP and volume schedules.
- **Auction-specific primary-exchange data**: official cross price/size, imbalance/indicative price updates, session calendar and order cutoffs.
- **Contract/reference lifecycle data**: OCC deliverables/adjustments, exercise styles, premium multipliers, product calendars, AM/PM final settlement values, dividends and distributions.
- **Data provenance**: exact vendor/feed, condition/venue codebooks, trade correction/cancel policy, clock conventions, IV/Greek units/models, macro source series IDs and publication vintages, fundamentals units/currencies and revision policy.
- **Broker/execution assumptions**: commissions, venue/clearing fees, borrow/financing, latency distributions, routing and allocation. No such execution logs are supplied here.

These are capability requirements, not a claim that a particular vendor supplies all instruments/history needed or a recommendation to purchase before a scoped coverage check.

## Sources and interpretation

Dataset facts come from the supplied files and their metadata; source links are recorded per file in `file_manifest.csv`. External references support market-data concepts, not the provenance of these particular extracts:

- [ThetaData option trade/quote documentation](https://www.thetadata.net/docs/operations/option_history_trade_quote.html): documents a trade-plus-last-NBBO design. The supplied schema resembles such a design; this does **not** verify that ThetaData is its source.
- [Databento schema definitions](https://www.databento.tech/docs/schemas/whats-a-schema) and [market-by-order definition](https://www.databento.tech/docs/schemas/mbo): distinguish best-price data, depth, and order-ID events.
- [NYSE Daily TAQ specification](https://www.nyse.com/publicdocs/nyse/data/Daily_TAQ_Client_Spec_v3.3.pdf): relevant context for equity trade/quote condition fields. The exact applicable source version and any preprocessing still need confirmation.
- [Cboe SPX product reference](https://www.cboe.com/tradable-products/sp-500/spx-options/): SPX cash settlement and European exercise. Historical contract/session rules must be checked for each observation period.

## How to use the deliverables

Open `DATA_DICTIONARY.html` for searchable dataset cards, every column definition, measured null/min/max statistics, coverage and a complete file manifest. Read this assessment first to understand what the numbers do and do not establish.

`dataset_catalog.csv`: 21 dataset summaries. `column_dictionary.csv`: 267 field definitions with physical types and all-partition statistics. `file_manifest.csv`: 152 files with exact row/column counts, bytes, source links and verification scope. `file_columns.csv`: physical-file-level field statistics. `ticker_coverage.csv`: measured daily-equity and auction-summary coverage. `full_profiles.json`: full-scan profiles and examples for the 53 smaller files. `metadata/`: individual verified file metadata. `*_sample.json`: selected large-file records and diagnostics. `README.md`: this assessment plus all dataset schemas and the complete physical-file inventory.

Not performed: full scans of the roughly four billion option-tape rows, complete per-symbol/day tape counts, full-dataset trade-join reconciliation, correction/cancel reconstruction, independent vendor provenance verification, and a production backtest. Those are subsequent validation tasks, not implied by the exact footer row counts.


## Complete dataset catalogue

| Dataset | Files | Rows | Columns | GB | Observation start | Observation end |
| --- | --- | --- | --- | --- | --- | --- |
| auction_volume_summary_monthly | 36 | 23,494 | 8 | 0.001002 | 2022-01-03 | 2024-12-31 |
| auction_window_trades_monthly | 36 | 66,092,687 | 9 | 1.037470 | 2022-01-03 | 2024-12-31 |
| dspx_dispersion_index_2022_2024.parquet | 1 | 753 | 2 | 0.000012 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| earnings_actuals_2022_2024.parquet | 1 | 66,713 | 8 | 0.000485 |  |  |
| eod_option_chain/_ticker_id_mapping | 1 | 20 | 4 | 0.000004 |  |  |
| eod_option_chain/eod_option_chain | 3 | 57,600,631 | 26 | 2.369002 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| eod_option_chain/forward_prices | 3 | 299,709 | 5 | 0.003218 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| equity_daily_2022_2024.parquet | 1 | 13,464 | 30 | 0.001590 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| factor_returns_daily_2022_2024.parquet | 1 | 753 | 8 | 0.000026 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| fundamentals_daily_2022_2024.parquet | 1 | 12,801 | 32 | 0.000456 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| fundamentals_quarterly.parquet | 1 | 139,137 | 33 | 0.017745 |  |  |
| industry_returns_daily_2022_2024.parquet | 1 | 54,216 | 6 | 0.001633 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| intraday_nbbo_close_open_windows_monthly | 36 | 553,094,031 | 11 | 5.121792 | 2022-01-03 | 2024-12-31 |
| macro_daily_2022_2024.parquet | 1 | 798 | 10 | 0.000023 | 2022-01-01 00:00:00 | 2024-12-31 00:00:00 |
| market_overlays_2022_2024.parquet | 1 | 782 | 11 | 0.000040 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| option_trades_with_greeks_quarterly | 12 | 2,258,715,280 | 16 | 57.512447 | 2022-01-03 | 2024-12-31 |
| option_trades_with_nbbo_quarterly | 12 | 1,808,163,203 | 13 | 22.472218 | 20220103 | 20241231 |
| sector_classification.parquet | 1 | 1,996 | 13 | 0.000099 |  |  |
| sector_returns_daily_2022_2024.parquet | 1 | 8,283 | 6 | 0.000257 | 2022-01-03 00:00:00 | 2024-12-31 00:00:00 |
| sp500_membership_2022_2024.parquet | 1 | 557 | 7 | 0.000024 |  |  |
| ticker_security_mapping.parquet | 1 | 8,391 | 9 | 0.000172 |  |  |

## Measured equity and auction coverage

| ticker | equity_rows | equity_security_ids | expected_calendar_days | equity_missing_days | auction_MOO_days | auction_MOC_days |
| --- | --- | --- | --- | --- | --- | --- |
| AAPL | 753 | 14593 | 753 | 0 | 753 | 747 |
| AMD | 753 | 61241 | 753 | 0 | 753 | 747 |
| AMZN | 753 | 84788 | 753 | 0 | 753 | 747 |
| AVGO | 753 | 93002 | 753 | 0 | 753 | 747 |
| CRM | 753 | 90215 | 753 | 0 | 742 | 747 |
| GOOGL | 753 | 90319 | 753 | 0 | 0 | 0 |
| JPM | 753 | 47896 | 753 | 0 | 753 | 747 |
| LLY | 753 | 50876 | 753 | 0 | 404 | 335 |
| META | 663 | 21413;13407 | 753 | 90 | 663 | 657 |
| MSFT | 753 | 10107 | 753 | 0 | 753 | 747 |
| NFLX | 753 | 89393 | 753 | 0 | 753 | 747 |
| NVDA | 753 | 86580 | 753 | 0 | 753 | 747 |
| QQQ | 753 | 86755 | 753 | 0 | 753 | 747 |
| SPY | 753 | 84398 | 753 | 0 | 752 | 747 |
| TSLA | 753 | 93436 | 753 | 0 | 753 | 747 |
| UNH | 753 | 92655 | 753 | 0 | 740 | 742 |
| WMT | 753 | 55976 | 753 | 0 | 745 | 746 |
| XOM | 753 | 11850 | 753 | 0 | 311 | 163 |

## auction_volume_summary_monthly

Selected equity auction prints aggregated by date/root/MOO-or-MOC.

**Shape:** 23,494 rows × 8 columns across 36 file(s). Compressed bytes: 1,002,031.

**Row key:** date, sym_root, side.

**Use:** Auction benchmark and historical size diagnostics; incomplete symbol/session coverage.

**Verification:** Full scan of all 36 files.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | string | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| sym_root | string | 0 | 0.0 | Equity ticker/root associated with this record; resolve date-qualified instrument identity. |
| side | string | 0 | 0.0 | Auction category MOO/MOC, not buy/sell trade direction. |
| total_size | int64 | 0 | 0.0 | Sum of selected auction-flagged print quantities for date/root/side; not proven complete official exchange auction size. |
| num_prints | int64 | 0 | 0.0 | Count of selected prints in summary. |
| vwap_price | double | 0 | 0.0 | Quantity-weighted execution price of selected auction-flagged prints. Not whole-day equity VWAP. |
| first_print_time | string | 0 | 0.0 | First selected print clock time string; no timezone attached. |
| last_print_time | string | 0 | 0.0 | Last selected print clock time string; no timezone attached. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| auction_volume_summary_monthly/2022_01.parquet | 629 | 8 | 27627 | 1 |
| auction_volume_summary_monthly/2022_02.parquet | 559 | 8 | 25095 | 1 |
| auction_volume_summary_monthly/2022_03.parquet | 668 | 8 | 28836 | 1 |
| auction_volume_summary_monthly/2022_04.parquet | 584 | 8 | 25874 | 1 |
| auction_volume_summary_monthly/2022_05.parquet | 625 | 8 | 27190 | 1 |
| auction_volume_summary_monthly/2022_06.parquet | 674 | 8 | 28907 | 1 |
| auction_volume_summary_monthly/2022_07.parquet | 661 | 8 | 28297 | 1 |
| auction_volume_summary_monthly/2022_08.parquet | 711 | 8 | 29937 | 1 |
| auction_volume_summary_monthly/2022_09.parquet | 650 | 8 | 27832 | 1 |
| auction_volume_summary_monthly/2022_10.parquet | 643 | 8 | 27689 | 1 |
| auction_volume_summary_monthly/2022_11.parquet | 638 | 8 | 27374 | 1 |
| auction_volume_summary_monthly/2022_12.parquet | 652 | 8 | 27889 | 1 |
| auction_volume_summary_monthly/2023_01.parquet | 610 | 8 | 26448 | 1 |
| auction_volume_summary_monthly/2023_02.parquet | 591 | 8 | 25994 | 1 |
| auction_volume_summary_monthly/2023_03.parquet | 725 | 8 | 30359 | 1 |
| auction_volume_summary_monthly/2023_04.parquet | 592 | 8 | 25643 | 1 |
| auction_volume_summary_monthly/2023_05.parquet | 688 | 8 | 28840 | 1 |
| auction_volume_summary_monthly/2023_06.parquet | 647 | 8 | 27427 | 1 |
| auction_volume_summary_monthly/2023_07.parquet | 625 | 8 | 26833 | 1 |
| auction_volume_summary_monthly/2023_08.parquet | 722 | 8 | 29950 | 1 |
| auction_volume_summary_monthly/2023_09.parquet | 623 | 8 | 26571 | 1 |
| auction_volume_summary_monthly/2023_10.parquet | 706 | 8 | 29414 | 1 |
| auction_volume_summary_monthly/2023_11.parquet | 654 | 8 | 27476 | 1 |
| auction_volume_summary_monthly/2023_12.parquet | 641 | 8 | 27027 | 1 |
| auction_volume_summary_monthly/2024_01.parquet | 673 | 8 | 28184 | 1 |
| auction_volume_summary_monthly/2024_02.parquet | 626 | 8 | 26797 | 1 |
| auction_volume_summary_monthly/2024_03.parquet | 635 | 8 | 27151 | 1 |
| auction_volume_summary_monthly/2024_04.parquet | 701 | 8 | 29186 | 1 |
| auction_volume_summary_monthly/2024_05.parquet | 710 | 8 | 29647 | 1 |
| auction_volume_summary_monthly/2024_06.parquet | 604 | 8 | 26112 | 1 |
| auction_volume_summary_monthly/2024_07.parquet | 691 | 8 | 29086 | 1 |
| auction_volume_summary_monthly/2024_08.parquet | 692 | 8 | 29130 | 1 |
| auction_volume_summary_monthly/2024_09.parquet | 632 | 8 | 27131 | 1 |
| auction_volume_summary_monthly/2024_10.parquet | 741 | 8 | 30551 | 1 |
| auction_volume_summary_monthly/2024_11.parquet | 621 | 8 | 26688 | 1 |
| auction_volume_summary_monthly/2024_12.parquet | 650 | 8 | 27839 | 1 |

## auction_window_trades_monthly

Equity executed trades in narrow opening/closing windows.

**Shape:** 66,092,687 rows × 9 columns across 36 file(s). Compressed bytes: 1,037,469,990.

**Row key:** No certified global key; candidate date, ex, tr_id with corrections.

**Use:** Trade VWAP inside supplied windows and auction extraction after condition/correction handling.

**Verification:** All 36 footers; first January 2022 row group scanned (85,350 rows).

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | string | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| time_m | string | 0 | 0.0 | Equity event clock time string; sampled microsecond precision. Combine with date; source timezone and event-clock meaning need confirmation. |
| ex | string | 0 | 0.0 | Equity trade exchange code string; requires applicable TAQ codebook. |
| sym_root | string | 0 | 0.0 | Equity ticker/root associated with this record; resolve date-qualified instrument identity. |
| tr_scond | string | 2059616 | 3.116254 | Composite equity sale-condition string; can contain multiple codes. O/6 alone do not establish complete primary auction coverage. |
| size | int64 | 0 | 0.0 | Executed trade quantity; options conventionally contracts, equities shares. Validate corrections and units before VWAP. |
| price | double | 0 | 0.0 | Executed trade price; premium per quoted unit for options, share price for equities. Not a guaranteed hypothetical fill. |
| tr_corr | string | 0 | 0.0 | Equity trade correction indicator; retain and decode before trade/VWAP aggregation. |
| tr_id | string | 0 | 0.0 | Equity trade identifier stored as text; use date and exchange scope. Not an order ID. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| auction_window_trades_monthly/2022_01.parquet | 1,978,532 | 9 | 30701887 | 20 |
| auction_window_trades_monthly/2022_02.parquet | 1,736,823 | 9 | 26979671 | 19 |
| auction_window_trades_monthly/2022_03.parquet | 1,858,724 | 9 | 29662187 | 23 |
| auction_window_trades_monthly/2022_04.parquet | 1,730,928 | 9 | 27022665 | 20 |
| auction_window_trades_monthly/2022_05.parquet | 1,913,563 | 9 | 29932864 | 21 |
| auction_window_trades_monthly/2022_06.parquet | 1,732,879 | 9 | 27319512 | 21 |
| auction_window_trades_monthly/2022_07.parquet | 1,367,698 | 9 | 22123927 | 20 |
| auction_window_trades_monthly/2022_08.parquet | 1,450,453 | 9 | 23881218 | 23 |
| auction_window_trades_monthly/2022_09.parquet | 1,475,357 | 9 | 24021139 | 21 |
| auction_window_trades_monthly/2022_10.parquet | 1,575,433 | 9 | 25641597 | 21 |
| auction_window_trades_monthly/2022_11.parquet | 1,579,090 | 9 | 25328741 | 21 |
| auction_window_trades_monthly/2022_12.parquet | 1,446,062 | 9 | 23779886 | 21 |
| auction_window_trades_monthly/2023_01.parquet | 1,527,003 | 9 | 24722842 | 20 |
| auction_window_trades_monthly/2023_02.parquet | 1,506,592 | 9 | 24287523 | 19 |
| auction_window_trades_monthly/2023_03.parquet | 1,607,742 | 9 | 26636157 | 23 |
| auction_window_trades_monthly/2023_04.parquet | 1,257,622 | 9 | 20447814 | 19 |
| auction_window_trades_monthly/2023_05.parquet | 1,575,736 | 9 | 24993805 | 22 |
| auction_window_trades_monthly/2023_06.parquet | 1,762,235 | 9 | 27992222 | 21 |
| auction_window_trades_monthly/2023_07.parquet | 1,596,982 | 9 | 25409038 | 20 |
| auction_window_trades_monthly/2023_08.parquet | 1,736,174 | 9 | 27928314 | 23 |
| auction_window_trades_monthly/2023_09.parquet | 1,444,578 | 9 | 23250278 | 20 |
| auction_window_trades_monthly/2023_10.parquet | 1,585,213 | 9 | 25897868 | 22 |
| auction_window_trades_monthly/2023_11.parquet | 1,577,929 | 9 | 25091406 | 21 |
| auction_window_trades_monthly/2023_12.parquet | 1,602,419 | 9 | 25281137 | 20 |
| auction_window_trades_monthly/2024_01.parquet | 2,047,403 | 9 | 31481326 | 21 |
| auction_window_trades_monthly/2024_02.parquet | 2,029,334 | 9 | 31168125 | 20 |
| auction_window_trades_monthly/2024_03.parquet | 2,113,215 | 9 | 32428332 | 20 |
| auction_window_trades_monthly/2024_04.parquet | 2,285,923 | 9 | 35456048 | 22 |
| auction_window_trades_monthly/2024_05.parquet | 1,923,919 | 9 | 30222262 | 22 |
| auction_window_trades_monthly/2024_06.parquet | 2,203,244 | 9 | 33248740 | 19 |
| auction_window_trades_monthly/2024_07.parquet | 2,554,013 | 9 | 39221255 | 22 |
| auction_window_trades_monthly/2024_08.parquet | 2,591,729 | 9 | 39821168 | 22 |
| auction_window_trades_monthly/2024_09.parquet | 2,129,342 | 9 | 32744288 | 20 |
| auction_window_trades_monthly/2024_10.parquet | 2,411,587 | 9 | 36536541 | 23 |
| auction_window_trades_monthly/2024_11.parquet | 2,458,994 | 9 | 36507753 | 20 |
| auction_window_trades_monthly/2024_12.parquet | 2,718,217 | 9 | 40300454 | 21 |

## dspx_dispersion_index_2022_2024.parquet

Daily dispersion index closing level.

**Shape:** 753 rows × 2 columns across 1 file(s). Compressed bytes: 11,797.

**Row key:** date.

**Use:** Benchmark/context for dispersion research; not directly traded fills.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| dspx_close | double | 0 | 0.0 | Daily dispersion-index close used as benchmark; not an executable strategy return or options basket. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| dspx_dispersion_index_2022_2024.parquet | 753 | 2 | 11797 | 1 |

## earnings_actuals_2022_2024.parquet

Historical earnings announcements and actual EPS for broad ticker set.

**Shape:** 66,713 rows × 8 columns across 1 file(s). Compressed bytes: 484,837.

**Row key:** No validated unique event key; ticker, period_end, announce_date is a candidate.

**Use:** Earnings exclusion/event flags after duplicate, identity, time and currency handling.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| ticker | string | 2521 | 3.778874 | Ticker label; must resolve to a security for the observation date. META collision confirmed. |
| company_name | string | 2521 | 3.778874 | Issuer/company name label; not an instrument key. |
| period_end | string | 0 | 0.0 | Earnings accounting period end, ISO date string. |
| announce_date | string | 0 | 0.0 | Announcement date: fundamentals availability date or earnings event date; combine with time and release/vintage rules. |
| announce_time | string | 0 | 0.0 | Earnings announcement clock time string; timezone and placeholder conventions not specified. Midnight may be unknown time. |
| actual_eps | double | 10670 | 15.993884 | Reported actual EPS; currencies vary and extreme outliers exist. 10,670 nulls. Do not assume directly comparable accounting/split basis. |
| currency | string | 0 | 0.0 | EPS currency code. 33 observed categories including BPN; preserve raw code and verify mapping. |
| measure | string | 0 | 0.0 | Earnings measure label; observed EPS. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| earnings_actuals_2022_2024.parquet | 66,713 | 8 | 484837 | 1 |

## eod_option_chain/_ticker_id_mapping

Underlying ticker to option-system security ID.

**Shape:** 20 rows × 4 columns across 1 file(s). Compressed bytes: 3,717.

**Row key:** ticker; ID deliberately not unique for SPX/SPXW.

**Use:** Join bridge only; 20 tickers, 19 option_security_id values.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| ticker | string | 0 | 0.0 | Ticker label; must resolve to a security for the observation date. META collision confirmed. |
| option_security_id | int64 | 0 | 0.0 | Underlying identifier in the options dataset; not the individual option contract ID. SPX/SPXW share 108105. Float64 in chains/forwards, int64 in mapping. |
| issuer | string | 0 | 0.0 | Issuer name in option ticker mapping. |
| note | string | 0 | 0.0 | Supplier annotation; includes build/expansion notes, not effective-dated security history. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| eod_option_chain/_ticker_id_mapping.parquet | 20 | 4 | 3717 | 1 |

## eod_option_chain/eod_option_chain

End-of-day individual option contract observations.

**Shape:** 57,600,631 rows × 26 columns across 3 file(s). Compressed bytes: 2,369,001,508.

**Row key:** Candidate date, optionid; validate uniqueness before use.

**Use:** Daily option selection, marks and risk; no intraday execution replay or quote sizes.

**Verification:** All 3 current remote footers; existing local files match byte sizes and row counts; 5 sample records inspected.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| option_security_id | double | 0 | 0.0 | Underlying identifier in the options dataset; not the individual option contract ID. SPX/SPXW share 108105. Float64 in chains/forwards, int64 in mapping. |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| symbol | string | 0 | 0.0 | In EOD chains: encoded option contract symbol. In Greeks tape: underlying/root ticker, not a complete contract identifier. |
| symbol_flag | string | 0 | 0.0 | Supplier symbol-format flag; observed 1. Vendor codebook required. |
| exdate | timestamp[ns] | 0 | 0.0 | Contract expiration date in EOD chain; combine with settlement and actual session rules for time to expiry. |
| last_date | timestamp[ns] | 10014370 | 17.385869 | Supplier last trade date field; nullable and can precede observation date. Exact vendor convention requires confirmation. |
| cp_flag | string | 0 | 0.0 | Call/put flag, C/P. |
| strike_price | double | 0 | 0.0 | EOD strike scaled by 1,000; divide by 1,000 to obtain dollar strike (supplier dictionary, consistent with sampled contracts). |
| best_bid | double | 0 | 0.0 | Best bid price. EOD: end-of-day option quote; equity NBBO: quote-event top of book. No additional price levels. |
| best_offer | double | 0 | 0.0 | End-of-day best option offer/ask price; quote size is absent. |
| volume | double | 0 | 0.0 | EOD option daily traded volume, stored as double. Not quote liquidity or a live participation allowance. |
| open_interest | double | 0 | 0.0 | EOD option open interest, stored as double. Availability timing must be confirmed; not dealer inventory or executable size. |
| impl_volatility | double | 6605418 | 11.467614 | EOD model implied volatility, typically annualized decimal. 6,605,418 nulls across all chains; model convention requires vendor confirmation. |
| delta | double | 6605418 | 11.467614 | Option sensitivity to underlying price. Model, units, timestamp and exercise convention must be established. |
| gamma | double | 6605418 | 11.467614 | EOD option delta sensitivity; absent from intraday Greeks tape. Do not infer dealer positioning from open interest alone. |
| vega | double | 6605418 | 11.467614 | Option sensitivity to volatility; dollar/percentage-point scaling must be confirmed before aggregation across sources. |
| theta | double | 6605419 | 11.467616 | Option time-decay sensitivity; per-day/per-year and pricing convention must be confirmed. |
| optionid | double | 0 | 0.0 | Individual option identifier stored as double. Validate integral values before lossless integer conversion. |
| cfadj | double | 0 | 0.0 | Supplier cumulative contract adjustment factor, stored as double; confirm corporate-action application from source documentation. |
| am_settlement | double | 0 | 0.0 | EOD settlement indicator, numeric 1 AM / 0 PM per supplied dictionary; float physical type. |
| contract_size | double | 0 | 0.0 | Supplier option contract size/deliverable quantity, stored as double; nonstandard values exist (2022 range 7–172). Not sufficient alone to resolve all adjusted deliverables. |
| ss_flag | string | 0 | 0.0 | Supplier special-settlement flag; retain and decode using exact vendor manual before trading. |
| forward_price | string | 57600631 | 100.0 | EOD chain placeholder stored as string and entirely null in all 57,600,631 rows. Use separate forward_prices tables. |
| expiry_indicator | string | 36654579 | 63.635725 | Supplier expiry classification; nullable, observed m/w. Decode before using as a contract selection rule. |
| root | string | 57600631 | 100.0 | NBBO tape: underlying option root. EOD chain: entirely null placeholder. |
| suffix | string | 57600631 | 100.0 | EOD placeholder; entirely null. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| eod_option_chain/eod_option_chain_2022.parquet | 18,239,871 | 26 | 754084185 | 18 |
| eod_option_chain/eod_option_chain_2023.parquet | 17,479,400 | 26 | 712636838 | 17 |
| eod_option_chain/eod_option_chain_2024.parquet | 21,881,360 | 26 | 902280485 | 21 |

## eod_option_chain/forward_prices

End-of-day forward references by underlying/date/expiry/settlement.

**Shape:** 299,709 rows × 5 columns across 3 file(s). Compressed bytes: 3,218,061.

**Row key:** option_security_id, date, expiration, amsettlement.

**Use:** Forward reference for date-specific pricing; EOD timing unsuitable for same-day intraday signal.

**Verification:** Full scan of all 3 downloaded files.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| option_security_id | double | 0 | 0.0 | Underlying identifier in the options dataset; not the individual option contract ID. SPX/SPXW share 108105. Float64 in chains/forwards, int64 in mapping. |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| expiration | timestamp[ns] | 0 | 0.0 | Contract expiration: ISO string in Greeks, YYYYMMDD integer in NBBO, timestamp in forwards. |
| amsettlement | double | 0 | 0.0 | Forward table AM/PM settlement indicator; normalize to same domain as am_settlement. |
| forwardprice | double | 0 | 0.0 | Numeric date/expiry-specific underlying forward reference. EOD observation; not a contemporaneous intraday forward. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| eod_option_chain/forward_prices_2022.parquet | 93,025 | 5 | 1000067 | 1 |
| eod_option_chain/forward_prices_2023.parquet | 97,183 | 5 | 1044484 | 1 |
| eod_option_chain/forward_prices_2024.parquet | 109,501 | 5 | 1173510 | 1 |

## equity_daily_2022_2024.parquet

Daily raw/adjusted equity OHLCV and identifiers.

**Shape:** 13,464 rows × 30 columns across 1 file(s). Compressed bytes: 1,590,318.

**Row key:** security_id, date (verified unique).

**Use:** Daily underlying returns/hedge marks; META requires identity repair; VWAP proxy is not VWAP.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| security_id | int64 | 0 | 0.0 | Permanent equity security identifier; join with effective dates, never a ticker alone. |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| open_raw | double | 0 | 0.0 | Raw daily opening share price. |
| high_raw | double | 0 | 0.0 | Raw daily high share price. |
| low_raw | double | 0 | 0.0 | Raw daily low share price. |
| close_raw | double | 0 | 0.0 | Raw daily closing share price; consult close_is_quote_midpoint. |
| bid_eod | double | 0 | 0.0 | Equity end-of-day best bid; exact observation time is not provided. |
| ask_eod | double | 0 | 0.0 | Equity end-of-day best ask; exact observation time is not provided. |
| volume_raw | double | 0 | 0.0 | Raw daily equity share volume, stored as double. |
| trade_count | int64 | 5290 | 39.289958 | Daily equity trade count, int64. |
| total_return | double | 0 | 0.0 | Daily total return including distributions per supplier; decimal return convention. |
| price_return_ex_div | double | 0 | 0.0 | Daily price return excluding dividends per supplier; decimal return convention. |
| price_adj_factor | double | 0 | 0.0 | Supplier price adjustment factor used in adjusted OHLC calculation. |
| share_adj_factor | double | 0 | 0.0 | Supplier share adjustment factor; confirm direction before adjusting quantities. |
| shares_outstanding_k | double | 0 | 0.0 | Equity shares outstanding in thousands, per field naming/supplier dictionary. |
| ticker | string | 0 | 0.0 | Ticker label; must resolve to a security for the observation date. META collision confirmed. |
| company_name_pit | string | 0 | 0.0 | Issuer name labelled point-in-time by supplier. Equity META rows demonstrate distinct issuers. |
| share_class_code | int64 | 0 | 0.0 | Supplier share/security class code; no local decoder supplied. |
| exchange_code | int64 | 0 | 0.0 | Supplier listing exchange code; not interchangeable with intraday venue codes. |
| sic_code_pit | int64 | 0 | 0.0 | SIC industry code labelled point-in-time. |
| naics_code_pit | string | 0 | 0.0 | NAICS code labelled point-in-time; retain as text. |
| cusip_pit | string | 0 | 0.0 | CUSIP-like identifier labelled point-in-time; sample is eight characters; preserve leading zeros. |
| close_is_quote_midpoint | bool | 0 | 0.0 | Boolean indicator that closing value is quote midpoint rather than trade. |
| adj_open | double | 0 | 0.0 | Adjusted daily opening price; supplier states raw / price_adj_factor. |
| adj_high | double | 0 | 0.0 | Adjusted daily high price; supplier states raw / price_adj_factor. |
| adj_low | double | 0 | 0.0 | Adjusted daily low price; supplier states raw / price_adj_factor. |
| adj_close | double | 0 | 0.0 | Adjusted daily close; supplier states raw / price_adj_factor. Never mix with raw strikes/premiums. |
| adj_volume | double | 0 | 0.0 | Adjusted daily equity volume; confirm adjustment convention against share_adj_factor. |
| dollar_volume | double | 0 | 0.0 | Derived daily turnover value; sampled value equals close_raw × volume_raw. Not the sum of actual trade dollars. |
| vwap_proxy | double | 0 | 0.0 | (high_raw + low_raw + close_raw) / 3 per supplier; typical-price proxy, not transaction VWAP. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| equity_daily_2022_2024.parquet | 13,464 | 30 | 1590318 | 1 |

## factor_returns_daily_2022_2024.parquet

Daily market/style factor and risk-free returns.

**Shape:** 753 rows × 8 columns across 1 file(s). Compressed bytes: 26,335.

**Row key:** date.

**Use:** Return attribution and risk conditioning; no executable order information.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| market_minus_rf | double | 0 | 0.0 | Daily market excess return (market minus risk-free), decimal per supplier. |
| size_factor | double | 0 | 0.0 | Daily size factor return, decimal per supplier. |
| value_factor | double | 0 | 0.0 | Daily value factor return, decimal per supplier. |
| momentum_factor | double | 0 | 0.0 | Daily momentum factor return, decimal per supplier. |
| risk_free_rate_1m | double | 0 | 0.0 | Daily risk-free return associated with one-month instrument in factor series; not interchangeable with annual treasury_1mo yield. |
| profitability_factor | double | 0 | 0.0 | Daily profitability factor return, decimal per supplier. |
| investment_factor | double | 0 | 0.0 | Daily investment factor return, decimal per supplier. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| factor_returns_daily_2022_2024.parquet | 753 | 8 | 26335 | 1 |

## fundamentals_daily_2022_2024.parquet

Daily forward-filled quarterly accounting panel.

**Shape:** 12,801 rows × 32 columns across 1 file(s). Compressed bytes: 456,340.

**Row key:** security_id, date (verified unique).

**Use:** Fundamental signals with announcement-time safeguards; one all-null issuer history.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| security_id | int64 | 0 | 0.0 | Permanent equity security identifier; join with effective dates, never a ticker alone. |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| as_of_date | timestamp[ns] | 753 | 5.882353 | Supplier announcement/as-of date used for daily fundamentals join. Date-only; same-day after-close announcements can still cause lookahead. |
| report_date | timestamp[ns] | 753 | 5.882353 | Accounting period end/report date. Not information release date. Quarterly history extends into 2026. |
| revenue | double | 1506 | 11.764706 | Revenue for accounting period. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| cogs | double | 753 | 5.882353 | Cost of goods sold. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| sga | double | 753 | 5.882353 | Selling, general and administrative expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| operating_income | double | 753 | 5.882353 | Accounting operating income. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| net_income | double | 753 | 5.882353 | Accounting net income. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| eps_basic | double | 753 | 5.882353 | Basic earnings per share. |
| eps_diluted | double | 753 | 5.882353 | Diluted earnings per share. |
| operating_cash_flow_ytd | double | 753 | 5.882353 | Operating cash flow, fiscal year to date; must difference within fiscal year to derive discrete quarters. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| capex_ytd | double | 753 | 5.882353 | Capital expenditure, fiscal year to date; must difference within fiscal year for discrete quarters. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| total_assets | double | 753 | 5.882353 | Total assets. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| total_liabilities | double | 753 | 5.882353 | Total liabilities. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| book_equity | double | 753 | 5.882353 | Book equity; vendor definition needs confirmation. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| common_equity | double | 753 | 5.882353 | Common shareholders equity. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| long_term_debt | double | 753 | 5.882353 | Long-term debt. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| short_term_debt | double | 984 | 7.686899 | Short-term debt. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| cash_and_equivalents | double | 753 | 5.882353 | Cash and equivalents. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| inventory | double | 1354 | 10.577299 | Inventory. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| receivables | double | 753 | 5.882353 | Receivables. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| current_liabilities | double | 1506 | 11.764706 | Current liabilities. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| interest_expense | double | 2066 | 16.139364 | Interest expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| rd_expense | double | 2079 | 16.240919 | Research and development expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| common_shares_outstanding_mn | double | 753 | 5.882353 | Common shares outstanding in millions per field name. |
| dividend_per_share | double | 753 | 5.882353 | Dividend per share for supplier reporting period. |
| income_taxes | double | 753 | 5.882353 | Income tax expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| net_ppe | double | 753 | 5.882353 | Net property, plant and equipment. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| goodwill | double | 1506 | 11.764706 | Goodwill. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| intangibles | double | 753 | 5.882353 | Intangible assets. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| gross_profit | double | 1506 | 11.764706 | Gross profit. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| fundamentals_daily_2022_2024.parquet | 12,801 | 32 | 456340 | 1 |

## fundamentals_quarterly.parquet

Long quarterly accounting history, 1990 through 2026.

**Shape:** 139,137 rows × 33 columns across 1 file(s). Compressed bytes: 17,745,404.

**Row key:** Candidate company_id, report_date; verify reporting variants.

**Use:** As-of fundamental joins; exclude post-backtest announcements and unverified revisions.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| company_id | string | 0 | 0.0 | Company identifier stored as a zero-padded string; preserve leading zeros. |
| report_date | string | 0 | 0.0 | Accounting period end/report date. Not information release date. Quarterly history extends into 2026. |
| announce_date | string | 9564 | 6.873801 | Announcement date: fundamentals availability date or earnings event date; combine with time and release/vintage rules. |
| fiscal_year | int64 | 0 | 0.0 | Fiscal year, integer. |
| fiscal_quarter | int64 | 19 | 0.013656 | Fiscal quarter, integer. |
| revenue | double | 9301 | 6.684778 | Revenue for accounting period. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| cogs | double | 4556 | 3.27447 | Cost of goods sold. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| sga | double | 34373 | 24.704428 | Selling, general and administrative expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| operating_income | double | 5169 | 3.715043 | Accounting operating income. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| net_income | double | 3673 | 2.639844 | Accounting net income. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| eps_basic | double | 5950 | 4.276361 | Basic earnings per share. |
| eps_diluted | double | 5932 | 4.263424 | Diluted earnings per share. |
| operating_cash_flow_ytd | double | 12809 | 9.206034 | Operating cash flow, fiscal year to date; must difference within fiscal year to derive discrete quarters. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| capex_ytd | double | 13593 | 9.769508 | Capital expenditure, fiscal year to date; must difference within fiscal year for discrete quarters. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| total_assets | double | 6229 | 4.476882 | Total assets. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| total_liabilities | double | 6295 | 4.524318 | Total liabilities. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| book_equity | double | 6269 | 4.505631 | Book equity; vendor definition needs confirmation. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| common_equity | double | 6792 | 4.88152 | Common shareholders equity. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| long_term_debt | double | 7237 | 5.201348 | Long-term debt. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| short_term_debt | double | 15911 | 11.435492 | Short-term debt. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| cash_and_equivalents | double | 6750 | 4.851334 | Cash and equivalents. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| inventory | double | 10276 | 7.385526 | Inventory. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| receivables | double | 8971 | 6.447602 | Receivables. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| current_liabilities | double | 29095 | 20.911045 | Current liabilities. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| interest_expense | double | 21995 | 15.80816 | Interest expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| rd_expense | double | 82694 | 59.433508 | Research and development expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| common_shares_outstanding_mn | double | 6697 | 4.813242 | Common shares outstanding in millions per field name. |
| dividend_per_share | double | 4718 | 3.390902 | Dividend per share for supplier reporting period. |
| income_taxes | double | 4097 | 2.94458 | Income tax expense. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| net_ppe | double | 12925 | 9.289405 | Net property, plant and equipment. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| goodwill | double | 57790 | 41.534603 | Goodwill. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| intangibles | double | 48840 | 35.102094 | Intangible assets. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |
| gross_profit | double | 10242 | 7.36109 | Gross profit. Accounting monetary scale/currency is not included in these tables; millions is plausible, not verified. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| fundamentals_quarterly.parquet | 139,137 | 33 | 17745404 | 1 |

## industry_returns_daily_2022_2024.parquet

Daily value/equal-weighted returns for 72 industry groups.

**Shape:** 54,216 rows × 6 columns across 1 file(s). Compressed bytes: 1,632,927.

**Row key:** date, gics_industry.

**Use:** Industry benchmarks and neutralization; constituent/weight timing needs verification.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| gics_industry | string | 0 | 0.0 | GICS industry code stored as string. |
| industry_vw_return | double | 0 | 0.0 | Daily value-weighted industry return per supplier. Constituent and weight timing not certified. |
| industry_ew_return | double | 0 | 0.0 | Daily equal-weighted industry return per supplier. |
| industry_constituent_count | double | 0 | 0.0 | Number of industry constituents, physically double. |
| industry_total_mcap | double | 0 | 0.0 | Industry aggregate market capitalization in supplier scale (unit unverified). |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| industry_returns_daily_2022_2024.parquet | 54,216 | 6 | 1632927 | 1 |

## intraday_nbbo_close_open_windows_monthly

Equity consolidated best-bid/offer quote events near open and close.

**Shape:** 553,094,031 rows × 11 columns across 36 file(s). Compressed bytes: 5,121,792,414.

**Row key:** date, sym_root, time_m is not guaranteed unique.

**Use:** Spread and top-of-book execution modelling within covered windows. No L2 depth.

**Verification:** All 36 footers; first January 2022 row group scanned (551,880 rows).

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | string | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| time_m | string | 0 | 0.0 | Equity event clock time string; sampled microsecond precision. Combine with date; source timezone and event-clock meaning need confirmation. |
| sym_root | string | 0 | 0.0 | Equity ticker/root associated with this record; resolve date-qualified instrument identity. |
| best_bid | double | 106903 | 0.019328 | Best bid price. EOD: end-of-day option quote; equity NBBO: quote-event top of book. No additional price levels. |
| best_bid_sz | int64 | 106903 | 0.019328 | Equity displayed best-bid size. Sample values appear share-denominated; verify upstream conversion before capacity modelling. |
| best_ask | double | 107011 | 0.019348 | Equity NBBO best ask price, not market depth. |
| best_ask_sz | int64 | 107011 | 0.019348 | Equity displayed best-ask size. Sample values appear share-denominated; verify upstream conversion before capacity modelling. |
| qu_cond | string | 0 | 0.0 | Equity quote-condition code; decode for firmness/eligibility. |
| natbbo_ind | string | 0 | 0.0 | National BBO indicator code; exact TAQ specification needed. |
| qu_source | string | 0 | 0.0 | Quote source/tape code; exact codebook required. |
| nbbo_qu_cond | string | 553094031 | 100.0 | NBBO condition field; entirely null across 553,094,031 rows; other quote-status columns must be used. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| intraday_nbbo_close_open_windows_monthly/2022_01.parquet | 14,878,369 | 11 | 142631961 | 21 |
| intraday_nbbo_close_open_windows_monthly/2022_02.parquet | 14,210,948 | 11 | 135842858 | 20 |
| intraday_nbbo_close_open_windows_monthly/2022_03.parquet | 15,279,113 | 11 | 146865049 | 23 |
| intraday_nbbo_close_open_windows_monthly/2022_04.parquet | 14,915,893 | 11 | 141753093 | 21 |
| intraday_nbbo_close_open_windows_monthly/2022_05.parquet | 16,600,476 | 11 | 158799120 | 22 |
| intraday_nbbo_close_open_windows_monthly/2022_06.parquet | 15,122,641 | 11 | 144710811 | 21 |
| intraday_nbbo_close_open_windows_monthly/2022_07.parquet | 14,288,694 | 11 | 134868323 | 20 |
| intraday_nbbo_close_open_windows_monthly/2022_08.parquet | 15,228,085 | 11 | 143302994 | 23 |
| intraday_nbbo_close_open_windows_monthly/2022_09.parquet | 17,454,996 | 11 | 162220867 | 21 |
| intraday_nbbo_close_open_windows_monthly/2022_10.parquet | 18,091,664 | 11 | 167553868 | 23 |
| intraday_nbbo_close_open_windows_monthly/2022_11.parquet | 15,929,096 | 11 | 147296928 | 21 |
| intraday_nbbo_close_open_windows_monthly/2022_12.parquet | 17,722,935 | 11 | 161125327 | 22 |
| intraday_nbbo_close_open_windows_monthly/2023_01.parquet | 18,137,036 | 11 | 164277091 | 20 |
| intraday_nbbo_close_open_windows_monthly/2023_02.parquet | 17,655,595 | 11 | 159943464 | 21 |
| intraday_nbbo_close_open_windows_monthly/2023_03.parquet | 21,561,813 | 11 | 193506188 | 27 |
| intraday_nbbo_close_open_windows_monthly/2023_04.parquet | 13,003,259 | 11 | 117641967 | 19 |
| intraday_nbbo_close_open_windows_monthly/2023_05.parquet | 15,098,211 | 11 | 136649607 | 22 |
| intraday_nbbo_close_open_windows_monthly/2023_06.parquet | 15,019,173 | 11 | 137575190 | 21 |
| intraday_nbbo_close_open_windows_monthly/2023_07.parquet | 14,466,449 | 11 | 131270602 | 20 |
| intraday_nbbo_close_open_windows_monthly/2023_08.parquet | 16,942,196 | 11 | 154670649 | 23 |
| intraday_nbbo_close_open_windows_monthly/2023_09.parquet | 14,114,562 | 11 | 128621601 | 20 |
| intraday_nbbo_close_open_windows_monthly/2023_10.parquet | 18,778,596 | 11 | 168744835 | 23 |
| intraday_nbbo_close_open_windows_monthly/2023_11.parquet | 15,374,316 | 11 | 138130873 | 21 |
| intraday_nbbo_close_open_windows_monthly/2023_12.parquet | 14,761,908 | 11 | 133289792 | 20 |
| intraday_nbbo_close_open_windows_monthly/2024_01.parquet | 15,409,207 | 11 | 140404890 | 21 |
| intraday_nbbo_close_open_windows_monthly/2024_02.parquet | 14,188,929 | 11 | 130990225 | 21 |
| intraday_nbbo_close_open_windows_monthly/2024_03.parquet | 14,721,235 | 11 | 134743109 | 20 |
| intraday_nbbo_close_open_windows_monthly/2024_04.parquet | 16,406,238 | 11 | 150452283 | 22 |
| intraday_nbbo_close_open_windows_monthly/2024_05.parquet | 13,066,815 | 11 | 121612094 | 22 |
| intraday_nbbo_close_open_windows_monthly/2024_06.parquet | 11,320,334 | 11 | 107398627 | 19 |
| intraday_nbbo_close_open_windows_monthly/2024_07.parquet | 14,249,848 | 11 | 135131559 | 22 |
| intraday_nbbo_close_open_windows_monthly/2024_08.parquet | 15,350,957 | 11 | 144704227 | 23 |
| intraday_nbbo_close_open_windows_monthly/2024_09.parquet | 13,196,140 | 11 | 123831308 | 20 |
| intraday_nbbo_close_open_windows_monthly/2024_10.parquet | 15,331,425 | 11 | 143447454 | 23 |
| intraday_nbbo_close_open_windows_monthly/2024_11.parquet | 13,061,729 | 11 | 122312619 | 20 |
| intraday_nbbo_close_open_windows_monthly/2024_12.parquet | 12,155,150 | 11 | 115470961 | 21 |

## macro_daily_2022_2024.parquet

Mixed-frequency macro/credit/volatility observations.

**Shape:** 798 rows × 10 columns across 1 file(s). Compressed bytes: 22,554.

**Row key:** date.

**Use:** Credit and macro conditioning after source/release repair; CPI/PMI fields quarantined.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| hy_spread_oas | double | 394 | 49.373434 | High-yield option-adjusted credit spread; non-null from 2023-06-19. Unit and vintage confirmation required. |
| ig_spread_oas | double | 395 | 49.498747 | Investment-grade option-adjusted credit spread; non-null from 2023-06-19. Unit and vintage confirmation required. |
| cpi_yoy | double | 762 | 95.488722 | MISLABELLED/UNVERIFIED: observed 282.543–317.604, consistent with index levels, not YoY percent. 36 month-start observations; quarantine until source series and releases verified. |
| unemployment_rate | double | 762 | 95.488722 | Monthly unemployment-rate-like values, 36 month-start observations. Release dates/vintages absent; not established point-in-time. |
| industrial_production | double | 762 | 95.488722 | Monthly industrial-production-like index, 36 month-start observations. Exact series, release dates and revisions unverified. |
| ism_pmi | double | 762 | 95.488722 | MISLABELLED/UNVERIFIED: observed 12,564–12,903; cannot treat as conventional PMI. 36 month-start observations; quarantine pending series identity. |
| vix9d | double | 45 | 5.639098 | Daily short-horizon volatility index level; 753 non-null dates. End-of-day availability must be respected. |
| baa_10y_spread | double | 50 | 6.265664 | BAA minus 10-year Treasury spread; 748 non-null observations. Unit/vintage confirmation required. |
| aaa_10y_spread | double | 50 | 6.265664 | AAA minus 10-year Treasury spread; 748 non-null observations. Unit/vintage confirmation required. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| macro_daily_2022_2024.parquet | 798 | 10 | 22554 | 1 |

## market_overlays_2022_2024.parquet

Daily volatility indices, Treasury yields and S&P cash index.

**Shape:** 782 rows × 11 columns across 1 file(s). Compressed bytes: 40,261.

**Row key:** date.

**Use:** Risk context/discount-curve inputs, with yield-unit and availability checks.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| vix_1m | double | 10 | 1.278772 | Daily VIX one-month index level, index points. |
| vix_3m | double | 29 | 3.70844 | Daily three-month volatility index level, index points. |
| treasury_1mo | double | 33 | 4.219949 | 1mo Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_3mo | double | 33 | 4.219949 | 3mo Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_6mo | double | 33 | 4.219949 | 6mo Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_1y | double | 33 | 4.219949 | 1y Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_2y | double | 33 | 4.219949 | 2y Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_5y | double | 33 | 4.219949 | 5y Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| treasury_10y | double | 33 | 4.219949 | 10y Treasury yield, annual percentage-point-like quote (e.g. 0.05), not a daily return. Confirm units and curve convention before discounting. |
| sp500_cash_level | double | 29 | 3.70844 | S&P 500 cash-index daily level; not executable asset price or AM settlement series. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| market_overlays_2022_2024.parquet | 782 | 11 | 40261 | 1 |

## option_trades_with_greeks_quarterly

Intraday option executions with attached model Greeks and underlying reference.

**Shape:** 2,258,715,280 rows × 16 columns across 12 file(s). Compressed bytes: 57,512,447,092.

**Row key:** No unique trade ID supplied; candidate contract + trade time + venue + price + size.

**Use:** Options volume/VWAP and trade-associated risk analysis; no bid/ask, no gamma.

**Verification:** All 12 footers; first 2022Q1 row group scanned (1,048,576 rows).

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| symbol | string | 0 | 0.0 | In EOD chains: encoded option contract symbol. In Greeks tape: underlying/root ticker, not a complete contract identifier. |
| expiration | string | 0 | 0.0 | Contract expiration: ISO string in Greeks, YYYYMMDD integer in NBBO, timestamp in forwards. |
| strike | double | 0 | 0.0 | Greeks tape: dollar strike (double). NBBO tape: integer strike scaled by 1,000. |
| right | string | 0 | 0.0 | Call/put: CALL/PUT in Greeks; C/P in NBBO. Normalize explicitly. |
| timestamp | timestamp[ns] | 5057516 | 0.223911 | Option trade timestamp, timezone-naive timestamp[ns]; sampled precision is milliseconds. 5,057,516 nulls across Greeks tape. |
| size | int64 | 0 | 0.0 | Executed trade quantity; options conventionally contracts, equities shares. Validate corrections and units before VWAP. |
| exchange | int64 | 0 | 0.0 | Numeric option trade venue code; not an equity exchange code. Mapping not supplied. |
| price | double | 0 | 0.0 | Executed trade price; premium per quoted unit for options, share price for equities. Not a guaranteed hypothetical fill. |
| delta | double | 0 | 0.0 | Option sensitivity to underlying price. Model, units, timestamp and exercise convention must be established. |
| theta | double | 0 | 0.0 | Option time-decay sensitivity; per-day/per-year and pricing convention must be confirmed. |
| vega | double | 0 | 0.0 | Option sensitivity to volatility; dollar/percentage-point scaling must be confirmed before aggregation across sources. |
| rho | double | 0 | 0.0 | Intraday option sensitivity to interest rates; rate-unit scaling requires confirmation. |
| implied_vol | double | 0 | 0.0 | Trade-associated model implied volatility, typically annualized decimal. Zero and extreme values observed; maximum 214748.3646. |
| underlying_timestamp | timestamp[ns] | 0 | 0.0 | Underlying reference timestamp, stored without timezone; distinct from option trade time. Use to evaluate reference staleness. |
| underlying_price | double | 0 | 0.0 | Underlying reference price attached to model calculation; not executable underlying bid/ask. |
| trading_date | string | 0 | 0.0 | Greeks tape trading-date ISO string; cannot replace a missing intraday trade time. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| option_trades_with_greeks_quarterly/2022Q1.parquet | 153,866,305 | 16 | 4237304165 | 155 |
| option_trades_with_greeks_quarterly/2022Q2.parquet | 160,037,912 | 16 | 4368460799 | 161 |
| option_trades_with_greeks_quarterly/2022Q3.parquet | 173,496,381 | 16 | 4547750910 | 174 |
| option_trades_with_greeks_quarterly/2022Q4.parquet | 179,616,490 | 16 | 4591713852 | 181 |
| option_trades_with_greeks_quarterly/2023Q1.parquet | 191,578,242 | 16 | 4808931899 | 193 |
| option_trades_with_greeks_quarterly/2023Q2.parquet | 179,131,126 | 16 | 4430132767 | 180 |
| option_trades_with_greeks_quarterly/2023Q3.parquet | 188,049,697 | 16 | 4705284921 | 189 |
| option_trades_with_greeks_quarterly/2023Q4.parquet | 182,397,026 | 16 | 4538024372 | 183 |
| option_trades_with_greeks_quarterly/2024Q1.parquet | 195,883,606 | 16 | 4924927405 | 197 |
| option_trades_with_greeks_quarterly/2024Q2.parquet | 202,808,941 | 16 | 5095687726 | 204 |
| option_trades_with_greeks_quarterly/2024Q3.parquet | 228,999,658 | 16 | 5747971165 | 230 |
| option_trades_with_greeks_quarterly/2024Q4.parquet | 222,849,896 | 16 | 5516257111 | 224 |

## option_trades_with_nbbo_quarterly

Intraday option executions with attached prevailing NBBO prices and sizes.

**Shape:** 1,808,163,203 rows × 13 columns across 12 file(s). Compressed bytes: 22,472,218,183.

**Row key:** No unique trade ID supplied; candidate root, expiry, strike, right, date, ms_of_day, exchange, price, size.

**Use:** Strongest available option spread/slippage dataset, at observed trade times only. No quote-event tape or L2.

**Verification:** All 12 footers; first 2022Q1 row group scanned (1,048,576 rows).

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| root | string | 0 | 0.0 | NBBO tape: underlying option root. EOD chain: entirely null placeholder. |
| expiration | int64 | 0 | 0.0 | Contract expiration: ISO string in Greeks, YYYYMMDD integer in NBBO, timestamp in forwards. |
| strike | int64 | 0 | 0.0 | Greeks tape: dollar strike (double). NBBO tape: integer strike scaled by 1,000. |
| right | string | 0 | 0.0 | Call/put: CALL/PUT in Greeks; C/P in NBBO. Normalize explicitly. |
| ms_of_day | int64 | 0 | 0.0 | Option trade milliseconds since midnight: reconstruct with date after confirming clock timezone. Values cover almost the full 24-hour day. |
| size | int64 | 0 | 0.0 | Executed trade quantity; options conventionally contracts, equities shares. Validate corrections and units before VWAP. |
| exchange | int64 | 0 | 0.0 | Numeric option trade venue code; not an equity exchange code. Mapping not supplied. |
| price | double | 0 | 0.0 | Executed trade price; premium per quoted unit for options, share price for equities. Not a guaranteed hypothetical fill. |
| bid_size | int64 | 0 | 0.0 | Displayed option NBBO bid size; conventionally contracts, but supplier unit confirmation is required. |
| bid | double | 0 | 0.0 | Option NBBO best bid attached to trade; separate quote timestamp is absent. |
| ask_size | int64 | 0 | 0.0 | Displayed option NBBO ask size; conventionally contracts, but supplier unit confirmation is required. |
| ask | double | 0 | 0.0 | Option NBBO best ask attached to trade; separate quote timestamp is absent. |
| date | int64 | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| option_trades_with_nbbo_quarterly/2022Q1.parquet | 134,827,458 | 13 | 1756165786 | 136 |
| option_trades_with_nbbo_quarterly/2022Q2.parquet | 132,882,399 | 13 | 1740874254 | 133 |
| option_trades_with_nbbo_quarterly/2022Q3.parquet | 140,823,310 | 13 | 1797925379 | 142 |
| option_trades_with_nbbo_quarterly/2022Q4.parquet | 143,316,655 | 13 | 1803975377 | 144 |
| option_trades_with_nbbo_quarterly/2023Q1.parquet | 131,226,494 | 13 | 1636031436 | 132 |
| option_trades_with_nbbo_quarterly/2023Q2.parquet | 141,871,676 | 13 | 1735586577 | 142 |
| option_trades_with_nbbo_quarterly/2023Q3.parquet | 162,059,643 | 13 | 2017160308 | 163 |
| option_trades_with_nbbo_quarterly/2023Q4.parquet | 153,941,290 | 13 | 1896530725 | 155 |
| option_trades_with_nbbo_quarterly/2024Q1.parquet | 171,363,553 | 13 | 2111158448 | 173 |
| option_trades_with_nbbo_quarterly/2024Q2.parquet | 170,880,541 | 13 | 2071736582 | 172 |
| option_trades_with_nbbo_quarterly/2024Q3.parquet | 160,342,131 | 13 | 1940301709 | 161 |
| option_trades_with_nbbo_quarterly/2024Q4.parquet | 164,628,053 | 13 | 1964771602 | 166 |

## sector_classification.parquet

Equity/company linkage and classification reference.

**Shape:** 1,996 rows × 13 columns across 1 file(s). Compressed bytes: 99,270.

**Row key:** security_id (1,996 distinct, one row each).

**Use:** Company joins and classifications; no demonstrated GICS history/vintage timeline.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| security_id | double | 0 | 0.0 | Permanent equity security identifier; join with effective dates, never a ticker alone. |
| company_id | string | 0 | 0.0 | Company identifier stored as a zero-padded string; preserve leading zeros. |
| link_start | string | 0 | 0.0 | Start of equity-to-company linkage interval; not proof of historically versioned GICS. |
| link_end | string | 760 | 38.076152 | End of equity-to-company linkage interval; handle open-ended values per source. |
| gics_sector | string | 203 | 10.170341 | GICS sector code stored as string. |
| gics_industry_group | string | 203 | 10.170341 | GICS industry-group code stored as string. |
| gics_industry | string | 203 | 10.170341 | GICS industry code stored as string. |
| gics_subindustry | string | 203 | 10.170341 | GICS subindustry code stored as string. |
| company_long_name | string | 0 | 0.0 | Company long name from classification reference table. |
| sic_code | string | 0 | 0.0 | SIC code from classification reference; preserve as text. |
| naics_code | string | 162 | 8.116232 | NAICS code stored as text; missing values present. |
| ipo_date | string | 1226 | 61.422846 | IPO date if supplied; nullable. |
| hq_country | string | 0 | 0.0 | Headquarters country code; does not imply listing or EPS currency. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| sector_classification.parquet | 1,996 | 13 | 99270 | 1 |

## sector_returns_daily_2022_2024.parquet

Daily value/equal-weighted returns for 11 GICS sectors.

**Shape:** 8,283 rows × 6 columns across 1 file(s). Compressed bytes: 256,648.

**Row key:** date, gics_sector.

**Use:** Sector benchmarks and neutralization; not an execution dataset.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| date | timestamp[ns] | 0 | 0.0 | Observation/trading date; stored as timestamp, ISO date string, or YYYYMMDD integer depending on table. Not an availability timestamp. |
| gics_sector | string | 0 | 0.0 | GICS sector code stored as string. |
| sector_vw_return | double | 0 | 0.0 | Daily value-weighted sector return per supplier. Constituent and weight timing not certified. |
| sector_ew_return | double | 0 | 0.0 | Daily equal-weighted sector return per supplier. |
| sector_constituent_count | double | 0 | 0.0 | Number of sector constituents, physically double. |
| sector_total_mcap | double | 0 | 0.0 | Sector aggregate market capitalization in supplier scale (unit unverified). |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| sector_returns_daily_2022_2024.parquet | 8,283 | 6 | 256648 | 1 |

## sp500_membership_2022_2024.parquet

S&P 500 membership intervals intersecting supplied sample.

**Shape:** 557 rows × 7 columns across 1 file(s). Compressed bytes: 23,677.

**Row key:** security_id (one row per ID observed).

**Use:** Historical universe filter; missing ticker labels and interval-boundary semantics need handling.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| security_id | int64 | 0 | 0.0 | Permanent equity security identifier; join with effective dates, never a ticker alone. |
| in_date | string | 0 | 0.0 | S&P 500 membership interval start; can predate sample window. |
| out_date | string | 0 | 0.0 | Membership interval end, potentially censored at sample end; confirm inclusivity. |
| ticker | string | 60 | 10.771993 | Ticker label; must resolve to a security for the observation date. META collision confirmed. |
| company_name_pit | string | 12 | 2.154399 | Issuer name labelled point-in-time by supplier. Equity META rows demonstrate distinct issuers. |
| share_class_code | int64 | 12 | 2.154399 | Supplier share/security class code; no local decoder supplied. |
| exchange_code | int64 | 12 | 2.154399 | Supplier listing exchange code; not interchangeable with intraday venue codes. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| sp500_membership_2022_2024.parquet | 557 | 7 | 23677 | 1 |

## ticker_security_mapping.parquet

Effective-dated ticker/name/security history.

**Shape:** 8,391 rows × 9 columns across 1 file(s). Compressed bytes: 172,481.

**Row key:** Candidate security_id, ticker, name_in_date, name_out_date.

**Use:** Mandatory date-qualified identity resolution; ticker reuse observed.

**Verification:** Full scan.

| Column | Physical type | Nulls | Null % | Meaning / units |
| --- | --- | --- | --- | --- |
| security_id | int64 | 0 | 0.0 | Permanent equity security identifier; join with effective dates, never a ticker alone. |
| ticker | string | 0 | 0.0 | Ticker label; must resolve to a security for the observation date. META collision confirmed. |
| company_name | string | 0 | 0.0 | Issuer/company name label; not an instrument key. |
| name_in_date | string | 0 | 0.0 | Effective start of ticker/name record. |
| name_out_date | string | 0 | 0.0 | Effective end of ticker/name record; confirm inclusive/exclusive convention. |
| share_class_code | int64 | 0 | 0.0 | Supplier share/security class code; no local decoder supplied. |
| exchange_code | int64 | 0 | 0.0 | Supplier listing exchange code; not interchangeable with intraday venue codes. |
| industry_code | int64 | 0 | 0.0 | Supplier industry code in ticker-history table; do not assume GICS. |
| naics_code | string | 4425 | 52.735073 | NAICS code stored as text; missing values present. |

**Physical files**

| Path | Rows | Columns | Bytes | Row groups |
| --- | --- | --- | --- | --- |
| ticker_security_mapping.parquet | 8,391 | 9 | 172481 | 1 |
