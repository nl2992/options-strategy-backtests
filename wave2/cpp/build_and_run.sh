#!/bin/zsh
# compile every engine and run them all (results -> wave2/results/*.csv)
set -e
cd "$(dirname $0)"
for f in f2_putwrite h1_0dte h2_overnight h3_overnight_eq h4_info h5_earnings h6_eodmom; do
  clang++ -std=c++17 -O2 -Wall -Wno-unused-function -o bin_$f "$PWD/$f.cpp"
done
for f in f2_putwrite h1_0dte h2_overnight h3_overnight_eq h4_info h5_earnings h6_eodmom; do ./bin_$f & done; wait
