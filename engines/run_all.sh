#!/bin/zsh
# Build and run the three engines; outputs go to <repo>/results (or $RES_DIR).
set -e
cd "$(dirname $0)"
for f in option_flow option_flow_v1 earnings_events; do
  clang++ -std=c++20 -O2 -Wall -Wno-unused-function -o bin_$f "$PWD/$f.cpp"
done
for f in option_flow option_flow_v1 earnings_events; do ./bin_$f & done; wait
