// Equity inputs: official auction crosses and daily corporate-action fields.
#pragma once
#include "common.hpp"

struct Cross { double px = NAN, sz = NAN; };
struct EqDay { double open_raw = NAN, close_raw = NAN, div = 0, adj = 1; };
struct Equity {
  std::map<std::pair<std::string, int>, Cross> open, close;  // (sym,date)
  std::map<std::pair<std::string, int>, EqDay> day;
  Equity() {
    auto d = load("ctx_equity");
    for (auto& r : d.rows) day[{r[1], std::stoi(r[0])}] = {num(r[2]), num(r[3]), std::isfinite(num(r[4])) ? num(r[4]) : 0, num(r[5])};
    auto a = load("auction_");
    for (auto& r : a.rows) {
      std::pair<std::string, int> k{r[0], std::stoi(r[1])}; Cross c{num(r[3]), num(r[4])};
      auto it = day.find(k);
      if (r[2] == "open") {  // data guard: an opening cross >2% from the day's first trade is a mis-tagged print
        if (it != day.end() && std::abs(c.px / it->second.open_raw - 1) < 0.02) open[k] = c;
      } else if (it != day.end() && std::abs(c.px / it->second.close_raw - 1) < 0.002) close[k] = c;
    }
  }
  const Cross* get(const std::map<std::pair<std::string, int>, Cross>& m, const std::string& s, int d) const {
    auto it = m.find({s, d}); return it == m.end() ? nullptr : &it->second;
  }
  // split/dividend-adjusted gross return from price a on date da to price b on date db (dividends of db credited)
  double ret(const std::string& s, int da, double a, int db, double b) const {
    auto x = day.find({s, da}), y = day.find({s, db});
    if (x == day.end() || y == day.end()) return NAN;
    return b * (x->second.adj / y->second.adj) / a - 1 + (da != db ? y->second.div : 0);
  }
};
