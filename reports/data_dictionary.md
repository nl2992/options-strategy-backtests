# Data_to_share — Consolidated 20-Ticker Dataset (2022–2024)

One folder covering **all data needed for the NMD, 0DTE Dealer-Gamma, and Volatility Dispersion strategies**.

**Universe (20 tickers):**
- **Index:** SPX, SPXW (weeklies)
- **ETFs:** SPY, QQQ
- **Single names (16):** AAPL, MSFT, NVDA, TSLA, GOOGL, AMZN, META, AVGO, NFLX, AMD, CRM, JPM, LLY, UNH, XOM, WMT

**Window:** 2022-01-01 → 2024-12-31 (753 trading days) unless noted.
All datasets are point-in-time and survivorship-bias-free. Currency USD.

---

## Folder layout

```
Data_to_share/
├── _data_dictionary.md                        ← you are here
├── equity_daily_2022_2024.parquet             ← daily OHLCV, 18 equity tickers
├── fundamentals_daily_2022_2024.parquet       ← quarterly fundamentals forward-filled daily (PIT)
├── fundamentals_quarterly.parquet             ← raw quarterly fundamentals (full history)
├── factor_returns_daily_2022_2024.parquet     ← market−rf, size, value, momentum, profitability, investment, rf
├── macro_daily_2022_2024.parquet              ← credit spreads, CPI, unemployment, IP, PMI, VIX9D
├── market_overlays_2022_2024.parquet          ← VIX 1m + 3m, Treasury curve 1m→10y, SP500 cash level
├── earnings_actuals_2022_2024.parquet         ← quarterly EPS announcements, 6,453 tickers
├── sector_classification.parquet              ← GICS sector/industry per security
├── sector_returns_daily_2022_2024.parquet     ← VW + EW daily returns per GICS sector
├── industry_returns_daily_2022_2024.parquet   ← same at industry granularity
├── ticker_security_mapping.parquet            ← effective-dated ticker history
├── sp500_membership_2022_2024.parquet         ← S&P 500 membership spans
├── dspx_dispersion_index_2022_2024.parquet    ← dispersion-index daily close (VDS benchmark)
├── eod_option_chain/                          ← EOD chains + forward prices, ALL 20 tickers
│   ├── eod_option_chain_2022|2023|2024.parquet
│   ├── forward_prices_2022|2023|2024.parquet
│   └── _ticker_id_mapping.parquet
├── option_trades_with_greeks_quarterly/       ← intraday option trades + Greeks, ALL 20 tickers
│   └── 2022Q1 … 2024Q4.parquet
├── option_trades_with_nbbo_quarterly/         ← intraday option trades + NBBO at trade time, ALL 20 tickers
│   └── 2022Q1 … 2024Q4.parquet
├── auction_window_trades_monthly/             ← MOC/MOO auction-window trades, all 18 equity tickers
│   └── 2022_01 … 2024_12.parquet
├── auction_volume_summary_monthly/            ← per-(ticker, date, side) cross size + VWAP
└── intraday_nbbo_close_open_windows_monthly/  ← equity NBBO in the 09:29–09:35 / 15:55–16:01 windows
```

---

## Core files

### `equity_daily_2022_2024.parquet` — 13,464 rows, 18 tickers

One row per (security_id, date). Raw + split/div-adjusted OHLCV, returns, point-in-time identifiers.

Key columns: `security_id`, `date`, `ticker`, `open_raw/high_raw/low_raw/close_raw`, `adj_open/adj_high/adj_low/adj_close` (divide raw by `price_adj_factor`), `bid_eod/ask_eod`, `volume_raw`, `adj_volume`, `dollar_volume`, `vwap_proxy` ((H+L+C)/3), `total_return`, `price_return_ex_div`, `shares_outstanding_k`, `close_is_quote_midpoint`, plus point-in-time SIC/NAICS/CUSIP.

**SPX note:** the cash index has no equity rows — use `sp500_cash_level` in `market_overlays_2022_2024.parquet`, or SPY as the tradeable proxy.

### `fundamentals_daily_2022_2024.parquet` / `fundamentals_quarterly.parquet`

Quarterly fundamentals (revenue, COGS, EPS, assets, debt, cash-flow, etc.) keyed on `company_id`; the daily file is a backward as-of join on the announcement date (`as_of_date ≤ date` always — PIT-safe). ETFs (SPY/QQQ) have no fundamentals rows.

### `factor_returns_daily_2022_2024.parquet` — 753 rows

Daily standard factor returns (decimals): `market_minus_rf`, `size_factor`, `value_factor`, `momentum_factor`, `profitability_factor`, `investment_factor`, `risk_free_rate_1m`.

### `macro_daily_2022_2024.parquet` — 798 rows

`hy_spread_oas`/`ig_spread_oas` (**2023-06-19 onward only** — source restricts earlier history; see below), `baa_10y_spread`/`aaa_10y_spread` (**full window** — use these for credit conditioning across all three years), `cpi_yoy`, `unemployment_rate`, `industrial_production`, `ism_pmi` (monthly release-dated), `vix9d` (753/753 trading days).

### `market_overlays_2022_2024.parquet` — 782 rows

`vix_1m`, `vix_3m`, Treasury constant-maturity yields (`treasury_1mo/3mo/6mo/1y/2y/5y/10y`), `sp500_cash_level`.

### `earnings_actuals_2022_2024.parquet` — 66,713 rows

Quarterly EPS announcements: `ticker`, `period_end`, `announce_date` (**use for PIT joins**), `announce_time`, `actual_eps`. Powers the earnings-exclusion overlay gates.

### Sector / classification / mapping files

- `sector_classification.parquet` — GICS sector/industry/sub-industry + SIC/NAICS per `security_id`, plus `company_id` for the fundamentals join.
- `sector_returns_daily` / `industry_returns_daily` — VW + EW daily returns per GICS group with constituent counts.
- `ticker_security_mapping.parquet` — effective-dated ticker↔security history (tickers get reused; always date-qualify reverse lookups).
- `sp500_membership_2022_2024.parquet` — membership spans (`in_date`/`out_date`) for universe filters.
- `dspx_dispersion_index_2022_2024.parquet` — 753 rows, dispersion-index daily close. VDS V5 benchmark.

---

## Option data

### `eod_option_chain/` — ALL 20 tickers ✅

One row per (option_security_id, date, contract). ~57.6M rows across three yearly files (~2.4 GB total).

26 columns incl.: `option_security_id`, `date`, `symbol`, `exdate`, `cp_flag`, `strike_price` (×1000 — divide by 1000), `best_bid/best_offer`, `volume`, `open_interest`, `impl_volatility`, `delta/gamma/vega/theta`, `am_settlement`, `forward_price`, `contract_size`, `cfadj`.

`forward_prices_<year>.parquet`: (option_security_id, date, expiration, amsettlement, forwardprice) — the canonical forward for Black-76 discounting. All 19 option-security IDs.

**SPX + SPXW share `option_security_id = 108105`.** Split by symbol prefix (`SPX ` vs `SPXW `) or `am_settlement` (1 = AM-settled monthly SPX, 0 = PM-settled SPXW weeklies). All other tickers map 1:1 — see `_ticker_id_mapping.parquet` (20 rows).

### Intraday option tapes — ALL 20 tickers ✅

`option_trades_with_greeks_quarterly/` — one row per option trade with first-order Greeks: `symbol`, `expiration`, `strike`, `right`, `timestamp`, `size`, `price`, `delta/theta/vega/rho`, `implied_vol`, `underlying_price`, `trading_date`. Gamma not included — recompute via Black-76 from `(F, K, T, σ)`. 12 quarterly files, **2.26B rows, 57.5 GB**.

`option_trades_with_nbbo_quarterly/` — one row per option trade with prevailing NBBO: `root`, `expiration`, `strike` (×1000), `right`, `ms_of_day`, `size`, `price`, `bid/ask` + sizes, `date` (YYYYMMDD int). For Lee-Ready sign inference. 12 quarterly files, **1.81B rows, 22.5 GB**.

**Coverage: all 20 universe tickers.** Approximate per-quarter volume ordering: SPY > SPXW > TSLA > QQQ > NVDA > AAPL > AMZN > AMD > META > MSFT > NFLX > GOOGL > SPX > JPM > XOM > CRM > AVGO > WMT > UNH > LLY.

---

## Auction / execution data — all 18 equity tickers

- `auction_window_trades_monthly/` — every trade in [09:29:55, 09:30:30] and [15:59:50, 16:00:30], with sale-condition codes. Opening cross carries condition `O`; closing cross carries condition `6`.
- `auction_volume_summary_monthly/` — desk-ready per-(date, ticker, side ∈ {MOO, MOC}) table: `total_size`, `num_prints`, `vwap_price`, first/last print times. Powers the participation-cap checks.
- `intraday_nbbo_close_open_windows_monthly/` — equity NBBO snapshots in [09:29, 09:35] and [15:55, 16:01] for half-spread / impact cost modeling.

36 monthly files each (2022_01 → 2024_12). SPX/SPXW have no equity auctions — use SPY as the execution proxy.

---

## Standard joins

| From → To | Join on |
|---|---|
| equity panel → fundamentals_daily | `(security_id, date)` |
| equity panel → fundamentals_quarterly | map `security_id → company_id` via `sector_classification`, then as-of on `announce_date` |
| equity panel → earnings_actuals | `(ticker, date)` vs `announce_date` (as-of / event window) |
| equity panel → factor / macro / overlays | `date` |
| equity panel → sector_returns | `(date, gics_sector)` via `sector_classification` |
| EOD chain → forwards | `(option_security_id, date, exdate↔expiration, am_settlement↔amsettlement)` |
| Greeks tape ↔ NBBO tape | `(symbol↔root, expiration, strike, right, timestamp↔ms_of_day)` — mind the ×1000 strike on the NBBO side |
| ticker → option_security_id | `eod_option_chain/_ticker_id_mapping.parquet` |

---

## Known gaps & caveats

1. **HY/IG OAS start 2023-06-19** (public source restricts the earlier window). Use `baa_10y_spread` / `aaa_10y_spread` for full-window credit conditioning.
2. **SPX cash index** is not in the equity panel — level lives in `market_overlays`; SPY is the tradeable proxy.
3. **ETFs (SPY/QQQ)** have no fundamentals or GICS classification rows.
4. **NBBO tape strike is integer ×1000** (e.g., `760000` = $760); the Greeks tape uses dollar strikes. Normalize at ingest.
5. **Trading calendar** is implicit in the equity panel's dates (753 days); no separate holiday/half-day table.
