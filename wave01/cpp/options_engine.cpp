#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
constexpr int NU=18, MULT=100, TRAIN=252, TEST=63, WARM=126;
const std::array<std::string,NU> UNDS={"SPY","QQQ","SPX","AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN","AVGO","NFLX","AMD","CRM","JPM","LLY","UNH","XOM","WMT"};
struct Sess { std::string date; int gap=1; double rf=0; };
struct Feature { double spot=NAN,ivp=NAN,ret20=NAN,ret60=NAN,vrp20=NAN,vrp60=NAN,skew=NAN; };
#pragma pack(push,1)
struct RawOption { uint16_t session; uint8_t und; char root[16]; int32_t expiry; uint8_t cp; double strike,bid,ask,delta; int32_t oi; };
#pragma pack(pop)
struct Option { uint16_t session; uint8_t und,cp; std::string root; int32_t expiry; double strike,bid,ask,delta; int oi; };
struct Key { std::string root; int32_t expiry; uint8_t cp; double strike; bool operator==(const Key& b)const{return root==b.root&&expiry==b.expiry&&cp==b.cp&&strike==b.strike;} };
struct Leg { Key k; int qty; };
struct Position { int id,und,n,kind; std::vector<Leg> legs; std::string entry_date,signal_date; int entry_i,expiry; double open_px,width,max_loss,entry_fees,entry_spread,last_cost; std::string pending; int stale=0; };
struct Config { std::string strategy,signal; double delta=.15,ivp_min=60,vrp_min=0,trend_threshold=0,skew_threshold=.02,fee_mult=1,slip=1; int dte=30; };
struct SimResult { std::vector<double> returns; std::vector<std::string> dates; int trades=0; double pnl=0,fees=0,spread=0; std::vector<std::array<double,9>> blotter; };
static int ordinal(const std::string&s);

static std::vector<std::string> csv(const std::string& s){std::vector<std::string> a;std::string x;std::stringstream q(s);while(std::getline(q,x,','))a.push_back(x);return a;}
static double num(const std::string& s){if(s.empty())return NAN;try{return std::stod(s);}catch(...){return NAN;}}
static std::string rootstr(const char* p){return std::string(p, strnlen(p,16));}
static bool finite(double x){return std::isfinite(x);}
static double fill(double b,double a,int side,double slip){double mid=(b+a)/2.;return std::max(0.,mid+side*slip*(a-b)/2.);}
struct Market {
 std::vector<Sess> sessions; std::array<std::vector<Feature>,NU> feat;
 std::vector<Option> opts; std::vector<std::array<size_t,2*NU>> ranges;
 mutable std::unordered_map<std::string,std::vector<Leg>> selection_cache;
 std::array<double,NU> width{};
 Feature& f(int i,int u){return feat[u][i];}
 std::pair<size_t,size_t> range(int i,int u)const{return {ranges[i][2*u],ranges[i][2*u+1]};}
 const Option* find(int i,int u,const Key& k)const{
   auto [a,b]=range(i,u);
   auto it=std::lower_bound(opts.begin()+a,opts.begin()+b,k,[](const Option& o,const Key& x){
     if(o.root!=x.root)return o.root<x.root;if(o.expiry!=x.expiry)return o.expiry<x.expiry;
     if(o.cp!=x.cp)return o.cp<x.cp;return o.strike<x.strike;});
   if(it!=opts.begin()+b&&it->root==k.root&&it->expiry==k.expiry&&it->cp==k.cp&&it->strike==k.strike)return &*it;return nullptr;
 }
};
static Market load(const fs::path& dir){
 Market m;std::ifstream sf(dir/"sessions.csv");std::string line;std::getline(sf,line);
 while(std::getline(sf,line)){auto v=csv(line);m.sessions.push_back({v[1],int(num(v[2])),num(v[3])});}
 for(auto& x:m.feat)x.resize(m.sessions.size());
 std::ifstream ff(dir/"features.csv");std::getline(ff,line);while(std::getline(ff,line)){auto v=csv(line);int i=int(num(v[0])),u=int(num(v[1]));if(i<0||i>=(int)m.sessions.size()||u<0||u>=NU)continue;auto& f=m.feat[u][i];f.spot=num(v[2]);f.ivp=num(v[3]);f.ret20=num(v[4]);f.ret60=num(v[5]);f.vrp20=num(v[6]);f.vrp60=num(v[7]);f.skew=num(v[8]);}
 std::ifstream bin(dir/"options.bin",std::ios::binary);if(!bin)throw std::runtime_error("missing options.bin");RawOption r;
 while(bin.read(reinterpret_cast<char*>(&r),sizeof(r))){Option o;o.session=r.session;o.und=r.und;o.cp=r.cp;o.root=rootstr(r.root);o.expiry=r.expiry;o.strike=r.strike;o.bid=r.bid;o.ask=r.ask;o.delta=r.delta;o.oi=r.oi;m.opts.push_back(std::move(o));}
 std::sort(m.opts.begin(),m.opts.end(),[](const Option&a,const Option&b){if(a.session!=b.session)return a.session<b.session;if(a.und!=b.und)return a.und<b.und;if(a.root!=b.root)return a.root<b.root;if(a.expiry!=b.expiry)return a.expiry<b.expiry;if(a.cp!=b.cp)return a.cp<b.cp;return a.strike<b.strike;});
 m.ranges.resize(m.sessions.size());size_t k=0;
 for(int i=0;i<(int)m.sessions.size();++i)for(int u=0;u<NU;++u){size_t a=k;while(k<m.opts.size()&&m.opts[k].session==i&&m.opts[k].und==u)++k;m.ranges[i][2*u]=a;m.ranges[i][2*u+1]=k;}
 for(int u=0;u<NU;++u)m.width[u]=(u==2||u==5||u==9)?10.:5.;
 std::cerr<<"Loaded "<<m.sessions.size()<<" sessions and "<<m.opts.size()<<" option snapshots\n";return m;
}

static std::vector<Leg> spread(const Market&m,int i,int u,int32_t ex,uint8_t cp,double delta,double W){
 auto [a,b]=m.range(i,u);const Option* sh=nullptr;
 for(size_t j=a;j<b;++j){const auto&o=m.opts[j];if(o.expiry!=ex||o.cp!=cp||!finite(o.delta)||o.bid<=0||o.oi<10||o.ask<=o.bid)continue;double mid=(o.ask+o.bid)/2;if((o.ask-o.bid)/mid>.30)continue;if(!sh||std::abs(std::abs(o.delta)-delta)<std::abs(std::abs(sh->delta)-delta))sh=&o;}
 if(!sh||std::abs(std::abs(sh->delta)-delta)>.07)return{};
 double target=sh->strike+(cp==0?-W:W);const Option* wing=nullptr;
 for(size_t j=a;j<b;++j){const auto&o=m.opts[j];if(o.root!=sh->root||o.expiry!=ex||o.cp!=cp||o.ask<=0||o.oi<10||o.ask<o.bid)continue;double mid=(o.ask+o.bid)/2;if((o.ask-o.bid)/mid>.60)continue;if(!wing||std::abs(o.strike-target)<std::abs(wing->strike-target))wing=&o;}
 if(!wing||std::abs(wing->strike-sh->strike)<.5*W||std::abs(wing->strike-sh->strike)>2*W)return{};
 return {{{sh->root,ex,cp,sh->strike},-1},{{wing->root,ex,cp,wing->strike},1}};
}
static std::vector<Leg> select_legs(const Market&m,int i,int u,const Config&c){
 std::string ck=std::to_string(i)+":"+std::to_string(u)+":"+c.strategy+":"+std::to_string(c.delta)+":"+std::to_string(c.dte);
 auto cached=m.selection_cache.find(ck);if(cached!=m.selection_cache.end())return cached->second;
 auto [a,b]=m.range(i,u);int lo=c.dte==30?21:35,hi=c.dte==30?35:60;double target=c.dte;
 int ex=0;double best=1e9;
 const int today=ordinal(m.sessions[i].date);
 for(size_t j=a;j<b;++j){int d=m.opts[j].expiry-today;if(d>=lo&&d<=hi&&std::abs(d-target)<best){best=std::abs(d-target);ex=m.opts[j].expiry;}}
 if(!ex){m.selection_cache.emplace(ck,std::vector<Leg>{});return{};}double W=m.width[u];std::vector<Leg> result;
 if(c.strategy=="pcs")result=spread(m,i,u,ex,0,c.delta,W);
 else if(c.strategy=="ccs")result=spread(m,i,u,ex,1,c.delta,W);
 else if(c.strategy=="ic"){auto p=spread(m,i,u,ex,0,c.delta,W),q=spread(m,i,u,ex,1,c.delta,W);if(!p.empty()&&!q.empty()){p.insert(p.end(),q.begin(),q.end());result=std::move(p);}}
 else {
 uint8_t cp=c.strategy=="dv"?1:0;const Option* L=nullptr;
 for(size_t j=a;j<b;++j){const auto&o=m.opts[j];if(o.expiry!=ex||o.cp!=cp||!finite(o.delta)||o.ask<=0||o.oi<10||o.ask<o.bid)continue;double mid=(o.ask+o.bid)/2;if((o.ask-o.bid)/mid>.60)continue;double d=cp==1?std::abs(o.delta-c.delta):std::abs(std::abs(o.delta)-c.delta);if(!L||d<(cp==1?std::abs(L->delta-c.delta):std::abs(std::abs(L->delta)-c.delta)))L=&o;}
 if(!L){m.selection_cache.emplace(ck,std::vector<Leg>{});return{};}double strike=L->strike+(cp==1?W:-W);const Option* sh=nullptr;
 for(size_t j=a;j<b;++j){const auto&o=m.opts[j];if(o.root!=L->root||o.expiry!=ex||o.cp!=cp||o.ask<=0||o.oi<10||o.ask<o.bid)continue;double mid=(o.ask+o.bid)/2;if((o.ask-o.bid)/mid>.60)continue;if(!sh||std::abs(o.strike-strike)<std::abs(sh->strike-strike))sh=&o;}
 if(sh&&std::abs(sh->strike-L->strike)>=.5*W&&std::abs(sh->strike-L->strike)<=2*W)result={{{L->root,ex,cp,L->strike},1},{{sh->root,ex,cp,sh->strike},-1}};
 }
 m.selection_cache.emplace(ck,result);return result;
}
static int ordinal(const std::string&s){int y=std::stoi(s.substr(0,4)),m=std::stoi(s.substr(5,2)),d=std::stoi(s.substr(8,2)); // days since 1970 (affine with Python ordinal)
 y-=m<=2;const int era=(y>=0?y:y-399)/400;const unsigned yoe=static_cast<unsigned>(y-era*400);const unsigned doy=(153*(m+(m>2?-3:9))+2)/5+d-1;const unsigned doe=yoe*365+yoe/4-yoe/100+doy;return era*146097+static_cast<int>(doe)-305;
}

static double marked_cost(const Market&m,Position&p,int i){double c=0;bool ok=true;for(const auto&l:p.legs){auto*q=m.find(i,p.und,l.k);if(!q){ok=false;break;}c+=l.qty<0?q->ask:-q->bid;}if(!ok){++p.stale;c=finite(p.last_cost)?p.last_cost:-p.open_px;}double lo=p.kind?-p.width:intrinsic(p.legs,m.feat[p.und][i].spot),hi=p.kind?0.:p.width;c=std::min(std::max(c,lo),hi);p.last_cost=c;return c;}
static double rf_day(const Market&m,int i){return m.sessions[i-1].rf*m.sessions[i].gap/360.;}
static SimResult simulate(const Market&m,const Config&cfg,int start,int stop){
 SimResult out;const int end=stop-1;double cash=200000.;std::vector<Position> pos;int next_id=0;std::vector<double> equity(end+1,NAN);equity[0]=cash;
 auto spot=[&](int u,int i){return m.feat[u][i].spot;};
 for(int i=1;i<=end;++i){const auto&d=m.sessions[i];cash*=1.+rf_day(m,i);
  for(size_t j=0;j<pos.size();){auto&p=pos[j];std::string reason=p.pending;int today=ordinal(d.date);
   if(reason.empty()&&p.expiry-today<=5)reason="time";
   if(reason.empty()&&(p.und==0||p.und==1))for(const auto&l:p.legs)if(l.qty<0){double sp=spot(p.und,i-1);if((l.k.cp==1&&sp>l.k.strike)||(l.k.cp==0&&sp<l.k.strike)){reason="itm_short";break;}}
   if(reason.empty()&&p.expiry<=today)reason="expiry";if(reason.empty()&&i==end)reason="fold_end";
   if(reason.empty()){++j;continue;}
   double cost=0,fees=0,sc=0;bool expiry=p.expiry<=today;
   if(expiry)cost=intrinsic(p.legs,spot(p.und,i));
   else {bool ok=true;for(const auto&l:p.legs){auto*q=m.find(i,p.und,l.k);if(!q){ok=false;break;}int side=l.qty<0?1:-1;double px=fill(q->bid,q->ask,side,cfg.slip);cost+=l.qty<0?px:-px;sc+=std::abs(px-(q->bid+q->ask)/2.);}if(!ok){p.pending=reason;++j;continue;}fees=.65*cfg.fee_mult*p.legs.size()*p.n;}
   const double pnl=(p.open_px-cost)*MULT*p.n-p.entry_fees-(expiry?0:fees);cash+=(-cost)*MULT*p.n-(expiry?0:fees);out.pnl+=pnl;out.fees+=p.entry_fees+(expiry?0:fees);out.spread+=p.entry_spread+sc*MULT*p.n;++out.trades;
   out.blotter.push_back({double(p.id),double(p.und),double(p.n),double(p.entry_i),double(i),pnl,p.entry_fees+(expiry?0:fees),p.entry_spread+sc*MULT*p.n,double(today-ordinal(p.entry_date))});pos.erase(pos.begin()+j);
  }
  if(i<end&&i>=start&&(i-start)%5==0){int si=i-1;double eq=cash;for(auto&p:pos)eq-=p.last_cost*MULT*p.n;
   for(int z=0;z<NU;++z){int u=(z+(i/5)%NU)%NU;const Feature&f=m.feat[u][si];if(!signal_ok(f,cfg))continue;auto legs=select_legs(m,si,u,cfg);if(legs.empty())continue;
    double px=0,sc=0;bool ok=true;std::vector<const Option*> qs;for(const auto&l:legs){auto*q=m.find(i,u,l.k);if(!q){ok=false;break;}qs.push_back(q);}if(!ok)continue;
    for(size_t k=0;k<legs.size();++k){const auto&l=legs[k];auto*q=qs[k];if(q->ask<=q->bid||q->ask<=0||(l.qty<0&&q->bid<=0)){ok=false;break;}double fpx=fill(q->bid,q->ask,l.qty>0?1:-1,cfg.slip);px+=l.qty>0?-fpx:fpx;sc+=std::abs(fpx-(q->bid+q->ask)/2.);}if(!ok)continue;
    double W=0;for(size_t k=0;k<legs.size();k+=2)W=std::max(W,std::abs(legs[k].k.strike-legs[k+1].k.strike));int kind=(cfg.strategy=="dv"||cfg.strategy=="pdv")?1:0;double debit=-px;
    if(kind&&(debit<=0||debit>=W))continue;if(!kind&&px<.1*W*(cfg.strategy=="ic"?2:1))continue;
    double maxloss=(kind?debit:W-px)*MULT+.65*cfg.fee_mult*legs.size()*2;double byund=0,agg=0,coll=0;
    for(const auto&p:pos){if(p.und==u)byund+=p.max_loss*p.n;agg+=p.max_loss*p.n;if(!p.kind)coll+=p.width*MULT*p.n;}
    double cap=std::min({.005*eq,.02*eq-byund,.05*eq-agg});int n=cap>0?int(std::floor(cap/maxloss)):0;if(n<1)continue;
    double need=kind?debit*MULT*n:W*MULT*n;double reserve=.25*eq;if(!kind&&cash-coll-W*MULT*n+px*MULT*n<reserve)continue;if(kind&&cash-coll-need<reserve)continue;
    double entryfees=.65*cfg.fee_mult*legs.size()*n;cash+=px*MULT*n-entryfees;Position p{};p.id=++next_id;p.und=u;p.n=n;p.kind=kind;p.legs=std::move(legs);p.entry_i=i;p.entry_date=d.date;p.signal_date=m.sessions[si].date;p.expiry=p.legs[0].k.expiry;p.open_px=px;p.width=W;p.max_loss=maxloss;p.entry_fees=entryfees;p.entry_spread=sc*MULT*n;p.last_cost=-px;pos.push_back(std::move(p));
   }
  }
  double liq=0;for(auto&p:pos){double cost=marked_cost(m,p,i);liq-=cost*MULT*p.n;double pnlps=p.open_px-cost;if(p.kind){double debit=-p.open_px;if(-cost>=debit*1.5)p.pending="take_profit";else if(-cost<=debit*.5)p.pending="stop";}else if(pnlps>=.5*p.open_px)p.pending="take_profit";else if(pnlps<=-2*p.open_px)p.pending="stop";}equity[i]=cash+liq;
 }
 for(int i=start;i<=end;++i){out.dates.push_back(m.sessions[i].date);out.returns.push_back(equity[i]/equity[i-1]-1.);out.rfs.push_back(rf_day(m,i));}return out;
}

struct Metrics { int n=0,trades=0;double total=0,exann=0,vol=0,sharpe=NAN,maxdd=0,es95=0; };
static Metrics metrics(const SimResult&r){Metrics z;z.n=int(r.returns.size());z.trades=r.trades;if(!z.n)return z;double eq=1,peak=1,sumex=0,sumr=0;std::vector<double> ex,rets=r.returns;for(size_t i=0;i<r.returns.size();++i){double x=r.returns[i];eq*=1+x;peak=std::max(peak,eq);z.maxdd=std::min(z.maxdd,eq/peak-1);double e=x-r.rfs[i];ex.push_back(e);sumex+=e;sumr+=x;}z.total=eq-1;z.exann=sumex/z.n*252.;double rm=sumr/z.n,em=sumex/z.n,rv=0,ev=0;for(size_t i=0;i<rets.size();++i){rv+=std::pow(rets[i]-rm,2);ev+=std::pow(ex[i]-em,2);}double sd=z.n>1?std::sqrt(rv/(z.n-1)):0,esd=z.n>1?std::sqrt(ev/(z.n-1)):0;z.vol=sd*std::sqrt(252.);if(z.n>=20&&esd>0)z.sharpe=em/esd*std::sqrt(252.);std::sort(rets.begin(),rets.end());int k=std::max(1,int(.05*z.n));z.es95=std::accumulate(rets.begin(),rets.begin()+k,0.)/k;return z;}
static std::vector<Config> grid(){std::vector<Config> v;for(const std::string s:{"pcs","ccs","ic","dv","pdv"}){std::vector<double> ds=(s=="pcs"||s=="ccs"||s=="ic")?std::vector<double>{.15,.25}:std::vector<double>{.50,.60};for(double d:ds)for(int dt:{30,45})for(int si=0;si<11;++si){Config c;c.strategy=s;c.delta=d;c.dte=dt;c.signal="none";c.ivp_min=60;c.vrp_min=0;c.trend_threshold=0;c.skew_threshold=.02;switch(si){case 0:break;case 1:c.signal="ivp";c.ivp_min=50;break;case 2:c.signal="ivp";c.ivp_min=70;break;case 3:c.signal="vrp20";break;case 4:c.signal="vrp20";c.vrp_min=.02;break;case 5:c.signal="vrp60";break;case 6:c.signal="trend20";break;case 7:c.signal="trend60";c.trend_threshold=.02;break;case 8:c.signal="vrp20_trend60";c.vrp_min=.02;c.trend_threshold=.02;break;case 9:c.signal="skew25";break;case 10:c.signal="skew25";c.skew_threshold=.04;break;}v.push_back(c);}}return v;}
static std::vector<std::array<int,4>> make_folds(int n){std::vector<std::array<int,4>> v;for(int s=WARM;s+TRAIN<n;s+=TEST){int te=std::min(s+TRAIN+TEST,n);if(te-(s+TRAIN)<20)break;v.push_back({s,s+TRAIN,s+TRAIN,te});}return v;}
static std::string trial_id(int i){std::ostringstream s;s<<'T'<<std::setw(4)<<std::setfill('0')<<i;return s.str();}
static void cfgout(std::ostream&o,const Config&c){o<<c.strategy<<','<<c.delta<<','<<c.dte<<','<<c.signal<<','<<c.ivp_min<<','<<c.vrp_min<<','<<c.trend_threshold<<','<<c.skew_threshold;}
static void mout(std::ostream&o,const Metrics&m){o<<m.n<<','<<std::setprecision(12)<<m.total<<','<<m.exann<<','<<m.vol<<','<<m.sharpe<<','<<m.maxdd<<','<<m.es95<<','<<m.trades;}

static void run_all(Market&m,const fs::path&outdir){
 fs::create_directories(outdir);auto configs=grid();auto folds=make_folds(int(m.sessions.size()));
 std::ofstream reg(outdir/"candidate_registry.csv"),cs(outdir/"fold_candidate_scores.csv"),sel(outdir/"fold_selections.csv"),fo(outdir/"fold_oos_results.csv"),daily(outdir/"oos_daily_returns.csv"),trades(outdir/"oos_trades.csv"),score(outdir/"oos_scorecard.csv");
 reg<<"trial_id,strategy,delta,dte_target,signal,ivp_min,vrp_min,trend_threshold,skew_threshold\n";cs<<"fold,trial_id,strategy,delta,dte_target,signal,ivp_min,vrp_min,trend_threshold,skew_threshold,n,total,ex_ann,vol,sharpe,maxdd,es95,trade_trades\n";sel<<"fold,trial_id,strategy,delta,dte_target,signal,ivp_min,vrp_min,trend_threshold,skew_threshold,train_sharpe,train_trades\n";fo<<"fold,strategy,variant,trial_id,n,total,ex_ann,vol,sharpe,maxdd,es95,trade_trades\n";daily<<"date,return,rf_daily,strategy,fold,normalized_equity\n";trades<<"strategy,fold,variant,trade_id,underlying,contracts,entry_session,exit_session,pnl,fees,spread_cost,hold_days\n";
 for(int t=0;t<(int)configs.size();++t){reg<<trial_id(t)<<',';cfgout(reg,configs[t]);reg<<'\n';}
 std::map<std::string,std::vector<std::tuple<std::string,double,double,int>>> all_daily;std::map<std::string,int> selected_n,positive,control_n,fee_n,slip_n,trades_n;std::map<std::string,double> control,fee,slip;
 const std::array<std::string,5> strategies={"pcs","ccs","ic","dv","pdv"};
 for(int fi=0;fi<(int)folds.size();++fi){int ts=folds[fi][0],te=folds[fi][1],os=folds[fi][2],oe=folds[fi][3];std::array<int,5> bi;bi.fill(-1);std::array<double,5> bs;bs.fill(-std::numeric_limits<double>::infinity());
  for(int t=0;t<(int)configs.size();++t){auto r=simulate(m,configs[t],ts,te);auto mt=metrics(r);cs<<fi+1<<','<<trial_id(t)<<',';cfgout(cs,configs[t]);cs<<',';mout(cs,mt);cs<<'\n';int si=int(std::find(strategies.begin(),strategies.end(),configs[t].strategy)-strategies.begin());if(mt.trades>=15&&finite(mt.sharpe)&&mt.sharpe>bs[si]){bs[si]=mt.sharpe;bi[si]=t;}}
  for(int si=0;si<5;++si){int t=bi[si];if(t<0)continue;Config base=configs[t];auto tr=simulate(m,base,ts,te);auto tm=metrics(tr);sel<<fi+1<<','<<trial_id(t)<<',';cfgout(sel,base);sel<<','<<tm.sharpe<<','<<tm.trades<<'\n';++selected_n[base.strategy];
   for(const std::string variant:{"selected","control","fee2x","slip1.5"}){Config c=base;if(variant=="control")c.signal="none";if(variant=="fee2x")c.fee_mult=2;if(variant=="slip1.5")c.slip=1.5;auto r=simulate(m,c,os,oe);auto mt=metrics(r);fo<<fi+1<<','<<base.strategy<<','<<variant<<','<<trial_id(t)<<',';mout(fo,mt);fo<<'\n';
    if(variant=="control"){control[base.strategy]+=mt.exann;++control_n[base.strategy];}if(variant=="fee2x"){fee[base.strategy]+=mt.exann;++fee_n[base.strategy];}if(variant=="slip1.5"){slip[base.strategy]+=mt.exann;++slip_n[base.strategy];}
    if(variant=="selected"){if(mt.exann>0)++positive[base.strategy];trades_n[base.strategy]+=r.trades;for(size_t k=0;k<r.returns.size();++k)all_daily[base.strategy].push_back({r.dates[k],r.returns[k],r.rfs[k],fi+1});}
    int tradeid=0;for(auto&b:r.blotter){int u=int(b[1]);trades<<base.strategy<<','<<fi+1<<','<<variant<<','<<++tradeid<<','<<UNDS[u]<<','<<int(b[2])<<','<<int(b[3])<<','<<int(b[4])<<','<<b[5]<<','<<b[6]<<','<<b[7]<<','<<b[8]<<'\n';}
   }
  }
  std::cerr<<"Completed fold "<<fi+1<<"/"<<folds.size()<<"; selection cache "<<m.selection_cache.size()<<"\n";
 }
 for(auto&[s,rows]:all_daily){std::sort(rows.begin(),rows.end());double nav=1;for(auto&x:rows){nav*=1+std::get<1>(x);daily<<std::get<0>(x)<<','<<std::setprecision(12)<<std::get<1>(x)<<','<<std::get<2>(x)<<','<<s<<','<<std::get<3>(x)<<','<<nav<<'\n';}}
 score<<"strategy,oos_sessions,oos_folds,oos_total_return,oos_excess_ann,oos_vol_ann,oos_sharpe,oos_maxdd,oos_es95,positive_oos_folds,control_ex_ann_mean,fee2x_ex_ann_mean,slip1_5_ex_ann_mean,oos_trades\n";
 for(auto&[s,rows]:all_daily){std::sort(rows.begin(),rows.end());int n=int(rows.size());double eq=1,peak=1,sumr=0,sumex=0;std::vector<double>r,ex;std::set<int> usedfolds;Metrics mt;for(auto&x:rows){double v=std::get<1>(x),rf=std::get<2>(x);eq*=1+v;peak=std::max(peak,eq);mt.maxdd=std::min(mt.maxdd,eq/peak-1);r.push_back(v);ex.push_back(v-rf);sumr+=v;sumex+=v-rf;usedfolds.insert(std::get<3>(x));}mt.n=n;mt.total=eq-1;mt.exann=sumex/n*252.;double rm=sumr/n,em=sumex/n,vr=0,ve=0;for(int j=0;j<n;++j){vr+=std::pow(r[j]-rm,2);ve+=std::pow(ex[j]-em,2);}mt.vol=std::sqrt(vr/(n-1)*252.);mt.sharpe=em/std::sqrt(ve/(n-1))*std::sqrt(252.);std::sort(r.begin(),r.end());int k=std::max(1,int(.05*n));mt.es95=std::accumulate(r.begin(),r.begin()+k,0.)/k;
  score<<s<<','<<n<<','<<usedfolds.size()<<','<<std::setprecision(12)<<mt.total<<','<<mt.exann<<','<<mt.vol<<','<<mt.sharpe<<','<<mt.maxdd<<','<<mt.es95<<','<<positive[s]<<','<<control[s]/std::max(1,selected_n[s])<<','<<fee[s]/std::max(1,selected_n[s])<<','<<slip[s]/std::max(1,selected_n[s])<<','<<trades_n[s]<<'\n';}
 std::cerr<<"Wrote C++ rolling grid files to "<<outdir<<"\n";
}
int main(int argc,char**argv){try{if(argc!=3){std::cerr<<"usage: options_engine INPUT_DIR OUTPUT_DIR\n";return 2;}auto m=load(argv[1]);run_all(m,argv[2]);return 0;}catch(const std::exception&e){std::cerr<<"options_engine: "<<e.what()<<"\n";return 1;}}
static double intrinsic(const std::vector<Leg>&legs,double spot){double c=0;for(const auto&l:legs){double iv=l.k.cp?std::max(0.,spot-l.k.strike):std::max(0.,l.k.strike-spot);c+=-l.qty*iv;}return c;}
static bool signal_ok(const Feature&f,const Config&c){
 if(c.signal=="none")return true;if(c.signal=="ivp")return finite(f.ivp)&&f.ivp>=c.ivp_min;
 bool credit=c.strategy=="pcs"||c.strategy=="ccs"||c.strategy=="ic";
 if(c.signal=="vrp20"||c.signal=="vrp60"){double v=c.signal=="vrp20"?f.vrp20:f.vrp60;if(!finite(v))return false;return credit?v>=c.vrp_min:v<=-c.vrp_min;}
 auto trend=[&](double t){if(!finite(t))return false;if(c.strategy=="pcs"||c.strategy=="dv")return t>c.trend_threshold;if(c.strategy=="ccs"||c.strategy=="pdv")return t< -c.trend_threshold;return std::abs(t)<=c.trend_threshold;};
 if(c.signal=="trend20")return trend(f.ret20);if(c.signal=="trend60")return trend(f.ret60);
 if(c.signal=="vrp20_trend60"){if(!finite(f.vrp20))return false;return (credit?f.vrp20>=c.vrp_min:f.vrp20<=-c.vrp_min)&&trend(f.ret60);}
 if(c.signal=="skew25"){if(!finite(f.skew))return false;if(c.strategy=="pcs"||c.strategy=="dv")return f.skew>=c.skew_threshold;if(c.strategy=="ccs"||c.strategy=="pdv")return f.skew<=-c.skew_threshold;return std::abs(f.skew)<=c.skew_threshold;}
 return false;
}
static double intrinsic(const std::vector<Leg>&legs,double spot){double c=0;for(const auto&l:legs){double iv=l.k.cp?std::max(0.,spot-l.k.strike):std::max(0.,l.k.strike-spot);c+=-l.qty*iv;}return c;}
static bool signal_ok(const Feature&f,const Config&c){
 if(c.signal=="none")return true;if(c.signal=="ivp")return finite(f.ivp)&&f.ivp>=c.ivp_min;
 bool credit=c.strategy=="pcs"||c.strategy=="ccs"||c.strategy=="ic";
 if(c.signal=="vrp20"||c.signal=="vrp60"){double v=c.signal=="vrp20"?f.vrp20:f.vrp60;if(!finite(v))return false;return credit?v>=c.vrp_min:v<=-c.vrp_min;}
 auto trend=[&](double t){if(!finite(t))return false;if(c.strategy=="pcs"||c.strategy=="dv")return t>c.trend_threshold;if(c.strategy=="ccs"||c.strategy=="pdv")return t< -c.trend_threshold;return std::abs(t)<=c.trend_threshold;};
 if(c.signal=="trend20")return trend(f.ret20);if(c.signal=="trend60")return trend(f.ret60);
 if(c.signal=="vrp20_trend60"){if(!finite(f.vrp20))return false;return (credit?f.vrp20>=c.vrp_min:f.vrp20<=-c.vrp_min)&&trend(f.ret60);}
 if(c.signal=="skew25"){if(!finite(f.skew))return false;if(c.strategy=="pcs"||c.strategy=="dv")return f.skew>=c.skew_threshold;if(c.strategy=="ccs"||c.strategy=="pdv")return f.skew<=-c.skew_threshold;return std::abs(f.skew)<=c.skew_threshold;}
 return false;
}

static double marked_cost(const Market&m,Position&p,int i){double c=0;bool ok=true;for(const auto&l:p.legs){auto*q=m.find(i,p.und,l.k);if(!q){ok=false;break;}c+=l.qty<0?q->ask:-q->bid;}if(!ok){++p.stale;c=finite(p.last_cost)?p.last_cost:-p.open_px;}const double lo=p.kind? -p.width:intrinsic(p.legs,m.f(i,p.und).spot);const double hi=p.kind?0.:p.width;c=std::min(std::max(c,lo),hi);p.last_cost=c;return c;}
static double rf_day(const Market&m,int i){return m.sessions[i-1].rf*m.sessions[i].gap/360.;}
static SimResult simulate(const Market&m,const Config&cfg,int start,int stop){
 SimResult out;const int end=stop-1;double cash=200000.;std::vector<Position> pos;int next_id=0;std::vector<double> equity(end+1,NAN);equity[0]=cash;
 auto spot=[&](int u,int i){return m.f(i,u).spot;};
 for(int i=1;i<=end;++i){const auto&d=m.sessions[i];cash*=1.+rf_day(m,i);
   for(size_t j=0;j<pos.size();){auto&p=pos[j];std::string reason=p.pending;int today=ordinal(d.date),prev=ordinal(m.sessions[i-1].date);
     if(reason.empty()&&p.expiry-today<=5)reason="time";
     if(reason.empty()&&(p.und==0||p.und==1))for(const auto&l:p.legs)if(l.qty<0){double sp=spot(p.und,i-1);if((l.k.cp==1&&sp>l.k.strike)||(l.k.cp==0&&sp<l.k.strike)){reason="itm_short";break;}}
     if(reason.empty()&&p.expiry<=today)reason="expiry";if(reason.empty()&&i==end)reason="fold_end";
     if(reason.empty()){++j;continue;}
     double cost=0,fees=0,sc=0;bool expiry=p.expiry<=today;
     if(expiry)cost=intrinsic(p.legs,spot(p.und,i));
     else {bool ok=true;for(const auto&l:p.legs){auto*q=m.find(i,p.und,l.k);if(!q){ok=false;break;}int side=l.qty<0?1:-1;double px=fill(q->bid,q->ask,side,cfg.slip);cost+=l.qty<0?px:-px;sc+=std::abs(px-(q->bid+q->ask)/2.);}if(!ok){p.pending=reason;++j;continue;}fees=.65*cfg.fee_mult*p.legs.size()*p.n;}
     const double pnl=(p.open_px-cost)*MULT*p.n-p.entry_fees-(expiry?0:fees);cash+=(-cost)*MULT*p.n-(expiry?0:fees);out.pnl+=pnl;out.fees+=p.entry_fees+(expiry?0:fees);out.spread+=p.entry_spread+sc*MULT*p.n;++out.trades;
     out.blotter.push_back({double(p.id),double(p.und),double(p.n),double(p.entry_i),double(i),pnl,p.entry_fees+(expiry?0:fees),p.entry_spread+sc*MULT*p.n,double((today-ordinal(p.entry_date)))});
     pos.erase(pos.begin()+j);
   }
   if(i<end&&i>=start&&(i-start)%5==0){int si=i-1;double eq=cash;for(auto&p:pos)eq-=p.last_cost*MULT*p.n;
     for(int z=0;z<NU;++z){int u=(z+(i/5)%NU)%NU;const Feature& f=m.f(si,u);if(!signal_ok(f,cfg))continue;auto legs=select_legs(m,si,u,cfg);if(legs.empty())continue;
       double px=0,sc=0;bool ok=true;std::vector<const Option*> qs;for(const auto&l:legs){auto*q=m.find(i,u,l.k);if(!q){ok=false;break;}qs.push_back(q);}if(!ok)continue;
       for(size_t k=0;k<legs.size();++k){const auto&l=legs[k];auto*q=qs[k];if(q->ask<=q->bid||q->ask<=0||(l.qty<0&&q->bid<=0)){ok=false;break;}double fpx=fill(q->bid,q->ask,l.qty>0?1:-1,cfg.slip);px+=l.qty>0?-fpx:fpx;sc+=std::abs(fpx-(q->bid+q->ask)/2.);}if(!ok)continue;
       double W=0;for(size_t k=0;k<legs.size();k+=2)W=std::max(W,std::abs(legs[k].k.strike-legs[k+1].k.strike));int kind=(cfg.strategy=="dv"||cfg.strategy=="pdv")?1:0;
       double debit=-px;if(kind&&(debit<=0||debit>=W))continue;if(!kind&&px<.1*W*(cfg.strategy=="ic"?2:1))continue;
       double maxloss=(kind?debit:W-px)*MULT+.65*cfg.fee_mult*legs.size()*2;
       double byund=0,agg=0,coll=0;for(const auto&p:pos){if(p.und==u)byund+=p.max_loss*p.n;agg+=p.max_loss*p.n;if(!p.kind)coll+=p.width*MULT*p.n;}
       double cap=std::min({.005*eq,.02*eq-byund,.05*eq-agg});int n=cap>0?int(std::floor(cap/maxloss)):0;if(n<1)continue;
       double need=kind?debit*MULT*n:W*MULT*n;double reserve=.25*eq;if(!kind&&cash-coll-W*MULT*n+px*MULT*n<reserve)continue;if(kind&&cash-coll-need<reserve)continue;
       double entryfees=.65*cfg.fee_mult*legs.size()*n;cash+=px*MULT*n-entryfees;
       Position p; p.id=++next_id;p.und=u;p.n=n;p.kind=kind;p.legs=std::move(legs);p.entry_i=i;p.entry_date=d.date;p.signal_date=m.sessions[si].date;p.expiry=p.legs[0].k.expiry;p.open_px=px;p.width=W;p.max_loss=maxloss;p.entry_fees=entryfees;p.entry_spread=sc*MULT*n;p.last_cost=-px;pos.push_back(std::move(p));
     }
   }
   double liq=0;for(auto&p:pos){double cost=marked_cost(m,p,i);liq-=cost*MULT*p.n;double pnlps=p.open_px-cost;if(p.kind){double debit=-p.open_px;if(-cost>=debit*1.5)p.pending="take_profit";else if(-cost<=debit*.5)p.pending="stop";}else if(pnlps>=.5*p.open_px)p.pending="take_profit";else if(pnlps<=-2*p.open_px)p.pending="stop";}
   equity[i]=cash+liq;
 }
 for(int i=start;i<=end;++i){out.dates.push_back(m.sessions[i].date);out.returns.push_back(equity[i]/equity[i-1]-1.);}
 return out;
}
