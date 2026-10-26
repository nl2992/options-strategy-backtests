// Shared plumbing for the wave-2 engines: CSV loading, sessions, T2 quotes/fills, Black-Scholes, account ledger.
// Conventions follow wave2/prereg/PREREGISTRATION.md. Dates are yyyymmdd ints, times are ms after midnight ET.
#pragma once
#include <algorithm>
#include <array>
#include <set>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;
static const fs::path EXD = fs::path(__FILE__).parent_path().parent_path() / "extracts";
// RES_DIR env override lets later waves reuse these loaders (default unchanged)
static const fs::path RES = std::getenv("RES_DIR") ? fs::path(std::getenv("RES_DIR")) : fs::path(__FILE__).parent_path().parent_path() / "results";
constexpr double E0 = 1e6;
constexpr int A_MS = 10000;  // max quote age after arrival (enforced at extraction)

// ---------- CSV ----------
struct Table {
  std::vector<std::string> cols;
  std::vector<std::vector<std::string>> rows;
  int c(const std::string& n) const {
    auto it = std::find(cols.begin(), cols.end(), n);
    if (it == cols.end()) throw std::runtime_error("missing column " + n);
    return int(it - cols.begin());
  }
};
inline std::vector<std::string> split(const std::string& s) {
  std::vector<std::string> v; std::string x; std::stringstream q(s);
  while (std::getline(q, x, ',')) v.push_back(x);
  if (!s.empty() && s.back() == ',') v.push_back("");
  return v;
}
inline double num(const std::string& s) { return s.empty() ? NAN : std::stod(s); }
// all files in extracts/ whose name starts with prefix, concatenated in name order
inline Table load(const std::string& prefix) {
  std::vector<fs::path> fsv;
  for (auto& e : fs::directory_iterator(EXD))
    if (e.path().filename().string().rfind(prefix, 0) == 0 && e.path().extension() == ".csv") fsv.push_back(e.path());
  std::sort(fsv.begin(), fsv.end());
  if (fsv.empty()) throw std::runtime_error("no extract " + prefix);
  Table t; std::string line;
  for (auto& p : fsv) {
    std::ifstream f(p); std::getline(f, line);
    if (t.cols.empty()) t.cols = split(line);
    while (std::getline(f, line)) t.rows.push_back(split(line));
  }
  std::cerr << prefix << ": " << t.rows.size() << " rows from " << fsv.size() << " files\n";
  return t;
}

// ---------- sessions ----------
struct Sessions {
  std::vector<int> d; std::vector<double> rf, spx; std::unordered_map<int, int> idx;
  Sessions() {
    auto t = load("ctx_sessions");
    for (auto& r : t.rows) { idx[std::stoi(r[0])] = int(d.size()); d.push_back(std::stoi(r[0])); rf.push_back(num(r[1])); spx.push_back(num(r[2])); }
  }
  int i(int date) const { auto it = idx.find(date); return it == idx.end() ? -1 : it->second; }
};
inline int weekday(int ymd) {  // 0=Mon..6=Sun (Sakamoto)
  int y = ymd / 10000, m = ymd / 100 % 100, dd = ymd % 100; static int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  if (m < 3) y -= 1;
  return ((y + y / 4 - y / 100 + y / 400 + t[m - 1] + dd) % 7 + 6) % 7;
}
inline long days_between(int a, int b) {  // calendar days b-a
  auto jd = [](int ymd) { int y = ymd / 10000, m = ymd / 100 % 100, d = ymd % 100; int a = (14 - m) / 12, yy = y + 4800 - a, mm = m + 12 * a - 3;
    return long(d + (153 * mm + 2) / 5 + 365 * yy + yy / 4 - yy / 100 + yy / 400 - 32045); };
  return jd(b) - jd(a);
}

// ---------- quote snapshots (lat=-1: last quote before tau; lat>=0: first quote in [tau+lat, tau+lat+A]) ----------
struct Q { std::string root; int exp = 0; double k = 0; char cp = 0; double bid = 0, ask = 0; int bsz = 0, asz = 0; long ms = 0;
  double mid() const { return (bid + ask) / 2; } };
using SnapKey = long long;
inline SnapKey skey(int date, long tau, int lat) { return (SnapKey(date) * 100000000LL + tau) * 100000LL + (lat + 1); }
struct Snaps {
  std::unordered_map<SnapKey, std::vector<Q>> by;
  explicit Snaps(const std::string& prefix, bool equity = false) {
    auto t = load(prefix);
    int ct = t.c("tau"), cl = t.c("lat"), cd = t.c("date"), cr = t.c(equity ? "sym" : "root"), cb = t.c("bid"), ca = t.c("ask"),
        cbs = t.c("bsz"), cas = t.c("asz"), cm = t.c("ms");
    int ce = equity ? -1 : t.c("exp"), ck = equity ? -1 : t.c("k"), cc = equity ? -1 : t.c("cp");
    for (auto& r : t.rows) {
      Q q; q.root = r[cr]; q.bid = num(r[cb]); q.ask = num(r[ca]); q.bsz = int(num(r[cbs])); q.asz = int(num(r[cas])); q.ms = long(num(r[cm]));
      if (!equity) { q.exp = std::stoi(r[ce]); q.k = num(r[ck]); q.cp = r[cc][0]; }
      by[skey(std::stoi(r[cd]), std::stol(r[ct]), std::stoi(r[cl]))].push_back(q);
    }
  }
  const std::vector<Q>* get(int date, long tau, int lat) const { auto it = by.find(skey(date, tau, lat)); return it == by.end() ? nullptr : &it->second; }
  const Q* find(int date, long tau, int lat, const std::string& root, int exp = 0, double k = 0, char cp = 0) const {
    auto v = get(date, tau, lat); if (!v) return nullptr;
    for (auto& q : *v) if (q.root == root && q.exp == exp && std::abs(q.k - k) < 1e-6 && q.cp == cp) return &q;
    return nullptr;
  }
};
// T2 marketable fill: buy at ask, sell at bid. Returns NAN when the quote is unusable.
inline double fill_px(const Q* q, int side) {
  if (!q || q->bid <= 0 || q->ask < q->bid) return NAN;
  return side > 0 ? q->ask : q->bid;
}
inline int disp(const Q* q, int side) { return side > 0 ? q->asz : q->bsz; }

// put-call parity forward at one expiry from mids: K* minimizing |C-P|, F = K* + C - P
struct Fwd { double F = NAN, K = NAN, straddle = NAN; };
inline Fwd forward(const std::vector<Q>& v, const std::string& root, int exp) {
  std::map<double, std::pair<const Q*, const Q*>> m;
  for (auto& q : v) if (q.root == root && q.exp == exp && q.bid > 0 && q.ask >= q.bid) (q.cp == 'C' ? m[q.k].first : m[q.k].second) = &q;
  Fwd f; double best = 1e18;
  for (auto& [k, cp] : m) if (cp.first && cp.second) {
    double d = std::abs(cp.first->mid() - cp.second->mid());
    if (d < best) { best = d; f.K = k; f.F = k + cp.first->mid() - cp.second->mid(); f.straddle = cp.first->mid() + cp.second->mid(); }
  }
  return f;
}

// ---------- fees ----------
inline double fee_opt(const std::string& root, double mult = 1) { return mult * (0.65 + ((root == "SPX" || root == "SPXW") ? 0.60 : 0.10)); }
constexpr double FEE_SH = 0.0035;

// ---------- Black-Scholes (European, no dividends; used only for hedge ratios and gamma sizing) ----------
inline double ncdf(double x) { return 0.5 * std::erfc(-x / std::sqrt(2.0)); }
inline double npdf(double x) { return std::exp(-0.5 * x * x) / std::sqrt(2 * M_PI); }
inline double bs(double S, double K, double T, double r, double v, char cp) {
  double d1 = (std::log(S / K) + (r + .5 * v * v) * T) / (v * std::sqrt(T)), d2 = d1 - v * std::sqrt(T);
  return cp == 'C' ? S * ncdf(d1) - K * std::exp(-r * T) * ncdf(d2) : K * std::exp(-r * T) * ncdf(-d2) - S * ncdf(-d1);
}
inline double bs_delta(double S, double K, double T, double r, double v, char cp) {
  double d1 = (std::log(S / K) + (r + .5 * v * v) * T) / (v * std::sqrt(T)); return cp == 'C' ? ncdf(d1) : ncdf(d1) - 1;
}
inline double bs_gamma(double S, double K, double T, double r, double v) {
  double d1 = (std::log(S / K) + (r + .5 * v * v) * T) / (v * std::sqrt(T)); return npdf(d1) / (S * v * std::sqrt(T));
}
inline double implied_vol(double px, double S, double K, double T, double r, char cp) {
  double lo = 1e-3, hi = 5;
  if (!(px > 0) || bs(S, K, T, r, lo, cp) > px || bs(S, K, T, r, hi, cp) < px) return NAN;
  for (int i = 0; i < 100; ++i) { double m = .5 * (lo + hi); (bs(S, K, T, r, m, cp) > px ? hi : lo) = m; }
  return .5 * (lo + hi);
}

// ---------- ledger: one account per variant; excess return = trading P&L / prior equity ----------
struct Ledger {
  std::map<std::string, std::map<int, double>> pnl;  // variant -> date -> $
  std::ofstream trades;
  explicit Ledger(const std::string& name, const std::string& header) {
    fs::create_directories(RES); trades.open(RES / (name + "_trades.csv")); trades << header << "\n"; this->name = name;
  }
  std::string name;
  void add(const std::string& v, int date, double x) { pnl[v][date] += x; }
  // writes date,variant,pnl,equity,ret for every session in [first,last] of the strategy's data coverage
  void write_daily(const Sessions& s, int first, int last) {
    std::ofstream f(RES / (name + "_daily.csv")); f << "date,variant,pnl,equity,ret\n";
    for (auto& [v, m] : pnl) {
      double E = E0;
      for (size_t i = 0; i < s.d.size(); ++i) {
        int d = s.d[i]; if (d < first || d > last) continue;
        double x = m.count(d) ? m.at(d) : 0.0, r = x / E;
        E = E * (1 + (std::isfinite(s.rf[i]) ? s.rf[i] : 0)) + x;
        f << d << "," << v << "," << x << "," << E << "," << r << "\n";
      }
    }
  }
};
