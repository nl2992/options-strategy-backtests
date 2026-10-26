// Shared plumbing for the strategy engines: CSV loading, the session calendar and the daily ledger.
// Dates are yyyymmdd integers.
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
static const fs::path EXD = fs::path(__FILE__).parent_path().parent_path() / "data" / "extracts";
// RES_DIR overrides the output directory (default: <repo>/results)
static const fs::path RES = std::getenv("RES_DIR") ? fs::path(std::getenv("RES_DIR")) : fs::path(__FILE__).parent_path().parent_path() / "results";
constexpr double E0 = 1e6;

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

// ---------- stock commission used by the earlier option-flow engine ----------
constexpr double FEE_SH = 0.0035;

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
