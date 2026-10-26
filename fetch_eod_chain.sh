#!/bin/zsh
# Download the three EOD option-chain files (about 2.4 GB) into data/raw/eod_option_chain/, verifying byte counts.
set -e
cd "$(dirname $0)"
mkdir -p data/raw/eod_option_chain
for y in 2022 2023 2024; do
  wave2/fetch.sh eod_option_chain/eod_option_chain_$y.parquet
  mv wave2/raw/eod_option_chain/eod_option_chain_$y.parquet data/raw/eod_option_chain/
done
