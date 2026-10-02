// 在已有搜索器上加入规划硬固定、运输预留格及目标空矩形。
#include <bits/stdc++.h>
#include <unistd.h>
using namespace std;
const int W=70,N=4900,DX[4]={1,0,-1,0},DY[4]={0,1,0,-1};
struct Pin{int x,y,d,off;};
struct U{string name;int type,x,y,d,w,h;};
struct E{int s,t;};
struct Step{int c,i,o;};
struct Path{vector<Step> v;Pin s,t;};
vector<U> us;vector<E> es;vector<vector<int>> incident;vector<Path> paths;vector<vector<Pin>> inp,outp;
int occ[N],needin[400],needout[400],overlap=0;vector<int> heat[N];int use[N][2];double hist[N][2];
bool locked[400];int reserved[N];int reservation_overlap(){int v=0;for(int c=0;c<N;c++)if(reserved[c])v+=occ[c];return v;}
mt19937 rng;int seed;string pref;double ovweight=100,pinweight=15,heatweight=0;bool hardbody=false;double connweight=0;int disconnected=0;
auto tstart=chrono::steady_clock::now();double elapsed(){return chrono::duration<double>(chrono::steady_clock::now()-tstart).count();}
int ri(int n){return rng()%n;}double rf(){return (rng()+.5)/4294967296.;}bool in(int x,int y){return x>=0&&x<70&&y>=0&&y<70;}
void shape(U&u){if(u.type==0)u.w=u.h=3;else if(u.type==1)u.w=u.h=5;else if(u.type==2){u.w=u.d%2?6:4;u.h=u.d%2?4:6;}else if(u.type==3)u.w=u.h=9;else if(u.type==4){u.w=u.d==0?1:3;u.h=u.d==0?3:1;}else u.w=u.h=2;}
void change(U &u,int v){for(int y=u.y;y<u.y+u.h;y++)for(int x=u.x;x<u.x+u.w;x++){int c=y*70+x;overlap-=occ[c]*(occ[c]-1)/2;occ[c]+=v;overlap+=occ[c]*(occ[c]-1)/2;}}
void rebuild(){memset(occ,0,sizeof(occ));overlap=0;for(int y=14;y<20;y++)for(int x=63;x<69;x++)occ[y*70+x]=1;for(auto &u:us)change(u,1);}
vector<Pin> edge(const U&u,int d,const vector<int>&offs={}){vector<Pin> p;int n=d%2?u.w:u.h;for(int o=0;o<n;o++){if(!offs.empty()&&find(offs.begin(),offs.end(),o)==offs.end())continue;int x=d==0?u.x+u.w:d==2?u.x-1:u.x+o;int y=d==1?u.y+u.h:d==3?u.y-1:u.y+o;p.push_back({x,y,d,o});}return p;}
void pins(){for(int j=0;j<(int)us.size();j++){auto&u=us[j];inp[j].clear();outp[j].clear();if(u.type<=2){inp[j]=edge(u,u.d);outp[j]=edge(u,(u.d+2)%4);}else if(u.type==3){for(int d=0;d<4;d++){auto a=edge(u,d,d%2==u.d%2?vector<int>{1,2,3,4,5,6,7}:vector<int>{1,4,7});auto&v=d%2==u.d%2?inp[j]:outp[j];v.insert(v.end(),a.begin(),a.end());}}else if(u.type==4)outp[j]=edge(u,u.d,{1});}}
int block(const Pin&p){return in(p.x,p.y)?occ[p.y*70+p.x]:5;}
struct Stats{double score,wire,power,heat;int overlap,deficit;};
Stats fitness(){pins();double wire=0,power=0,ht=0;int def=0;
 static int comp[N],q[N];int ci=0;fill(comp,comp+N,-1);disconnected=0;
 if(connweight)for(int c=0;c<N;c++)if(!occ[c]&&comp[c]<0){int head=0,tail=0;comp[c]=ci;q[tail++]=c;while(head<tail){int a=q[head++],x=a%70,y=a/70;for(int d=0;d<4;d++){int xx=x+DX[d],yy=y+DY[d];if(!in(xx,yy))continue;int b=yy*70+xx;if(!occ[b]&&comp[b]<0){comp[b]=ci;q[tail++]=b;}}}ci++;}
for(int j=0;j<(int)us.size();j++)if(us[j].type<5){int a=0,b=0;for(auto&p:inp[j])a+=!block(p);for(auto&p:outp[j])b+=!block(p);def+=max(0,needin[j]-a)+max(0,needout[j]-b);}
 for(auto&e:es){double best=1e5;bool connected=false;for(auto&a:outp[e.s])for(auto&b:inp[e.t]){if(connweight&&in(a.x,a.y)&&in(b.x,b.y)&&!occ[a.y*70+a.x]&&!occ[b.y*70+b.x]&&comp[a.y*70+a.x]==comp[b.y*70+b.x])connected=true;int dist=abs(a.x-b.x)+abs(a.y-b.y)+1;if(dist==1 && ((a.d+2)%4)==((b.d+2)%4))dist+=4;double c=dist+min(block(a),3)*pinweight+min(block(b),3)*pinweight;best=min(best,c);}wire+=best;disconnected+=connweight&&!connected;}
 for(int j=0;j<230;j++){auto&u=us[j];int bd=999;for(int k=277;k<(int)us.size();k++){auto&p=us[k];int d=max({0,p.x-5-(u.x+u.w-1),u.x-p.x-6})+max({0,p.y-5-(u.y+u.h-1),u.y-p.y-6});bd=min(bd,d);}power+=bd;}
 if(heatweight)for(int j=0;j<(int)us.size();j++)if(us[j].type!=4){auto&u=us[j];for(int y=u.y;y<u.y+u.h;y++)for(int x=u.x;x<u.x+u.w;x++)for(int r:heat[y*70+x])if(es[r].s!=j&&es[r].t!=j)ht++;}
 return {ovweight*(overlap+reservation_overlap())+wire+pinweight*def+20*power+heatweight*ht+connweight*disconnected,wire,power,ht,overlap,def};}
void heatbuild(){for(int c=0;c<N;c++)heat[c].clear();for(int r=0;r<(int)paths.size();r++)for(auto&a:paths[r].v)heat[a.c].push_back(r);}
void save(string tag,Stats st){ofstream o(pref+"-"+tag+".json");o<<"{\"seed\":"<<seed<<",\"elapsed\":"<<elapsed()<<",\"score\":"<<st.score<<",\"overlap\":"<<(st.overlap+reservation_overlap())<<",\"deficit\":"<<st.deficit<<",\"disconnected\":"<<disconnected<<",\"wire\":"<<st.wire<<",\"power_distance\":"<<st.power<<",\"units\":[";for(int j=0;j<(int)us.size();j++){if(j)o<<",";auto&u=us[j];o<<"{\"id\":\""<<u.name<<"\",\"type\":"<<u.type<<",\"x\":"<<u.x<<",\"y\":"<<u.y<<",\"d\":"<<u.d<<",\"w\":"<<u.w<<",\"h\":"<<u.h<<"}";}o<<"],\"paths\":[";for(int r=0;r<(int)paths.size();r++){if(r)o<<",";auto&p=paths[r];o<<"{\"r\":"<<r<<",\"source\":["<<p.s.x<<","<<p.s.y<<","<<p.s.d<<","<<p.s.off<<"],\"target\":["<<p.t.x<<","<<p.t.y<<","<<p.t.d<<","<<p.t.off<<"],\"cells\":[";for(int i=0;i<(int)p.v.size();i++){if(i)o<<",";auto&a=p.v[i];o<<"["<<a.c%70<<","<<a.c/70<<","<<a.i<<","<<a.o<<"]";}o<<"]}";}o<<"]}\n";}
void init(){for(int j=0;j<(int)us.size();j++){auto&u=us[j];u.d=ri(4);shape(u);u.x=1+ri(70-u.w);u.y=1+ri(70-u.h);if(u.type==4){int k=j-231;int b=k<17?k+6:k<34?k-17+6:k<40?k-34:k-40;u.d=(k<17||k>=34&&k<40)?0:1;shape(u);u.x=u.d?1+3*b:0;u.y=u.d?0:1+3*b;}if(u.type==3){u.x=35;u.y=35;u.d=0;shape(u);}if(u.type==5){int k=j-277;u.x=6+(k%5)*13;u.y=6+(k/5)*13;}}
 rebuild();}
void clamp(U&u){u.x=max(1,min(70-u.w,u.x));u.y=max(1,min(70-u.h,u.y));}
long moves=0,accepted=0;double lastprint=0;vector<U> bestlegal;double bestlg=1e30;
void anneal(double secs,int phase){double until=elapsed()+secs;Stats cur=fitness();double bst=cur.score;vector<U> localbest=us;long k=0;double begin=elapsed();
 while(elapsed()<until){k++;moves++;
 if(overlap==0 && ri(100)<35){
  int j=ri(us.size());if(locked[j])continue;int dir=ri(4),dx=DX[dir],dy=DY[dir];
  vector<int> group{j};bool member[400]={};member[j]=true;bool valid=true;
  for(int qi=0;qi<(int)group.size()&&valid;qi++){int a=group[qi];auto &u=us[a];int x=u.x+dx,y=u.y+dy;
   if(x<1||y<1||x+u.w>70||y+u.h>70||(x<69&&x+u.w>63&&y<20&&y+u.h>14)){valid=false;break;}
   for(int z=0;z<(int)us.size();z++)if(!member[z]){auto &v=us[z];if(x<v.x+v.w&&x+u.w>v.x&&y<v.y+v.h&&y+u.h>v.y){if(locked[z]){valid=false;break;}member[z]=true;group.push_back(z);}}
  }
  if(!valid)continue;for(int a:group)change(us[a],-1);for(int a:group){us[a].x+=dx;us[a].y+=dy;change(us[a],1);}
  Stats ns=fitness();double f=(elapsed()-begin)/secs;double temp=(phase==0?12.:8.)*pow(.025,f)+.12;
  bool acc=ns.score<=cur.score||rf()<exp((cur.score-ns.score)/temp);
  if(acc){cur=ns;accepted++;if(cur.score<bst){bst=cur.score;localbest=us;}if(!overlap&&!reservation_overlap()&&cur.score<bestlg){bestlg=cur.score;bestlegal=us;save("bestplace",cur);}}
  else{for(int a:group)change(us[a],-1);for(int a:group){us[a].x-=dx;us[a].y-=dy;change(us[a],1);}}
  continue;
 }
 int j=ri(us.size());if(locked[j])continue;int q=-1;U old=us[j],oldq;change(us[j],-1);int mode=ri(100);
 if(mode<18){vector<int> qs;for(int z=0;z<(int)us.size();z++)if(z!=j&&!locked[z]&&us[z].type==us[j].type)qs.push_back(z);if(!qs.empty()){q=qs[ri(qs.size())];oldq=us[q];change(us[q],-1);swap(us[j].x,us[q].x);swap(us[j].y,us[q].y);if(us[j].type==2)swap(us[j].d,us[q].d);shape(us[j]);shape(us[q]);}}
 else if(mode<27){us[j].d=ri(4);shape(us[j]);}
 else if(mode<30&&!hardbody){us[j].x=1+ri(70-us[j].w);us[j].y=1+ri(70-us[j].h);}
 else{int d=ri(4),len=(mode<65?1:mode<90?2:1+ri(8));us[j].x+=DX[d]*len;us[j].y+=DY[d]*len;}
 clamp(us[j]);if(q>=0)clamp(us[q]);change(us[j],1);if(q>=0)change(us[q],1);
 bool acc=false;Stats ns;if(!hardbody||(overlap==0&&!reservation_overlap())){ns=fitness();double f=(elapsed()-begin)/secs;double temp=phase==0?(12.0*pow(.015,f)+.12):(8.0*pow(.025,f)+.08);if(hardbody)temp*=.55;acc=ns.score<=cur.score||rf()<exp((cur.score-ns.score)/temp);}
 if(acc){cur=ns;accepted++;if(cur.score<bst){bst=cur.score;localbest=us;}if(!overlap&&!reservation_overlap()&&cur.score<bestlg){bestlg=cur.score;bestlegal=us;save("bestplace",cur);}}
 else{change(us[j],-1);if(q>=0)change(us[q],-1);us[j]=old;if(q>=0)us[q]=oldq;change(us[j],1);if(q>=0)change(us[q],1);}
 if(elapsed()-lastprint>25){cur=fitness();cerr<<"place "<<seed<<" t="<<elapsed()<<" moves="<<moves<<" E="<<cur.score<<" ov="<<overlap<<" def="<<cur.deficit<<" wire="<<cur.wire<<" disconnected="<<disconnected<<" power="<<cur.power<<" heat="<<cur.heat<<"\n";save("latest",cur);lastprint=elapsed();}
 }
 us=localbest;rebuild();fitness();}
// Direction-state negotiated-congestion routing. Every route has its own chosen endpoint ports.
void usage(int r,int delta){for(auto&a:paths[r].v){int mask=(a.o==(a.i+2)%4)?1<<(a.i%2):3;for(int z=0;z<2;z++)if(mask&(1<<z))use[a.c][z]+=delta;}}
struct Node{double f,g;int state;bool operator<(Node const&a)const{return f>a.f;}};
Path route(int r,double present,double machineCost,bool hard){auto&e=es[r];vector<Pin> starts,goals;for(auto&a:outp[e.s])if(in(a.x,a.y)&&(!hard||!occ[a.y*70+a.x]))starts.push_back(a);for(auto&b:inp[e.t])if(in(b.x,b.y)&&(!hard||!occ[b.y*70+b.x]))goals.push_back(b);if(starts.empty()||goals.empty())return {};
 static double dist[N*4];static int prev[N*4],origin[N*4];fill(dist,dist+N*4,1e30);fill(prev,prev+N*4,-1);priority_queue<Node> pq;
 int gx0=70,gx1=-1,gy0=70,gy1=-1;for(auto&b:goals){gx0=min(gx0,b.x);gx1=max(gx1,b.x);gy0=min(gy0,b.y);gy1=max(gy1,b.y);}auto heur=[&](int x,int y){return max({0,gx0-x,x-gx1})+max({0,gy0-y,y-gy1});};
 for(int k=0;k<(int)starts.size();k++){auto&a=starts[k];int st=(a.y*70+a.x)*4+(a.d+2)%4;dist[st]=0;origin[st]=k;pq.push({double(heur(a.x,a.y)),0,st});}
 double best=1e30;int finish=-1,fo=-1,fg=-1;int expansions=0;
 while(!pq.empty()){auto n=pq.top();pq.pop();if(n.g!=dist[n.state])continue;if(n.f>=best)break;if(++expansions>40000)break;int c=n.state/4,ii=n.state%4,x=c%70,y=c/70;
  for(int o=0;o<4;o++){if(o==ii)continue;int mask=o==(ii+2)%4?1<<(ii%2):3;double cost=1+(mask==3?.15:0)+machineCost*occ[c];bool bad=false;for(int z=0;z<2;z++)if(mask&(1<<z)){if(hard&&use[c][z])bad=true;cost+=present*use[c][z]+hist[c][z];}if(bad)continue;double ng=n.g+cost;
   for(int k=0;k<(int)goals.size();k++){auto&b=goals[k];if(x==b.x&&y==b.y&&o==(b.d+2)%4&&ng<best){best=ng;finish=n.state;fo=o;fg=k;}}
   int xx=x+DX[o],yy=y+DY[o];if(!in(xx,yy))continue;int cc=yy*70+xx;if(hard&&occ[cc])continue;if(!hard&&occ[cc]>1&&machineCost>=1000)continue;int st=cc*4+(o+2)%4;if(ng<dist[st]){dist[st]=ng;prev[st]=n.state;origin[st]=origin[n.state];pq.push({ng+heur(xx,yy),ng,st});}
  }
 }
 if(finish<0)return {};Path p;p.s=starts[origin[finish]];p.t=goals[fg];int st=finish,o=fo;unordered_set<int> seen;
 while(true){int c=st/4;if(!seen.insert(c).second)return {};p.v.push_back({c,st%4,o});int ps=prev[st];if(ps<0)break;o=(st%4+2)%4;st=ps;}reverse(p.v.begin(),p.v.end());return p;
}
struct RS{int routed,blocked,conflict,length,physical;};
RS rstats(){int nr=0,b=0,k=0,len=0,phys=0;for(auto&p:paths){nr+=!p.v.empty();for(auto&a:p.v){b+=occ[a.c];len++;}}for(int c=0;c<N;c++){k+=max(0,use[c][0]-1)+max(0,use[c][1]-1);phys+=use[c][0]||use[c][1];}return {nr,b,k,len,phys};}
void router(int loops,double mc,bool hard=false){pins();memset(use,0,sizeof(use));for(int r=0;r<(int)es.size();r++)usage(r,1);vector<int> order(es.size());iota(order.begin(),order.end(),0);
 for(int it=0;it<loops;it++){shuffle(order.begin(),order.end(),rng);if(it%3==0)sort(order.begin(),order.end(),[&](int a,int b){return paths[a].v.size()<paths[b].v.size();});for(int r:order){usage(r,-1);paths[r]=route(r,hard?1000:2.+it*.6,mc,hard);usage(r,1);}auto st=rstats();if(!hard)for(int c=0;c<N;c++)for(int z=0;z<2;z++)hist[c][z]+=.04*max(0,use[c][z]-1);if(it==loops-1||it%10==0)cerr<<"route "<<seed<<" t="<<elapsed()<<" it="<<it<<" paths="<<st.routed<<" body="<<st.blocked<<" conflicts="<<st.conflict<<" len="<<st.length<<"\n";}
 heatbuild();}
// Accept a simple text resume to avoid introducing a JSON library.
void resume(string file){ifstream f(file);for(int j=0;j<(int)us.size();j++){int x,y,d;f>>x>>y>>d;if(!locked[j]){us[j].x=x;us[j].y=y;us[j].d=d;}}for(auto&u:us)shape(u);rebuild();}
void posfile(string tag){ofstream o(pref+"-"+tag+".pos");for(auto&u:us)o<<u.x<<" "<<u.y<<" "<<u.d<<"\n";}
bool protected_route[400];
void reusage(){memset(use,0,sizeof(use));for(int r=0;r<(int)es.size();r++)usage(r,1);}
void fixedpaths(string file){
 ifstream f(file);int nr;f>>nr;pins();
 for(int k=0,r,n;k<nr;k++){
  f>>r>>n;vector<int> cs;for(int j=0,x,y;j<n;j++){f>>x>>y;cs.push_back(y*70+x);}
  auto &p=paths[r];p={};bool a=false,b=false;
  for(auto q:outp[es[r].s])if(q.x==cs[0]%70&&q.y==cs[0]/70){p.s=q;a=true;break;}
  for(auto q:inp[es[r].t])if(q.x==cs.back()%70&&q.y==cs.back()/70){p.t=q;b=true;break;}
  if(!a||!b)throw runtime_error("保护进路端口不匹配");
  auto dir=[&](int a,int b){for(int d=0;d<4;d++)if(b%70-a%70==DX[d]&&b/70-a/70==DY[d])return d;throw runtime_error("不相邻");};
  for(int j=0;j<n;j++)p.v.push_back({cs[j],j?dir(cs[j],cs[j-1]):(p.s.d+2)%4,j+1<n?dir(cs[j],cs[j+1]):(p.t.d+2)%4});
  protected_route[r]=true;
 }
 reusage();
}
double actual_score(){
 auto z=fitness();auto r=rstats();double eq=0;int a=-1,b=-1;
 for(int j=0;j<(int)es.size();j++){if(us[es[j].s].name=="H6"&&us[es[j].t].name=="F4")a=j;if(us[es[j].s].name=="Q6"&&us[es[j].t].name=="F4")b=j;}
 if(a>=0&&b>=0&&!paths[a].v.empty()&&!paths[b].v.empty())eq=abs(int(paths[a].v.size())-int(paths[b].v.size()));
 return 2500.*(es.size()-r.routed)+r.length+z.power*400+z.deficit*3000+disconnected*5000+z.wire*.12+eq*5;
}
void hardroute(vector<int> order){
 for(int r:order){if(protected_route[r])continue;usage(r,-1);paths[r]=route(r,1000,10000,true);usage(r,1);}
}
int main(int argc,char**argv){
 ifstream f(argv[1]);int nu,ne,nr;f>>nu>>ne>>nr;us.resize(nu);
 for(int j=0;j<nu;j++){auto&u=us[j];f>>u.name>>u.type>>u.x>>u.y>>u.d>>locked[j];shape(u);}
 es.resize(ne);for(auto&e:es)f>>e.s>>e.t;
 for(int k=0,x,y;k<nr;k++){f>>x>>y;reserved[y*70+x]=1;}
 incident.resize(nu);inp.resize(nu);outp.resize(nu);paths.resize(ne);
 for(int r=0;r<ne;r++){auto&e=es[r];incident[e.s].push_back(r);incident[e.t].push_back(r);needout[e.s]++;needin[e.t]++;}
 seed=stoi(argv[2]);rng.seed(seed);pref=argv[3];double seconds=stod(argv[4]);rebuild();resume(argv[5]);
 if(overlap||reservation_overlap()){cerr<<"起始机身非法 "<<overlap<<" "<<reservation_overlap()<<"\n";return 2;}
 connweight=1;pinweight=0;heatweight=0;ovweight=1000;fixedpaths(argv[6]);
 for(int j=0;j<nu;j++)if(us[j].type==4){bool prot=false;for(int r:incident[j])prot|=protected_route[r];if(!prot)locked[j]=false;}
 if(argc>7){bool oldprot[400];copy(protected_route,protected_route+400,oldprot);resume(argv[5]);fixedpaths(argv[7]);copy(oldprot,oldprot+400,protected_route);}

 // 新增保护段可能与旧候选进路相碰；先保留保护段，再剔除冲突旧路。
 memset(use,0,sizeof(use));
 for(int pass=0;pass<2;pass++)for(int r=0;r<ne;r++)if(int(!protected_route[r])==pass){
  bool valid=true;set<int> seen;for(auto&a:paths[r].v){int mask=a.o==(a.i+2)%4?1<<(a.i%2):3;if(occ[a.c]||!seen.insert(a.c).second)valid=false;for(int z=0;z<2;z++)if((mask&(1<<z))&&use[a.c][z])valid=false;}
  if(!valid){if(protected_route[r])throw runtime_error("保护段彼此冲突");paths[r]={};}usage(r,1);
 }
 vector<int> order(ne);iota(order.begin(),order.end(),0);
 auto seedpaths=paths;int seednr=rstats().routed;for(int k=0;k<12;k++){shuffle(order.begin(),order.end(),rng);hardroute(order);if(rstats().routed>seednr){seednr=rstats().routed;seedpaths=paths;}}paths=seedpaths;reusage();
 double cur=actual_score(),best=cur;auto bestus=us;auto bestpaths=paths;int bestnr=rstats().routed;
 save("best",fitness());posfile("best");long trials=0,accept=0;double lastsave=0,lastlog=0;
 while(elapsed()<seconds){
  trials++;auto oldus=us;auto oldpaths=paths;vector<int> missing;for(int r=0;r<ne;r++)if(paths[r].v.empty())missing.push_back(r);
  vector<int> affected;
  if(ri(100)<72){
   int j=ri(nu);
   if(!missing.empty()&&ri(100)<80){
    int r=missing[ri(missing.size())];j=ri(2)?es[r].s:es[r].t;
    if(locked[j]||ri(100)<35){
     auto probe=route(r,3,12,false);vector<int> candidates;
     for(auto st:probe.v)for(int a=0;a<nu;a++)if(!locked[a]){auto&u=us[a];int x=st.c%70,y=st.c/70;if(x>=u.x&&x<u.x+u.w&&y>=u.y&&y<u.y+u.h)candidates.push_back(a);}
     if(!candidates.empty())j=candidates[ri(candidates.size())];
    }
   }
   if(locked[j])continue;vector<int> changed{j};int mode=ri(100);
   if(us[j].type==4){
    vector<int> cand;for(int a=0;a<nu;a++)if(a!=j&&!locked[a]&&us[a].type==4)cand.push_back(a);if(cand.empty())continue;int q=cand[ri(cand.size())];changed.push_back(q);
    swap(us[j].x,us[q].x);swap(us[j].y,us[q].y);swap(us[j].d,us[q].d);shape(us[j]);shape(us[q]);
   }else if(mode<15&&us[j].type==1){
    string id=us[j].name;char typ=id[0];int num=stoi(id.substr(2));char typ2=ri(2)?'S':'Q';int num2=1+ri(typ2=='S'?13:6);if(typ==typ2&&num==num2)continue;
    changed.clear();vector<char> roles=ri(3)?vector<char>{'C','A','B'}:vector<char>{'C','A'};bool ok=true;
    for(char role:roles){string a=string(1,typ)+role+to_string(num),b=string(1,typ2)+role+to_string(num2);int ai=-1,bi=-1;for(int z=0;z<nu;z++){if(us[z].name==a)ai=z;if(us[z].name==b)bi=z;}if(ai<0||bi<0||locked[ai]||locked[bi]){ok=false;break;}changed.push_back(ai);changed.push_back(bi);swap(us[ai].x,us[bi].x);swap(us[ai].y,us[bi].y);swap(us[ai].d,us[bi].d);}
    if(!ok){us=oldus;continue;}
   }else if(mode<23&&us[j].type==1){
    string id=us[j].name;string other=id;other[1]=id[1]=='A'?'C':'A';int q=-1;for(int z=0;z<nu;z++)if(us[z].name==other)q=z;
    if(q<0||locked[q])continue;changed.push_back(q);us[j].d=ri(4);us[q].d=ri(4);
   }else if(mode<25){vector<int> cand;for(int a=0;a<nu;a++)if(a!=j&&!locked[a]&&us[a].type==us[j].type&&(abs(us[a].x-us[j].x)+abs(us[a].y-us[j].y)<25||mode<4))cand.push_back(a);if(cand.empty())continue;int q=cand[ri(cand.size())];changed.push_back(q);swap(us[j].x,us[q].x);swap(us[j].y,us[q].y);if(us[j].type==2)swap(us[j].d,us[q].d);shape(us[j]);shape(us[q]);}
   else if(mode<43){us[j].d=ri(us[j].type==5?1:4);shape(us[j]);}
   else if(mode<75){int d=ri(4),n=1+ri(4);us[j].x+=DX[d]*n;us[j].y+=DY[d]*n;}
   else{
    int d=ri(4),dx=DX[d],dy=DY[d];bool member[400]={};member[j]=true;bool valid=true;
    for(int k=0;k<(int)changed.size()&&valid;k++){auto &u=us[changed[k]];int x=u.x+dx,y=u.y+dy;if(x<1||y<1||x+u.w>70||y+u.h>70){valid=false;break;}for(int a=0;a<nu;a++)if(!member[a]){auto&v=us[a];if(x<v.x+v.w&&x+u.w>v.x&&y<v.y+v.h&&y+u.h>v.y){if(locked[a]){valid=false;break;}member[a]=true;changed.push_back(a);}}}
    if(!valid){us=oldus;continue;}for(int a:changed){us[a].x+=dx;us[a].y+=dy;}
   }
   bool valid=true;for(int a:changed){auto&u=us[a];if((u.type!=4&&(u.x<1||u.y<1))||u.x<0||u.y<0||u.x+u.w>70||u.y+u.h>70)valid=false;}
   if(!valid){us=oldus;continue;}rebuild();
   if(overlap||reservation_overlap()){us=oldus;rebuild();continue;}
   bool af[400]={};for(int a:changed)for(int r:incident[a])af[r]=true;
   for(int r=0;r<ne;r++)for(auto st:paths[r].v)if(occ[st.c])af[r]=true;
   for(int r=0;r<ne;r++)if(af[r]&&!protected_route[r])affected.push_back(r);
  }else if(!missing.empty()){
   int r=missing[ri(missing.size())];auto probe=route(r,2,10000,false);bool af[400]={};af[r]=true;
   for(auto st:probe.v)for(int q=0;q<ne;q++)if(!protected_route[q])for(auto z:paths[q].v)if(z.c==st.c){af[q]=true;break;}
   for(int q=0;q<ne;q++)if(af[q])affected.push_back(q);
  }else{for(int k=0;k<1+ri(10);k++)affected.push_back(ri(ne));}
  for(int r:affected)if(!protected_route[r])paths[r]={};reusage();pins();
  affected.insert(affected.end(),missing.begin(),missing.end());sort(affected.begin(),affected.end());affected.erase(unique(affected.begin(),affected.end()),affected.end());shuffle(affected.begin(),affected.end(),rng);hardroute(affected);
  double now=actual_score();double phase=fmod(elapsed(),180.)/180.;double temp=900*pow(.03,phase)+3;
  bool acc=now<=cur||rf()<exp((cur-now)/temp);
  if(acc){cur=now;accept++;if(cur<best){best=cur;bestus=us;bestpaths=paths;auto rs=rstats();if(rs.routed>bestnr||elapsed()-lastsave>5){save("best",fitness());posfile("best");lastsave=elapsed();}bestnr=max(bestnr,rs.routed);}}
  else{us=oldus;paths=oldpaths;rebuild();reusage();pins();}
  if(elapsed()-lastlog>30){auto rs=rstats();cerr<<"direct seed="<<seed<<" t="<<elapsed()<<" trials="<<trials<<" accept="<<accept<<" routed="<<rs.routed<<" bestscore="<<best<<" bestnr="<<bestnr<<" length="<<rs.length<<" score="<<cur<<"\n";save("latest",fitness());lastlog=elapsed();}
  if(missing.empty()){auto zz=fitness();if(zz.power==0&&zz.deficit==0){save("complete-routes",zz);posfile("complete-routes");}}
  if(trials%71==0&&cur>best+6000){us=bestus;paths=bestpaths;rebuild();reusage();pins();cur=best;}
 }
 us=bestus;paths=bestpaths;rebuild();reusage();pins();save("best",fitness());posfile("best");cerr<<"final routes="<<rstats().routed<<" score="<<actual_score()<<"\n";return 0;
}
