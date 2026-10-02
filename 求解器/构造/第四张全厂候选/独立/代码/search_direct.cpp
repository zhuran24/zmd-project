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
mt19937 rng;int seed;string pref;double ovweight=100,pinweight=15,heatweight=0;bool hardbody=false;double connweight=0;int disconnected=0;
auto tstart=chrono::steady_clock::now();double elapsed(){return chrono::duration<double>(chrono::steady_clock::now()-tstart).count();}
int ri(int n){return rng()%n;}double rf(){return (rng()+.5)/4294967296.;}bool in(int x,int y){return x>=0&&x<70&&y>=0&&y<70;}
void shape(U&u){if(u.type==0)u.w=u.h=3;else if(u.type==1)u.w=u.h=5;else if(u.type==2){u.w=u.d%2?6:4;u.h=u.d%2?4:6;}else if(u.type==3)u.w=u.h=9;else if(u.type==4){u.w=u.d==0?1:3;u.h=u.d==0?3:1;}else u.w=u.h=2;}
void change(U &u,int v){for(int y=u.y;y<u.y+u.h;y++)for(int x=u.x;x<u.x+u.w;x++){int c=y*70+x;overlap-=occ[c]*(occ[c]-1)/2;occ[c]+=v;overlap+=occ[c]*(occ[c]-1)/2;}}
void rebuild(){memset(occ,0,sizeof(occ));overlap=0;for(int y=64;y<70;y++)for(int x=64;x<70;x++)occ[y*70+x]=1;for(auto &u:us)change(u,1);}
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
 return {ovweight*overlap+wire+pinweight*def+20*power+heatweight*ht+connweight*disconnected,wire,power,ht,overlap,def};}
void heatbuild(){for(int c=0;c<N;c++)heat[c].clear();for(int r=0;r<(int)paths.size();r++)for(auto&a:paths[r].v){heat[a.c].push_back(r);int mask=a.o==(a.i+2)%4?1<<(a.i%2):3;for(int axis=0;axis<2;axis++)if((mask&(1<<axis))&&use[a.c][axis]>1)for(int d=1-axis;d<4;d+=2){int x=a.c%70+DX[d],y=a.c/70+DY[d];if(in(x,y)){heat[y*70+x].push_back(r);heat[y*70+x].push_back(r);}}}}
void save(string tag,Stats st){ofstream o(pref+"-"+tag+".json");o<<"{\"seed\":"<<seed<<",\"elapsed\":"<<elapsed()<<",\"score\":"<<st.score<<",\"overlap\":"<<st.overlap<<",\"deficit\":"<<st.deficit<<",\"wire\":"<<st.wire<<",\"power_distance\":"<<st.power<<",\"units\":[";for(int j=0;j<(int)us.size();j++){if(j)o<<",";auto&u=us[j];o<<"{\"id\":\""<<u.name<<"\",\"type\":"<<u.type<<",\"x\":"<<u.x<<",\"y\":"<<u.y<<",\"d\":"<<u.d<<",\"w\":"<<u.w<<",\"h\":"<<u.h<<"}";}o<<"],\"paths\":[";for(int r=0;r<(int)paths.size();r++){if(r)o<<",";auto&p=paths[r];o<<"{\"r\":"<<r<<",\"source\":["<<p.s.x<<","<<p.s.y<<","<<p.s.d<<","<<p.s.off<<"],\"target\":["<<p.t.x<<","<<p.t.y<<","<<p.t.d<<","<<p.t.off<<"],\"cells\":[";for(int i=0;i<(int)p.v.size();i++){if(i)o<<",";auto&a=p.v[i];o<<"["<<a.c%70<<","<<a.c/70<<","<<a.i<<","<<a.o<<"]";}o<<"]}";}o<<"]}\n";}
void init(){for(int j=0;j<(int)us.size();j++){auto&u=us[j];u.d=ri(4);shape(u);u.x=1+ri(70-u.w);u.y=1+ri(70-u.h);if(u.type==4){int k=j-231;int b=k<17?k+6:k<34?k-17+6:k<40?k-34:k-40;u.d=(k<17||k>=34&&k<40)?0:1;shape(u);u.x=u.d?1+3*b:0;u.y=u.d?0:1+3*b;}if(u.type==3){u.x=35;u.y=35;u.d=0;shape(u);}if(u.type==5){int k=j-277;u.x=6+(k%5)*13;u.y=6+(k/5)*13;}}
 rebuild();}
void clamp(U&u){u.x=max(1,min(70-u.w,u.x));u.y=max(1,min(70-u.h,u.y));}
long moves=0,accepted=0;double lastprint=0;vector<U> bestlegal;double bestlg=1e30;
void anneal(double secs,int phase){double until=elapsed()+secs;Stats cur=fitness();double bst=cur.score;vector<U> localbest=us;long k=0;double begin=elapsed();
 while(elapsed()<until){k++;moves++;
 if(overlap==0 && ri(100)<35){
  int j=ri(us.size());if(us[j].type==4)continue;int dir=ri(4),dx=DX[dir],dy=DY[dir];
  vector<int> group{j};bool member[400]={};member[j]=true;bool valid=true;
  for(int qi=0;qi<(int)group.size()&&valid;qi++){int a=group[qi];auto &u=us[a];int x=u.x+dx,y=u.y+dy;
   if(x<1||y<1||x+u.w>70||y+u.h>70||(x+u.w>64&&y+u.h>64)){valid=false;break;}
   for(int z=0;z<(int)us.size();z++)if(!member[z]){auto &v=us[z];if(x<v.x+v.w&&x+u.w>v.x&&y<v.y+v.h&&y+u.h>v.y){if(v.type==4){valid=false;break;}member[z]=true;group.push_back(z);}}
  }
  if(!valid)continue;for(int a:group)change(us[a],-1);for(int a:group){us[a].x+=dx;us[a].y+=dy;change(us[a],1);}
  Stats ns=fitness();double f=(elapsed()-begin)/secs;double temp=(phase==0?12.:8.)*pow(.025,f)+.12;
  bool acc=ns.score<=cur.score||rf()<exp((cur.score-ns.score)/temp);
  if(acc){cur=ns;accepted++;if(cur.score<bst){bst=cur.score;localbest=us;}if(!overlap&&cur.score<bestlg){bestlg=cur.score;bestlegal=us;save("bestplace",cur);}}
  else{for(int a:group)change(us[a],-1);for(int a:group){us[a].x-=dx;us[a].y-=dy;change(us[a],1);}}
  continue;
 }
 int j=ri(us.size());if(us[j].type==4)continue;int q=-1;U old=us[j],oldq;change(us[j],-1);int mode=ri(100);
 if(mode<18){vector<int> qs;for(int z=0;z<(int)us.size();z++)if(z!=j&&us[z].type==us[j].type)qs.push_back(z);if(!qs.empty()){q=qs[ri(qs.size())];oldq=us[q];change(us[q],-1);swap(us[j].x,us[q].x);swap(us[j].y,us[q].y);if(us[j].type==2)swap(us[j].d,us[q].d);shape(us[j]);shape(us[q]);}}
 else if(mode<27){us[j].d=ri(4);shape(us[j]);}
 else if(mode<30&&!hardbody){us[j].x=1+ri(70-us[j].w);us[j].y=1+ri(70-us[j].h);}
 else{int d=ri(4),len=(mode<65?1:mode<90?2:1+ri(8));us[j].x+=DX[d]*len;us[j].y+=DY[d]*len;}
 clamp(us[j]);if(q>=0)clamp(us[q]);change(us[j],1);if(q>=0)change(us[q],1);
 bool acc=false;Stats ns;if(!hardbody||overlap==0){ns=fitness();double f=(elapsed()-begin)/secs;double temp=phase==0?(12.0*pow(.015,f)+.12):(8.0*pow(.025,f)+.08);if(hardbody)temp*=.55;acc=ns.score<=cur.score||rf()<exp((cur.score-ns.score)/temp);}
 if(acc){cur=ns;accepted++;if(cur.score<bst){bst=cur.score;localbest=us;}if(!overlap&&cur.score<bestlg){bestlg=cur.score;bestlegal=us;save("bestplace",cur);}}
 else{change(us[j],-1);if(q>=0)change(us[q],-1);us[j]=old;if(q>=0)us[q]=oldq;change(us[j],1);if(q>=0)change(us[q],1);}
 if(elapsed()-lastprint>25){cur=fitness();cerr<<"place "<<seed<<" t="<<elapsed()<<" moves="<<moves<<" E="<<cur.score<<" ov="<<overlap<<" def="<<cur.deficit<<" wire="<<cur.wire<<" disconnected="<<disconnected<<" power="<<cur.power<<" heat="<<cur.heat<<"\n";save("latest",cur);lastprint=elapsed();}
 }
 us=localbest;rebuild();fitness();}
// Direction-state negotiated-congestion routing. Every route has its own chosen endpoint ports.
void usage(int r,int delta){for(auto&a:paths[r].v){int mask=(a.o==(a.i+2)%4)?1<<(a.i%2):3;for(int z=0;z<2;z++)if(mask&(1<<z))use[a.c][z]+=delta;}}
struct Node{double f,g;int state;bool operator<(Node const&a)const{return f>a.f;}};
Path route(int r,double present,double machineCost,int mode){bool hard=mode>0;auto&e=es[r];vector<Pin> starts,goals;for(auto&a:outp[e.s])if(in(a.x,a.y)&&(!hard||!occ[a.y*70+a.x]))starts.push_back(a);for(auto&b:inp[e.t])if(in(b.x,b.y)&&(!hard||!occ[b.y*70+b.x]))goals.push_back(b);if(starts.empty()||goals.empty())return {};
 static double dist[N*4];static int prev[N*4],origin[N*4];fill(dist,dist+N*4,1e30);fill(prev,prev+N*4,-1);priority_queue<Node> pq;
 int gx0=70,gx1=-1,gy0=70,gy1=-1;for(auto&b:goals){gx0=min(gx0,b.x);gx1=max(gx1,b.x);gy0=min(gy0,b.y);gy1=max(gy1,b.y);}auto heur=[&](int x,int y){return max({0,gx0-x,x-gx1})+max({0,gy0-y,y-gy1});};
 for(int k=0;k<(int)starts.size();k++){auto&a=starts[k];int st=(a.y*70+a.x)*4+(a.d+2)%4;dist[st]=0;origin[st]=k;pq.push({double(heur(a.x,a.y)),0,st});}
 double best=1e30;int finish=-1,fo=-1,fg=-1;int expansions=0;
 while(!pq.empty()){auto n=pq.top();pq.pop();if(n.g!=dist[n.state])continue;if(n.f>=best)break;if(++expansions>40000)break;int c=n.state/4,ii=n.state%4,x=c%70,y=c/70;
  for(int o=0;o<4;o++){if(o==ii)continue;int mask=o==(ii+2)%4?1<<(ii%2):3;double cost=1+(mask==3?.15:0)+machineCost*occ[c];bool bad=false;for(int z=0;z<2;z++)if(mask&(1<<z)){if(mode==1&&use[c][z])bad=true;cost+=present*use[c][z]+hist[c][z];}if(bad)continue;double ng=n.g+cost;
   for(int k=0;k<(int)goals.size();k++){auto&b=goals[k];if(x==b.x&&y==b.y&&o==(b.d+2)%4&&ng<best){best=ng;finish=n.state;fo=o;fg=k;}}
   int xx=x+DX[o],yy=y+DY[o];if(!in(xx,yy))continue;int cc=yy*70+xx;if(hard&&occ[cc])continue;if(!hard&&occ[cc]>1&&machineCost>=1000)continue;int st=cc*4+(o+2)%4;if(ng<dist[st]){dist[st]=ng;prev[st]=n.state;origin[st]=origin[n.state];pq.push({ng+heur(xx,yy),ng,st});}
  }
 }
 if(finish<0)return {};Path p;p.s=starts[origin[finish]];p.t=goals[fg];int st=finish,o=fo;unordered_set<int> seen;
 while(true){int c=st/4;if(!seen.insert(c).second)return {};p.v.push_back({c,st%4,o});int ps=prev[st];if(ps<0)break;o=(st%4+2)%4;st=ps;}reverse(p.v.begin(),p.v.end());return p;
}
struct RS{int routed,blocked,conflict,length,physical;};
RS rstats(){int nr=0,b=0,k=0,len=0,phys=0;for(auto&p:paths){nr+=!p.v.empty();for(auto&a:p.v){b+=occ[a.c];len++;}}for(int c=0;c<N;c++){k+=max(0,use[c][0]-1)+max(0,use[c][1]-1);phys+=use[c][0]||use[c][1];}return {nr,b,k,len,phys};}
void router(int loops,double mc,int mode=0){bool hard=mode==1;pins();memset(use,0,sizeof(use));for(int r=0;r<(int)es.size();r++)usage(r,1);vector<int> order(es.size());iota(order.begin(),order.end(),0);
 for(int it=0;it<loops;it++){shuffle(order.begin(),order.end(),rng);if(it%3==0)sort(order.begin(),order.end(),[&](int a,int b){return paths[a].v.size()<paths[b].v.size();});for(int r:order){usage(r,-1);paths[r]=route(r,hard?1000:2.+it*.6,mc,mode);usage(r,1);}auto st=rstats();if(!hard)for(int c=0;c<N;c++)for(int z=0;z<2;z++)hist[c][z]+=.04*max(0,use[c][z]-1);if(it==loops-1||it%10==0)cerr<<"route "<<seed<<" t="<<elapsed()<<" it="<<it<<" paths="<<st.routed<<" body="<<st.blocked<<" conflicts="<<st.conflict<<" len="<<st.length<<"\n";}
 heatbuild();}
// Accept a simple text resume to avoid introducing a JSON library.
void resume(string file){ifstream f(file);for(auto&u:us)f>>u.x>>u.y>>u.d;for(auto&u:us)shape(u);rebuild();}
void posfile(string tag){ofstream o(pref+"-"+tag+".pos");for(auto&u:us)o<<u.x<<" "<<u.y<<" "<<u.d<<"\n";}

vector<double> priorityNet;bool fixedPower=false;
Stats directEval(){heatweight=0;connweight=1;pinweight=5;auto st=fitness();vector<int> order(es.size());iota(order.begin(),order.end(),0);vector<double> dd(es.size());
 for(int r:order){auto&e=es[r];double z=999;for(auto&a:outp[e.s])for(auto&b:inp[e.t])z=min(z,double(abs(a.x-b.x)+abs(a.y-b.y)));dd[r]=z+priorityNet[r];}
 sort(order.begin(),order.end(),[&](int a,int b){return dd[a]<dd[b];});for(auto&p:paths)p.v.clear();memset(use,0,sizeof(use));memset(hist,0,sizeof(hist));
 for(int r:order){paths[r]=route(r,1000,10000,1);usage(r,1);}
 // Revisit failed nets first, followed by the shortest successful nets.
 auto first=paths;auto best=rstats();sort(order.begin(),order.end(),[&](int a,int b){int aa=paths[a].v.empty()?0:1,bb=paths[b].v.empty()?0:1;return aa!=bb?aa<bb:dd[a]<dd[b];});
 for(int r:order){usage(r,-1);paths[r]=route(r,1000,10000,1);usage(r,1);}auto second=rstats();if(second.routed<best.routed||(second.routed==best.routed&&second.physical>best.physical)){paths=first;best=best;}else best=second;
 st.score=100*(325-best.routed)+100*st.power+8*st.deficit+2*disconnected+.04*st.wire+.015*best.physical;return st;
}
bool movable(int j){return us[j].type!=4&&(!fixedPower||us[j].type!=5);}
bool propose(vector<pair<int,U>>&old){
 int j=ri(us.size());if(ri(100)<60){vector<int> fail;for(int r=0;r<(int)paths.size();r++)if(paths[r].v.empty())fail.push_back(r);if(!fail.empty()){auto&e=es[fail[ri(fail.size())]];j=ri(2)?e.s:e.t;if(ri(100)<40){auto&a=ri(2)?outp[e.s]:inp[e.t];if(!a.empty()){auto p=a[ri(a.size())];for(int z=0;z<(int)us.size();z++)if(p.x>=us[z].x&&p.x<us[z].x+us[z].w&&p.y>=us[z].y&&p.y<us[z].y+us[z].h){j=z;break;}}}}}
 if(!movable(j))return false;int mode=ri(100);if(mode<40){int di=ri(4),dx=DX[di],dy=DY[di];vector<int> group{j};bool mem[400]={};mem[j]=true;
  for(int qi=0;qi<(int)group.size();qi++){auto&u=us[group[qi]];int x=u.x+dx,y=u.y+dy;if(x<1||y<1||x+u.w>70||y+u.h>70||(x+u.w>64&&y+u.h>64))return false;
   for(int z=0;z<(int)us.size();z++)if(!mem[z]){auto&v=us[z];if(x<v.x+v.w&&x+u.w>v.x&&y<v.y+v.h&&y+u.h>v.y){if(!movable(z))return false;mem[z]=true;group.push_back(z);}}}
  for(int a:group){old.push_back({a,us[a]});change(us[a],-1);}for(int a:group){us[a].x+=dx;us[a].y+=dy;change(us[a],1);}return overlap==0;
 }
 old.push_back({j,us[j]});change(us[j],-1);
 if(mode<73){vector<int> opts;for(int z=0;z<(int)us.size();z++)if(z!=j&&us[z].type==us[j].type&&movable(z))opts.push_back(z);if(opts.empty()){change(us[j],1);old.clear();return false;}int q=opts[ri(opts.size())];old.push_back({q,us[q]});change(us[q],-1);swap(us[j].x,us[q].x);swap(us[j].y,us[q].y);if(us[j].type==2)swap(us[j].d,us[q].d);shape(us[j]);shape(us[q]);change(us[q],1);}
 else if(mode<85){us[j].d=ri(4);shape(us[j]);clamp(us[j]);}
 else{int d=ri(4);int len=ri(100)<80?1:1+ri(6);us[j].x+=DX[d]*len;us[j].y+=DY[d]*len;clamp(us[j]);}
 change(us[j],1);return overlap==0;
}
void undo(vector<pair<int,U>>&old){for(auto&a:old)change(us[a.first],-1);for(auto&a:old){us[a.first]=a.second;change(us[a.first],1);}}
int main(int argc,char**argv){ifstream f(argv[1]);int nu,ne;f>>nu>>ne;us.resize(nu);for(auto&u:us)f>>u.name>>u.type;es.resize(ne);for(auto&e:es)f>>e.s>>e.t;incident.resize(nu);inp.resize(nu);outp.resize(nu);paths.resize(ne);for(int r=0;r<ne;r++){auto&e=es[r];incident[e.s].push_back(r);incident[e.t].push_back(r);needout[e.s]++;needin[e.t]++;}seed=stoi(argv[2]);rng.seed(seed);pref=argv[3];double seconds=stod(argv[4]);init();resume(argv[5]);fixedPower=argc>6&&string(argv[6])=="fixed";if(overlap){cerr<<"Input overlaps: "<<overlap<<"\n";return 2;}priorityNet.resize(ne);for(auto&a:priorityNet)a=rf()*4;
 auto cur=directEval();auto bestscore=cur.score;auto bestcoords=us;auto bestpaths=paths;double lastsave=0;int outer=0;long validmoves=0;int bestn=rstats().routed;
 while(elapsed()<seconds){vector<pair<int,U>> old;auto savedPaths=paths;bool ok=propose(old);moves++;if(!ok){if(!old.empty())undo(old);continue;}validmoves++;auto ns=directEval();double frac=fmod(elapsed(),90.)/90.;double temp=45*pow(.018,frac)+.3;bool acc=ns.score<=cur.score||rf()<exp((cur.score-ns.score)/temp);
  if(acc){cur=ns;accepted++;if(cur.score<bestscore){bestscore=cur.score;bestcoords=us;bestpaths=paths;save("best",cur);posfile("best");}auto rs=rstats();if(rs.routed>bestn){bestn=rs.routed;save("maxroutes",cur);posfile("maxroutes");}}
  else{undo(old);paths=savedPaths;pins();}
  if(elapsed()-lastsave>=30){cur=fitness();auto rs=rstats();cerr<<"DIRECT "<<seed<<" t="<<elapsed()<<" valid="<<validmoves<<" accepted="<<accepted<<" routed="<<rs.routed<<" best="<<bestn<<" connmiss="<<disconnected<<" deficit="<<cur.deficit<<" power="<<cur.power<<" wire="<<cur.wire<<"\n";cur=directEval();save("legal-"+to_string(outer),cur);posfile("iteration-"+to_string(outer));outer++;lastsave=elapsed();}
 }
 us=bestcoords;paths=bestpaths;rebuild();save("final",fitness());posfile("final");return 0;
}
