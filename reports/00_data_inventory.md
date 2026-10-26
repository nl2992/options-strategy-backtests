# Phase A — Data inventory

Generated: 2026-10-15
Source: Dropbox shared folder `Data_to_share` supplied by the user.

## Scope and status

This is the first forensic pass over the supplied dataset. The small context files, option-contract mapping, and annual EOD option-chain files have been registered in `data/raw/` and inspected with DuckDB. The project uses hard links to the completed downloads in `Downloads`, avoiding an additional 2.4 GB copy. The complete Dropbox archive remains unnecessary for this EOD stage because it also contains intraday and quarterly trade data.

No strategy results, trades, fills, returns, or performance claims have been produced.

## Verified local files

All files below are valid Parquet files and were read successfully with DuckDB. Counts and ranges are computed from the local copies.

| File | Rows | Date / period range | Notes |
|---|---:|---|---|
| `data/raw/eod_option_chain/_ticker_id_mapping.parquet` | 20 | n/a | 20 ticker rows; 19 distinct option security IDs because SPX and SPXW share 108105 |
| `data/raw/eod_option_chain/eod_option_chain_2022.parquet` | 18,239,871 | schema verified | 18 row groups; Parquet signature and metadata verified |
| `data/raw/eod_option_chain/eod_option_chain_2023.parquet` | 17,479,400 | schema verified | 17 row groups; Parquet signature and metadata verified |
| `data/raw/eod_option_chain/eod_option_chain_2024.parquet` | 21,881,360 | schema verified | 21 row groups; Parquet signature and metadata verified |
| `data/raw/context/dspx_dispersion_index_2022_2024.parquet` | 753 | 2022-01-03 to 2024-12-31 | Daily DSPX close |
| `data/raw/context/earnings_actuals_2022_2024.parquet` | 66,713 | 1997-06-30 to 2024-11-30 | Contains historical periods outside the main 2022–2024 study window |
| `data/raw/context/equity_daily_2022_2024.parquet` | 13,464 | 2022-01-03 to 2024-12-31 | 18 tickers; raw and adjusted prices, quotes, volume, identifiers |
| `data/raw/context/factor_returns_daily_2022_2024.parquet` | 753 | 2022-01-03 to 2024-12-31 | Daily factor and risk-free fields |
| `data/raw/context/fundamentals_daily_2022_2024.parquet` | 12,801 | 2022-01-03 to 2024-12-31 | Point-in-time daily panel; many fields are null on the first observed row |
| `data/raw/context/fundamentals_quarterly.parquet` | 139,137 | 1990-01-31 to 2026-05-31 | Broader historical file; must be date-filtered to avoid look-ahead |
| `data/raw/context/industry_returns_daily_2022_2024.parquet` | 54,216 | 2022-01-03 to 2024-12-31 | Industry daily returns and aggregate fields |
| `data/raw/context/macro_daily_2022_2024.parquet` | 798 | 2022-01-01 to 2024-12-31 | Calendar-dated macro panel; not every row is a trading day |
| `data/raw/context/market_overlays_2022_2024.parquet` | 782 | 2022-01-03 to 2024-12-31 | VIX, Treasury, and S&P 500 overlay fields |

## Source-folder inventory observed through the shared link

The folder contains these option-data directories: `auction_volume_summary_monthly`, `auction_window_trades_monthly`, `eod_option_chain`, `intraday_nbbo_close_open_windows_monthly`, `option_trades_with_greeks_quarterly`, and `option_trades_with_nbbo_quarterly`.

The `eod_option_chain` directory contains `_ticker_id_mapping.parquet`, `eod_option_chain_2022.parquet`, `eod_option_chain_2023.parquet`, `eod_option_chain_2024.parquet`, and `forward_prices_2022.parquet` through `forward_prices_2024.parquet`. Dropbox displayed the three annual chains at approximately 719 MB, 680 MB, and 860 MB respectively.

The remaining top-level Parquet files are the context files listed above, plus the source `_data_dictionary.md`, copied to the workspace as `data_dictionary.md`.

## Initial feasibility assessment

The supplied folder is sufficient to begin a point-in-time EOD options research pipeline. The context panel and the 57,600,631-row EOD chain are locally usable for universe, market, factor, macro, earnings, and fundamentals joins. The forward-price support files still need staging and reconciliation. Intraday and execution-specific strategy questions remain conditional on downloading and inspecting their corresponding monthly/quarterly files.

## Tooling note

DuckDB successfully reads the downloaded Parquet files. The system PyArrow import currently fails because its binary was compiled against NumPy 1.x while the environment has NumPy 2.0.2. This is recorded in `reports/00_quality_issues.csv`; it does not invalidate the Parquet files or prevent the initial inventory.
