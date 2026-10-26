#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/reports/rolling_research"
BIN="$(mktemp -t options-audit-cpp.XXXXXX)"
trap 'rm -f "$BIN"' EXIT
"${CXX:-clang++}" -std=c++17 -O3 -Wall -Wextra -pedantic "$ROOT/cpp/audit_returns.cpp" -o "$BIN"
"$BIN" "$OUT/oos_daily_returns.csv" "$OUT"
