#!/bin/zsh
# Download the three end-of-day option-chain files (~2.4 GB) into data/raw/eod_option_chain/. Then run pipeline/normalize.py.
set -e
cd "$(dirname $0)/.."
mkdir -p data/raw/eod_option_chain
for y in 2022 2023 2024; do
  pipeline/fetch.sh eod_option_chain/eod_option_chain_$y.parquet
  mv data/raw/tapes/eod_option_chain/eod_option_chain_$y.parquet data/raw/eod_option_chain/
done
