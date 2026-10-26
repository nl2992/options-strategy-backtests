#!/bin/zsh
# usage: W3_END=20231231 ./build_and_run.sh   (dev; the test run uses W3_END=20241231 only after the freeze commit)
set -e
cd "$(dirname $0)"
export RES_DIR="$PWD/../results"; mkdir -p "$RES_DIR"
for f in s_events s3_flow s5_spxw_vix s6_straddle_gs s7_pin s_calendar; do
  clang++ -std=c++20 -O2 -Wall -Wno-unused-function -o bin_$f "$PWD/$f.cpp"
done
for f in s_events s3_flow s5_spxw_vix s6_straddle_gs s7_pin s_calendar; do ./bin_$f & done; wait
