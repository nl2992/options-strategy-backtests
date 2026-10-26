// S6: monthly ATM straddles, long top-3 / short bottom-3 by (RV21 - IV). EOD entry (T3), held to expiry,
// ITM legs exercised/assigned at the official close; delivered shares closed at the next opening cross (T1).
#include "w3.hpp"

struct Pos { std::string v, root; int exp, n, side; double k, last, prem, fees; int d_in; };  // side +1 long straddle, -1 short

int main() {
  Sessions S; cut(S); Equity E;
  std::unordered_map<std::string, std::pair<double, double>> q;  // root|date|exp|k|cp -> (bid,ask)
  std::map<int, std::map<std::string, std::vector<std::array<double, 5>>>> ch;  // date -> root -> {exp,k,cp(0=C),bid,ask}+iv in q2
  std::unordered_map<std::string, double> ivm;
  std::set<int> exps;
  auto key = [](const std::string& r, int d, int e, double k, char cp) { char b[80]; snprintf(b, sizeof b, "%s|%d|%d|%.3f|%c", r.c_str(), d, e, k, cp); return std::string(b); };
  { auto t = load("w3_single_eod");
    for (auto& r : t.rows) { int d = std::stoi(r[1]), e = std::stoi(r[2]); double k = num(r[3]); char cp = r[4][0];
      q[key(r[0], d, e, k, cp)] = {num(r[5]), num(r[6])}; ivm[key(r[0], d, e, k, cp)] = num(r[7]);
      ch[d][r[0]].push_back({double(e), k, cp == 'C' ? 0. : 1., num(r[5]), num(r[6])}); exps.insert(e); } }
  Ledger L("s6", "variant,root,d_in,exp,side,k,gap,rv21,iv,n,premium,fees,settle_px,delivered_sh,pnl,ret_on_premium,status");
  std::vector<Pos> open;
  std::map<int, std::vector<std::tuple<std::string, std::string, double, double>>> deliver;  // date -> (variant, root, shares, ref px)
  std::vector<int> ev(exps.begin(), exps.end());
  for (size_t i = 0; i < S.d.size(); ++i) {
    int d = S.d[i];
    // --- close delivered shares at this session's opening cross (or close) ---
    for (auto& [v, r, shs, ref] : deliver[d]) {
      auto c = E.get(E.open, r, d); double p = c ? c->px : E.day.count({r, d}) ? E.day.at({r, d}).close_raw : NAN;
      if (!std::isfinite(p)) continue;
      double k = E.day.count({r, S.d[i - 1]}) && E.day.count({r, d}) ? E.day.at({r, S.d[i - 1]}).adj / E.day.at({r, d}).adj : 1;
      L.add(v, d, shs * k * (p - ref / k) - stock_fee(-shs * k, p, true));
    }
    // --- mark / expire open straddles ---
    for (auto& p : open) {
      double V = 0, dsh = 0;
      if (d >= p.exp) {
        auto it = E.day.find({p.root, d}); double sp = it == E.day.end() ? NAN : it->second.close_raw;
        if (!std::isfinite(sp)) continue;
        double c = std::max(sp - p.k, 0.), u = std::max(p.k - sp, 0.);
        V = p.side * (c + u) * 100 * p.n;
        // exercise/assignment: long call ITM -> +shares, long put ITM -> -shares; short legs opposite
        dsh = p.side * 100 * p.n * ((sp > p.k) - (sp < p.k));
        // exercise converts the option value into shares bought/sold at K; the share mark-to-close is the same value
        if (dsh != 0) deliver[S.d[std::min(i + 1, S.d.size() - 1)]].push_back({p.v, p.root, dsh, sp});
        L.add(p.v, d, V - p.last); p.last = V;
        // realized option P&L at expiry (excludes the next-open share move, which is booked on delivery)
        double pnl = p.side * ((c + u) - p.prem) * 100 * p.n - p.fees;
        L.trades << p.v << "," << p.root << "," << p.d_in << "," << p.exp << "," << p.side << "," << p.k << ",,,," << p.n << "," << p.prem << "," << p.fees
                 << "," << sp << "," << dsh << "," << pnl << "," << pnl / (p.prem * 100 * p.n) << ",settled\n";
        p.exp = -1;  // flag closed
        continue;
      }
      bool ok = true;
      for (char cp : {'C', 'P'}) { auto it = q.find(key(p.root, d, p.exp, p.k, cp)); if (it == q.end()) { ok = false; break; } V += p.side * (it->second.first + it->second.second) / 2 * 100 * p.n; }
      if (ok) { L.add(p.v, d, V - p.last); p.last = V; }
    }
    open.erase(std::remove_if(open.begin(), open.end(), [](const Pos& p) { return p.exp < 0; }), open.end());
    // --- entry on monthly-expiry Fridays: next monthly expiry ---
    if (!std::count(ev.begin(), ev.end(), d) || i < 22) continue;
    auto nx = std::upper_bound(ev.begin(), ev.end(), d); if (nx == ev.end()) continue;
    int exp = *nx;
    // --- signal: RV21 (annualized, from adjusted closes) minus ATM IV of the next expiry ---
    std::vector<std::tuple<double, std::string, double, double, double>> g;  // gap, root, K, rv, iv
    for (auto& [r, rows] : ch[d]) {
      auto it = E.day.find({r, d}); if (it == E.day.end()) continue; double sp = it->second.close_raw;
      double K = NAN; for (auto& x : rows) if (int(x[0]) == exp && x[3] > 0 && (!std::isfinite(K) || std::abs(x[1] - sp) < std::abs(K - sp))) K = x[1];
      if (!std::isfinite(K)) continue;
      double ivc = ivm.count(key(r, d, exp, K, 'C')) ? ivm[key(r, d, exp, K, 'C')] : NAN, ivp = ivm.count(key(r, d, exp, K, 'P')) ? ivm[key(r, d, exp, K, 'P')] : NAN;
      double iv = (ivc + ivp) / 2; if (!std::isfinite(iv) || !q.count(key(r, d, exp, K, 'C')) || !q.count(key(r, d, exp, K, 'P'))) continue;
      double s2 = 0; int n = 0; for (size_t j = i - 20; j <= i; ++j) { double x = cc_ret(E, r, S.d[j - 1], S.d[j]); if (std::isfinite(x)) { s2 += std::log1p(x) * std::log1p(x); ++n; } }
      if (n < 15) continue;
      double rv = std::sqrt(s2 / n * 252);
      g.push_back({rv - iv, r, K, rv, iv});
    }
    if (g.size() < 6) continue;
    std::sort(g.begin(), g.end());
    for (std::string v : {"S6_ls", "S6_long_top3"}) for (int j = 0; j < 6; ++j) {
      bool top = j >= 3; auto& [gap, r, K, rv, iv] = g[top ? g.size() - 6 + j : j];
      int side = top ? 1 : -1; if (v == "S6_long_top3" && side < 0) continue;
      auto c = q[key(r, d, exp, K, 'C')], p = q[key(r, d, exp, K, 'P')];
      double prem = side > 0 ? c.second + p.second : c.first + p.first;  // buy ask / sell bid
      auto row = [&](const std::string& st, int n = 0, double fees = 0) {
        L.trades << v << "," << r << "," << d << "," << exp << "," << side << "," << K << "," << gap << "," << rv << "," << iv << "," << n << "," << prem << "," << fees << ",,,,," << st << "\n"; };
      if (!(prem > 0) || (side < 0 && (c.first <= 0 || p.first <= 0))) { row("bad_quote"); continue; }
      int n = int(0.02 * E0 / 3 / (prem * 100));
      if (n < 1) { row("size_lt1"); continue; }
      double fees = 2 * n * opt_fee(r), V0 = side * ((c.first + c.second) / 2 + (p.first + p.second) / 2) * 100 * n;
      L.add(v, d, -side * prem * 100 * n - fees + V0);  // cash paid/received + mark
      open.push_back({v, r, exp, n, side, K, V0, prem, fees, d});
      row("filled", n, fees);
    }
  }
  L.write_daily(S, S.d[22], S.d.back());
  std::cerr << "s6 done\n";
}
