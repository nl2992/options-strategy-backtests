#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

// Independent, dependency-free scorecard builder for the saved daily return tape.
// Input is the transparent CSV emitted by run_rolling_research.py; no Python
// objects or binary serialization are required by this program.
struct Row { std::string date, strategy; int fold{}; double r{}, rf{}; };
struct Stats { int n{}; double total{}, excess_ann{}, vol_ann{}, sharpe{}, maxdd{}, es95{}; };

static std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> v; std::stringstream ss(s); std::string x;
    while (std::getline(ss, x, ',')) v.push_back(x);
    return v;
}
static Stats summarize(std::vector<Row> rows) {
    std::sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) { return a.date < b.date; });
    Stats z; z.n = static_cast<int>(rows.size()); if (!z.n) return z;
    double equity = 1., peak = 1., sum_ex = 0., sum_r = 0., sum_r2 = 0.;
    std::vector<double> sorted;
    for (const auto& x : rows) {
        equity *= 1. + x.r; peak = std::max(peak, equity);
        z.maxdd = std::min(z.maxdd, equity / peak - 1.);
        sum_ex += x.r - x.rf; sum_r += x.r; sum_r2 += x.r*x.r; sorted.push_back(x.r);
    }
    z.total = equity - 1.; z.excess_ann = sum_ex / z.n * 252.;
    const double mean = sum_r / z.n;
    const double var = z.n > 1 ? std::max(0., (sum_r2 - z.n*mean*mean)/(z.n-1)) : 0.;
    z.vol_ann = std::sqrt(var*252.);
    const double exmean = sum_ex / z.n;
    double ex2 = 0.; for (const auto& x : rows) ex2 += std::pow((x.r-x.rf)-exmean, 2);
    const double exsd = z.n > 1 ? std::sqrt(ex2/(z.n-1)) : 0.;
    z.sharpe = exsd > 0. ? exmean/exsd*std::sqrt(252.) : 0.;
    std::sort(sorted.begin(), sorted.end());
    const size_t k = std::max<size_t>(1, static_cast<size_t>(.05*z.n));
    z.es95 = std::accumulate(sorted.begin(), sorted.begin()+k, 0.) / k;
    return z;
}
static void write_stats(std::ofstream& o, const std::string& name, const Stats& s) {
    o << name << ',' << s.n << ',' << std::setprecision(12) << s.total << ',' << s.excess_ann
      << ',' << s.vol_ann << ',' << s.sharpe << ',' << s.maxdd << ',' << s.es95 << '\n';
}
int main(int argc, char** argv) try {
    if (argc != 3) throw std::runtime_error("usage: audit_returns INPUT.csv OUTPUT_DIR");
    std::ifstream in(argv[1]); if (!in) throw std::runtime_error("cannot open input CSV");
    std::string line; std::getline(in, line); const auto h = split(line);
    auto col = [&](const std::string& key) { auto i=std::find(h.begin(),h.end(),key); if(i==h.end()) throw std::runtime_error("missing column: "+key); return int(i-h.begin()); };
    const int date_i=col("date"), ret_i=col("return"), rf_i=col("rf_daily"), strat_i=col("strategy"), fold_i=col("fold");
    std::map<std::string,std::vector<Row>> by_strategy;
    std::map<std::pair<std::string,int>,std::vector<Row>> by_fold;
    while (std::getline(in,line)) {
        if(line.empty()) continue; auto v=split(line); if(static_cast<int>(v.size())<=std::max({date_i,ret_i,rf_i,strat_i,fold_i})) continue;
        Row r{v[date_i],v[strat_i],std::stoi(v[fold_i]),std::stod(v[ret_i]),std::stod(v[rf_i])};
        by_strategy[r.strategy].push_back(r); by_fold[{r.strategy,r.fold}].push_back(r);
    }
    std::string outdir=argv[2]; if(!outdir.empty() && outdir.back()!='/') outdir+='/';
    std::ofstream score(outdir+"cpp_oos_scorecard.csv"), folds(outdir+"cpp_fold_returns.csv"), tape(outdir+"cpp_oos_daily_returns.csv");
    if(!score || !folds || !tape) throw std::runtime_error("cannot create output files");
    score << "strategy,sessions,total_return,excess_ann,vol_ann,sharpe,maxdd,es95\n";
    folds << "strategy,fold,sessions,total_return,excess_ann,vol_ann,sharpe,maxdd,es95\n";
    tape << "date,return,rf_daily,strategy,fold,normalized_equity\n";
    for(const auto& [s,rs]:by_strategy) write_stats(score,s,summarize(rs));
    for(const auto& [key,rs]:by_fold) { const auto st=summarize(rs); folds<<key.first<<','<<key.second<<','<<st.n<<','<<std::setprecision(12)<<st.total<<','<<st.excess_ann<<','<<st.vol_ann<<','<<st.sharpe<<','<<st.maxdd<<','<<st.es95<<'\n'; }
    for(auto& [s,rs]:by_strategy) {
        std::sort(rs.begin(),rs.end(),[](const Row& a,const Row& b){ return a.date<b.date; });
        double nav=1.;
        for(const auto& r:rs) { nav*=1.+r.r; tape<<r.date<<','<<std::setprecision(12)<<r.r<<','<<r.rf<<','<<s<<','<<r.fold<<','<<nav<<'\n'; }
    }
    std::cout << "Wrote return tape, scorecard, and " << by_fold.size() << " fold result rows for " << by_strategy.size() << " strategies\n";
    return 0;
} catch(const std::exception& e) { std::cerr << "audit_returns: " << e.what() << '\n'; return 1; }
