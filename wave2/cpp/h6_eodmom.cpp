// H6: end-of-day momentum in SPY/QQQ. Signal = mid(15:55)/close(t-1) - 1; enter 15:55+L (T2), exit closing cross (T1).
#include "equity.hpp"

constexpr long TAU = 57300000;  // 15:55

int main() {
  Sessions S; Equity E; Snaps eq("eq_snap_", true);
  std::map<std::pair<std::string, int>, double> gex;
  { auto g = load("h6_gex"); for (auto& r : g.rows) gex[{r[1], std::stoi(r[0])}] = num(r[2]); }
  Ledger L("h6", "variant,date,sym,r_day,gex_prev,side,shares,entry,exit,long_pnl,short_pnl,fees,pnl,fill_frac");
  int first = 99999999, last = 0;
  for (size_t i = 1; i < S.d.size(); ++i) {
    int d = S.d[i], dp = S.d[i - 1];
    for (std::string s : {"SPY", "QQQ"}) {
      auto pre = eq.find(d, TAU, 500, s); auto c0 = E.get(E.close, s, dp), c1 = E.get(E.close, s, d);
      if (!pre || !c0 || !c1) continue;
      first = std::min(first, d); last = std::max(last, d);
      // --- signal: return into 15:55:00.5 (A2: the equity window opens at 15:55, so no earlier quote exists) ---
      double r = E.ret(s, dp, c0->px, d, pre->mid());
      auto gi = gex.find({s, dp}); double g = gi == gex.end() ? NAN : gi->second;
      int side = r > 0 ? 1 : r < 0 ? -1 : 0;
      for (int lat : {500, 2000, 10000}) for (std::string var : {"all", "gexneg", "nocap", "fee2"}) {
        if (var != "all" && lat != 2000) continue;
        std::string v = var + "_L" + std::to_string(lat);
        if (var == "gexneg" && !(g < 0)) continue;
        auto q = eq.find(d, TAU, lat, s); if (!q || side == 0) continue;
        // --- portfolio: 50% of equity per ETF; risk: size <= displayed size (except 'nocap' sensitivity) ---
        double entry = side > 0 ? q->ask : q->bid;
        double want = std::floor(0.5 * E0 / entry), shares = var == "nocap" ? want : std::min<double>(want, disp(q, side));
        double fm = var == "fee2" ? 2 : 1, fees = 2 * shares * FEE_SH * fm;
        double lp = shares * (c1->px - q->ask), sp = shares * (q->bid - c1->px);  // both directions, for the sign placebo
        double pnl = (side > 0 ? lp : sp) - fees;
        L.add(v, d, pnl);
        L.trades << v << "," << d << "," << s << "," << r << "," << g << "," << side << "," << shares << "," << entry << "," << c1->px << "," << lp << "," << sp << "," << fees << "," << pnl << "," << shares / want << "\n";
      }
    }
  }
  L.write_daily(S, first, last);
  std::cerr << "h6 done\n";
}
