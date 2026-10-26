// F2: engine validation. Monthly cash-secured ATM SPXW put-write (third Friday -> third Friday), settled on the SPX close.
// Variants: EOD bid (primary), EOD mid, tape 15:55 bid (sold before the close with a parity strike).
#include "common.hpp"

int main() {
  Sessions S; Snaps tape("f2_spxw_");
  auto t = load("f2_eod");
  std::map<int, std::vector<std::array<double, 5>>> eod;  // date -> {exp,k,bid,ask,spot}
  std::set<int> exps;
  for (auto& r : t.rows) { eod[std::stoi(r[0])].push_back({num(r[1]), num(r[2]), num(r[3]), num(r[4]), num(r[5])}); exps.insert(std::stoi(r[1])); }
  std::vector<int> rolls; for (int e : exps) if (S.i(e) >= 0 && eod.count(e)) rolls.push_back(e);
  fs::create_directories(RES); std::ofstream f(RES / "f2_monthly.csv"); f << "variant,date_in,date_out,k,premium,settle,ret\n";
  for (std::string v : {"eod_bid", "eod_mid", "tape1555_bid"}) {
    for (size_t j = 0; j + 1 < rolls.size(); ++j) {
      int d0 = rolls[j], d1 = rolls[j + 1]; double spot = S.spx[S.i(d0)], k = NAN, prem = NAN;
      if (v == "tape1555_bid") {  // strike from the 15:55 parity forward (known at 15:55), fill = first post-arrival bid
        auto pre = tape.get(d0, 57300000, -1); if (!pre) continue;
        Fwd fw = forward(*pre, "SPXW", d1); if (!std::isfinite(fw.F)) continue;
        double kb = -1; for (auto& q : *pre) if (q.exp == d1 && q.cp == 'P' && q.k <= fw.F && q.k > kb) kb = q.k;
        k = kb; prem = fill_px(tape.find(d0, 57300000, 99999, "SPXW", d1, k, 'P'), -1);  // first bid within 120 s (sparse tape)
      } else {
        double kb = -1, b = NAN, a = NAN;
        for (auto& x : eod[d0]) if (int(x[0]) == d1 && x[1] <= spot && x[1] > kb) { kb = x[1]; b = x[2]; a = x[3]; }
        k = kb; prem = v == "eod_bid" ? b : (a + b) / 2;
      }
      if (!(k > 0) || !(prem > 0)) { f << v << "," << d0 << "," << d1 << ",,,,\n"; continue; }
      // cash-secured: collateral = K per unit earns T-bills; return on collateral
      double settle = S.spx[S.i(d1)], growth = 1;
      for (int i = S.i(d0) + 1; i <= S.i(d1); ++i) growth *= 1 + (std::isfinite(S.rf[i]) ? S.rf[i] : 0);
      double ret = ((k + prem) * growth - std::max(k - settle, 0.0)) / k - 1;  // premium also invested in bills
      f << v << "," << d0 << "," << d1 << "," << k << "," << prem << "," << settle << "," << ret << "\n";
    }
  }
  std::cerr << "f2 done, " << rolls.size() << " roll dates\n";
}
