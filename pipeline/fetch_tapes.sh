#!/bin/zsh
# Download the raw tapes the strategies use (option trades with quotes, ~22.5 GB; auction prints, ~1.0 GB)
# and reduce them to data/extracts/. Then run pipeline/build_inputs.py.
set -e
cd "$(dirname $0)/.."
for y in 2022 2023 2024; do for q in Q1 Q2 Q3 Q4; do
  pipeline/fetch.sh option_trades_with_nbbo_quarterly/$y$q.parquet && python pipeline/extract.py options $y$q
done; done
for y in 2022 2023 2024; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  pipeline/fetch.sh auction_window_trades_monthly/${y}_$m.parquet && python pipeline/extract.py auction ${y}_$m
done; done
