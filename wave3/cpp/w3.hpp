// Wave-3 shared pieces: realistic fees, W3_END guard, beta, and a mark-to-market stock book (see wave3/PREREGISTRATION.md).
#pragma once
#include "../../wave2/cpp/equity.hpp"

// ---------- realistic fees ----------
inline double opt_fee(const std::string& root) {  // per contract per side
  return 0.65 + ((root == "SPX" || root == "SPXW") ? 0.66 : 0.50) + 0.025 + 0.003;
}
inline double stock_fee(double shares, double px, bool auction) {  // shares signed: <0 = sell
  double a = std::abs(shares), f = a * (0.0035 + 0.0002 + (auction ? 0.0010 : 0.0030));
  if (shares < 0) f += 27.80e-6 * a * px + std::min(0.000166 * a, 8.30);
  return f;
}
constexpr double BORROW = 0.004;

// ---------- sample guard: simulate nothing after W3_END ----------
inline int w3_end() { auto e = std::getenv("W3_END"); return e ? std::atoi(e) : 20231231; }
inline void cut(Sessions& S) {
  int e = w3_end(); size_t n = 0; while (n < S.d.size() && S.d[n] <= e) ++n;
  S.d.resize(n); S.rf.resize(n); S.spx.resize(n);
  for (auto it = S.idx.begin(); it != S.idx.end();) it = it->first > e ? S.idx.erase(it) : std::next(it);  // S.i() must not see cut dates
  std::cerr << "W3_END=" << e << " sessions=" << n << "\n";
}

// ---------- daily close-to-close return (split/dividend adjusted) ----------
inline double cc_ret(const Equity& E, const std::string& s, int d0, int d1) {
  auto a = E.day.find({s, d0}), b = E.day.find({s, d1});
  if (a == E.day.end() || b == E.day.end()) return NAN;
  return E.ret(s, d0, a->second.close_raw, d1, b->second.close_raw);
}
// OLS beta of s on SPY over the 60 sessions ending at index i-1, clipped to [0.5, 2]
inline double beta60(const Equity& E, const Sessions& S, const std::string& s, size_t i) {
  double sx = 0, sy = 0, sxx = 0, sxy = 0; int n = 0;
  for (size_t j = i >= 61 ? i - 60 : 1; j < i; ++j) {
    double y = cc_ret(E, s, S.d[j - 1], S.d[j]), x = cc_ret(E, "SPY", S.d[j - 1], S.d[j]);
    if (!std::isfinite(x) || !std::isfinite(y)) continue;
    sx += x; sy += y; sxx += x * x; sxy += x * y; ++n;
  }
  if (n < 30) return 1;
  double b = (sxy - sx * sy / n) / (sxx - sx * sx / n);
  return std::clamp(b, 0.5, 2.0);
}

// ---------- stock book: trades at auction prices, marked to the official close every session ----------
// Trades are queued per (date, OPEN|CLOSE). P&L is booked into a Ledger variant by day.
enum When { OPEN = 0, CLOSE = 1 };
struct Book {
  const Equity& E; const Sessions& S; Ledger& L; std::string v;
  std::map<std::string, double> sh, ref;               // shares and last mark (in current-day share units)
  std::map<std::pair<int, int>, std::vector<std::pair<std::string, double>>> q;  // (date,when) -> (sym, delta shares)
  Book(const Equity& e, const Sessions& s, Ledger& l, std::string var) : E(e), S(s), L(l), v(std::move(var)) {}
  void order(int date, When w, const std::string& sym, double dsh) { if (dsh != 0) q[{date, w}].push_back({sym, dsh}); }
  // price for an order: closes fill at the official close; opens need the opening cross (else NAN = not filled)
  double px(const std::string& s, int d, When w) const {
    if (w == CLOSE) { auto it = E.day.find({s, d}); return it == E.day.end() ? NAN : it->second.close_raw; }
    auto c = E.get(E.open, s, d); return c ? c->px : NAN;
  }
  // run the whole sample; returns number of orders that could not be filled
  int run() {
    int unfilled = 0;
    for (size_t i = 0; i < S.d.size(); ++i) {
      int d = S.d[i]; double pnl = 0;
      // corporate actions at the start of the day
      if (i > 0) for (auto& [s, n] : sh) if (n != 0) {
        auto a = E.day.find({s, S.d[i - 1]}), b = E.day.find({s, d});
        if (a == E.day.end() || b == E.day.end()) continue;
        pnl += n * a->second.close_raw * b->second.div;                    // dividend on prior close
        double k = a->second.adj / b->second.adj; n *= k; ref[s] /= k;      // split
      }
      for (When w : {OPEN, CLOSE}) {
        auto it = q.find({d, w});
        if (it != q.end()) for (auto& [s, dsh] : it->second) {
          double p = px(s, d, w);
          if (!std::isfinite(p)) {
            if (w == OPEN) { q[{d, CLOSE}].push_back({s, dsh}); continue; }  // missed open -> same-day close
            ++unfilled; continue;
          }
          if (sh[s] != 0) pnl += sh[s] * (p - ref[s]);                      // mark existing position to the trade price
          ref[s] = p; sh[s] += dsh;
          pnl -= stock_fee(dsh, p, true);
        }
        if (w == CLOSE) for (auto& [s, n] : sh) if (n != 0) {               // mark to the official close
          double p = px(s, d, CLOSE); if (!std::isfinite(p)) continue;
          pnl += n * (p - ref[s]); ref[s] = p;
          if (n < 0) pnl -= -n * p * BORROW / 252;
        }
      }
      if (pnl != 0) L.add(v, d, pnl);
    }
    return unfilled;
  }
};
