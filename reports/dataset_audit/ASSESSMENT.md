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
