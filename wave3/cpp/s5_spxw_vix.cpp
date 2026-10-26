// S5: weekly SPXW iron fly (~28 DTE) sold at EOD (T3), held to PM settlement (T0), timed by the VIX term structure.
// Positions are marked to the EOD mid daily; realized on the SPX close at expiry.
#include "w3.hpp"

struct O { double bid, ask; double mid() const { return (bid + ask) / 2; } };
struct Leg { double k; char cp; int side; };

int main() {
  Sessions S; cut(S);
  std::map<int, std::vector<std::tuple<int, double, char, double, double>>> chain;  // date -> (exp,k,cp,bid,ask)
  std::unordered_map<std::string, O> q;  // "date|exp|k|cp" -> quote
  auto key = [](int d, int e, double k, char cp) { char b[64]; snprintf(b, sizeof b, "%d|%d|%.3f|%c", d, e, k, cp); return std::string(b); };
  { auto t = load("w3_spxw_eod");
    for (auto& r : t.rows) { int d = std::stoi(r[0]), e = std::stoi(r[1]); double k = num(r[2]); char cp = r[3][0];
      chain[d].push_back({e, k, cp, num(r[4]), num(r[5])}); q[key(d, e, k, cp)] = {num(r[4]), num(r[5])}; } }
  std::map<int, std::pair<double, double>> vix;
  { auto t = load("w3_vix"); for (auto& r : t.rows) vix[std::stoi(r[0])] = {num(r[1]), num(r[2])}; }
  Ledger L("s5", "variant,d_in,exp,k,wc,wp,straddle,credit,max_loss,n,fees,vix,vix3m,rv21,settle,pnl,ret_on_risk,status");
  struct Pos { std::string v; int exp; std::vector<Leg> legs; int n; double last; };
  std::vector<Pos> open;
  for (size_t i = 0; i < S.d.size(); ++i) {
    int d = S.d[i]; double spot = S.spx[i];
    // --- mark / settle open positions ---
    for (auto& p : open) {
      double V = 0; bool ok = true;
      for (auto& l : p.legs) {
        double x;
        if (d == p.exp) x = l.cp == 'C' ? std::max(spot - l.k, 0.) : std::max(l.k - spot, 0.);
        else { auto it = q.find(key(d, p.exp, l.k, l.cp)); if (it == q.end() || (it->second.bid <= 0 && it->second.ask <= 0)) { ok = false; break; } x = it->second.mid(); }
        V += l.side * x * 100 * p.n;
      }
      if (ok) { L.add(p.v, d, V - p.last); p.last = V; }  // missing quote: carry the last mark
    }
    open.erase(std::remove_if(open.begin(), open.end(), [&](const Pos& p) { return p.exp <= d; }), open.end());
    if (weekday(d) != 4 || !chain.count(d) || !std::isfinite(spot) || i < 22) continue;
    // --- signals known at today's close ---
    auto [vx, vx3] = vix.count(d) ? vix[d] : std::pair<double, double>{NAN, NAN};
    double s2 = 0; for (size_t j = i - 20; j <= i; ++j) { double r = std::log(S.spx[j] / S.spx[j - 1]); s2 += r * r; }
    double rv21 = 100 * std::sqrt(s2 / 21 * 252);
    // --- expiry: Friday with DTE in [26,30], else nearest to 28 within [21,35] ---
    int exp = 0; long best = 99;
    for (auto& [e, k, cp, b, a] : chain[d]) { long dte = days_between(d, e); if (dte >= 21 && dte <= 35 && std::abs(dte - 28) < best) { best = std::abs(dte - 28); exp = e; } }
    for (std::string v : {"S5_contango", "S5_uncond", "S5_vrp"}) {
      auto row = [&](const std::string& st, std::vector<double> x = {}) { x.resize(14, NAN);
        L.trades << v << "," << d << "," << exp; for (double y : x) L.trades << "," << y; L.trades << "," << st << "\n"; };
      bool on = v == "S5_uncond" || (v == "S5_contango" && vx3 > vx) || (v == "S5_vrp" && vx > rv21);
      if (!on) { row("filtered", {NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, vx, vx3, rv21}); continue; }
      if (!exp) { row("no_expiry"); continue; }
      // --- portfolio: ATM short straddle + wings at +-1.5 x straddle ---
      std::map<double, std::pair<const O*, const O*>> m;
      for (auto& [e, k, cp, b, a] : chain[d]) if (e == exp) { auto& o = q[key(d, e, k, cp)]; (cp == 'C' ? m[k].first : m[k].second) = &o; }
      double K = NAN; for (auto& [k, cpq] : m) if (cpq.first && cpq.second && cpq.first->bid > 0 && cpq.second->bid > 0 && (!std::isfinite(K) || std::abs(k - spot) < std::abs(K - spot))) K = k;
      if (!std::isfinite(K)) { row("no_atm"); continue; }
      double strad = m[K].first->mid() + m[K].second->mid(), wc = NAN, wp = NAN;
      for (auto& [k, cpq] : m) {
        if (cpq.first && k > K && cpq.first->ask > 0 && (!std::isfinite(wc) || std::abs(k - K - 1.5 * strad) < std::abs(wc - K - 1.5 * strad))) wc = k;
        if (cpq.second && k < K && cpq.second->ask > 0 && (!std::isfinite(wp) || std::abs(K - k - 1.5 * strad) < std::abs(K - wp - 1.5 * strad))) wp = k;
      }
      if (!std::isfinite(wc) || !std::isfinite(wp)) { row("no_wing"); continue; }
      // --- execution: sell shorts at bid, buy wings at ask (T3) ---
      double credit = m[K].first->bid + m[K].second->bid - m[wc].first->ask - m[wp].second->ask;
      double ml = std::max(wc - K, K - wp) - credit;
      if (credit <= 0 || ml <= 0) { row("bad_price"); continue; }
      int n = int(0.01 * E0 / (ml * 100));
      int ei0 = S.i(exp);
      if (n < 1) {  // B1: record the unsized (1-lot) outcome so the per-trade test covers every entry
        double st = ei0 >= 0 ? S.spx[ei0] : NAN, pay = 0;
        for (auto [k, cp, sd] : std::vector<std::tuple<double, char, int>>{{K, 'C', -1}, {K, 'P', -1}, {wc, 'C', 1}, {wp, 'P', 1}})
          pay += sd * (cp == 'C' ? std::max(st - k, 0.) : std::max(k - st, 0.));
        double pnl1 = 100 * (credit + pay) - 4 * opt_fee("SPXW");
        row("size_lt1", {K, wc, wp, strad, credit, ml, 1, 4 * opt_fee("SPXW"), vx, vx3, rv21, st, pnl1, pnl1 / (100 * ml)}); continue; }
      std::vector<Leg> legs = {{K, 'C', -1}, {K, 'P', -1}, {wc, 'C', 1}, {wp, 'P', 1}};
      double fees = 4 * n * opt_fee("SPXW");
      double V0 = 0; for (auto& l : legs) V0 += l.side * q[key(d, exp, l.k, l.cp)].mid() * 100 * n;
      L.add(v, d, credit * 100 * n - fees + V0);  // entry-day P&L: cash received + mark of the position
      open.push_back({v, exp, legs, n, V0});
      // realized P&L at settlement for the trade file (if the expiry is inside the sample)
      int ei = S.i(exp); double settle = ei >= 0 ? S.spx[ei] : NAN, pay = 0;
      for (auto& l : legs) pay += l.side * (l.cp == 'C' ? std::max(settle - l.k, 0.) : std::max(l.k - settle, 0.));
      double pnl = n * 100 * (credit + pay) - fees;
      row(ei >= 0 ? "filled" : "open_at_end", {K, wc, wp, strad, credit, ml, double(n), fees, vx, vx3, rv21, settle, pnl, pnl / (n * 100 * ml)});
    }
  }
  L.write_daily(S, S.d[22], S.d.back());
  std::cerr << "s5 done\n";
}
