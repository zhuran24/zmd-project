#include <algorithm>
#include <array>
#include <bitset>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <random>
#include <string>
#include <vector>
using namespace std;
struct Unit {string id; int kind,movable,x,y,d,w,h;};
struct Edge {int a,b,weight;};
struct Ports {vector<int> in,out;int deficit=0;};
int dx[4]={1,0,-1,0},dy[4]={0,1,0,-1};
vector<Unit> us;vector<Edge> es;vector<vector<int>> incident;vector<int> incoming,outgoing,movable;
array<int,4900> grid,forbid,trin,trout,comp;vector<Ports> ps;vector<int> ec;
void shape(Unit&u){if(u.kind==0)u.w=u.h=3;else if(u.kind==1)u.w=u.h=5;else if(u.kind==2){u.w=u.d%2?6:4;u.h=u.d%2?4:6;}else if(u.kind==3){u.w=u.d==0?1:3;u.h=u.d==0?3:1;}else u.w=u.h=9;}
bool inside(int x,int y){return x>=0&&x<70&&y>=0&&y<70;}
void place(int i,int val){auto&u=us[i];for(int y=u.y;y<u.y+u.h;y++)for(int x=u.x;x<u.x+u.w;x++)grid[y*70+x]=val;}
bool legal(int i){auto&u=us[i];if(!inside(u.x,u.y)||!inside(u.x+u.w-1,u.y+u.h-1))return false;for(int y=u.y;y<u.y+u.h;y++)for(int x=u.x;x<u.x+u.w;x++){int c=y*70+x;if(grid[c]!=-1||forbid[c])return false;}return true;}
void port(vector<int>&v,const Unit&u,int d,int off,bool inbound){int x=u.x,y=u.y;if(d==0){x+=u.w-1;y+=off;}else if(d==2)y+=off;else if(d==1){x+=off;y+=u.h-1;}else x+=off;x+=dx[d];y+=dy[d];if(!inside(x,y))return;int c=y*70+x;if(grid[c]!=-1||forbid[c]==2)return;
 // An existing straight belt may become a crossing. A corner can only serve its existing adjacent unit.
 if(trin[c]>=0){int toward=(d+2)%4;bool attached=inbound?(trout[c]==toward):(trin[c]==toward);bool cross=((trin[c]+2)%4==trout[c]&&trin[c]%2!=d%2);if(!attached&&!cross)return;}
 v.push_back(c);}
Ports calcports(int i){auto&u=us[i];Ports p;
 if(u.kind<=2){int n=u.d%2?u.w:u.h;for(int o=0;o<n;o++){port(p.in,u,u.d,o,true);port(p.out,u,(u.d+2)%4,o,false);}}
 else if(u.kind==3)port(p.out,u,u.d,1,false);
 else {for(int d=0;d<4;d++){if(d%2==u.d%2){for(int o=1;o<=7;o++)port(p.in,u,d,o,true);}else for(int o:{1,4,7})port(p.out,u,d,o,false);}}
 p.deficit=max(0,incoming[i]-(int)p.in.size())+max(0,outgoing[i]-(int)p.out.size());return p;}
void components(){comp.fill(-1);int col=0;array<int,4900>q;for(int c=0;c<4900;c++){if(grid[c]!=-1||forbid[c]==2||comp[c]>=0)continue;int head=0,tail=0;q[tail++]=c;comp[c]=col;while(head<tail){int u=q[head++],x=u%70,y=u/70;for(int d=0;d<4;d++){int xx=x+dx[d],yy=y+dy[d];if(!inside(xx,yy))continue;int v=yy*70+xx;if(grid[v]==-1&&forbid[v]!=2&&comp[v]<0){comp[v]=col;q[tail++]=v;}}}col++;}}
int edgecost(int e){auto&a=ps[es[e].a].out;auto&b=ps[es[e].b].in;if(a.empty()||b.empty())return 2000*es[e].weight;int best=5000,fallback=5000;for(int x:a)for(int y:b){int md=abs(x%70-y%70)+abs(x/70-y/70)+1;fallback=min(fallback,md);if(comp[x]==comp[y])best=min(best,md);}return (best==5000?1500+fallback:best)*es[e].weight;}
void gather(int i,bitset<300>&a){auto&u=us[i];a[i]=1;for(int y=max(0,u.y-1);y<=min(69,u.y+u.h);y++)for(int x=max(0,u.x-1);x<=min(69,u.x+u.w);x++){int j=grid[y*70+x];if(j>=0)a[j]=1;}}
void writebest(const string&path,const vector<Unit>&best,long long score,long long iter,double sec,int seed){ofstream o(path);o<<"{\"score\":"<<score<<",\"iterations\":"<<iter<<",\"seconds\":"<<sec<<",\"seed\":"<<seed<<",\"units\":[";for(int i=0;i<(int)best.size();i++){if(i)o<<',';auto&u=best[i];o<<"{\"id\":\""<<u.id<<"\",\"x\":"<<u.x<<",\"y\":"<<u.y<<",\"Din\":"<<u.d<<"}";}o<<"]}\n";}
int main(int argc,char**argv){if(argc<5)return 2;ifstream in(argv[1]);string out=argv[2];int seed=stoi(argv[3]);double limit=stod(argv[4]);mt19937 rng(seed);uniform_real_distribution<double>rand01(0,1);int n,m,nt;in>>n>>m>>nt;us.resize(n);incoming.assign(n,0);outgoing.assign(n,0);incident.resize(n);ps.resize(n);grid.fill(-1);forbid.fill(0);trin.fill(-1);trout.fill(-1);
 for(int i=0;i<n;i++){auto&u=us[i];in>>u.id>>u.kind>>u.movable>>u.x>>u.y>>u.d;shape(u);place(i,i);if(u.movable)movable.push_back(i);}
 for(int j=0;j<m;j++){int a,b,w;in>>a>>b>>w;es.push_back({a,b,w});incoming[b]++;outgoing[a]++;incident[a].push_back(j);incident[b].push_back(j);}
 for(int j=0;j<nt;j++){int x,y,a,b;in>>x>>y>>a>>b;int c=y*70+x;forbid[c]=1;trin[c]=a;trout[c]=b;}
 int rx,ry,rw,rh;in>>rx>>ry>>rw>>rh;for(int y=ry;y<ry+rh;y++)for(int x=rx;x<rx+rw;x++)forbid[y*70+x]=2;
 components();long long score=0;for(int i=0;i<n;i++){ps[i]=calcports(i);score+=10000LL*ps[i].deficit;}ec.resize(m);for(int e=0;e<m;e++){ec[e]=edgecost(e);score+=10*ec[e];}
 auto bestus=us;long long best=score,accepted=0,iter=0;auto start=chrono::steady_clock::now();double lastsave=0,lastlog=0;writebest(out,bestus,best,0,0,seed);
 vector<Ports> backup(n);vector<int> oldec(m);
 while(true){iter++;double sec=chrono::duration<double>(chrono::steady_clock::now()-start).count();if(sec>=limit)break;int a=movable[rng()%movable.size()],b=-1;Unit ua=us[a],ub;int mode=rng()%100;bitset<300>affected;gather(a,affected);
  if(mode<30){vector<int> candidates;for(int j:movable)if(j!=a&&us[j].kind==us[a].kind)candidates.push_back(j);b=candidates[rng()%candidates.size()];ub=us[b];gather(b,affected);place(a,-1);place(b,-1);us[a].x=ub.x;us[a].y=ub.y;us[a].d=ub.d;us[b].x=ua.x;us[b].y=ua.y;us[b].d=ua.d;shape(us[a]);shape(us[b]);}
  else {place(a,-1);if(mode<47){us[a].d=rng()%4;shape(us[a]);}else if(mode<82){us[a].x+=(int)(rng()%9)-4;us[a].y+=(int)(rng()%9)-4;}else{us[a].x=rng()%70;us[a].y=rng()%70;if(rng()%2){us[a].d=rng()%4;shape(us[a]);}}}
  bool ok=legal(a);if(ok){place(a,a);if(b>=0){ok=legal(b);if(ok)place(b,b);}}
  if(!ok){if(inside(us[a].x,us[a].y)&&inside(us[a].x+us[a].w-1,us[a].y+us[a].h-1)){for(int y=us[a].y;y<us[a].y+us[a].h;y++)for(int x=us[a].x;x<us[a].x+us[a].w;x++)if(grid[y*70+x]==a)grid[y*70+x]=-1;}us[a]=ua;place(a,a);if(b>=0){us[b]=ub;place(b,b);}continue;}
  gather(a,affected);if(b>=0)gather(b,affected);bool changedgeo=(b<0&&(us[a].x!=ua.x||us[a].y!=ua.y||us[a].w!=ua.w||us[a].h!=ua.h));if(changedgeo)components();bitset<400>changededges;if(changedgeo)changededges.set();long long delta=0;
  for(int i=0;i<n;i++)if(affected[i]){backup[i]=ps[i];Ports p=calcports(i);delta+=10000LL*(p.deficit-ps[i].deficit);ps[i]=move(p);for(int e:incident[i])changededges[e]=1;}
  for(int e=0;e<m;e++)if(changededges[e]){oldec[e]=ec[e];ec[e]=edgecost(e);delta+=10*(ec[e]-oldec[e]);}
  // Repeated cooling keeps enough movement to break packed rows, then compacts the wiring.
  double phase=fmod(sec,30.0)/30.0;double temp=18000*pow(.0004,phase)+2;
  bool accept=delta<=0||rand01(rng)<exp(-min(700.,(double)delta/temp));
  if(accept){score+=delta;accepted++;if(score<best){best=score;bestus=us;if(sec-lastsave>.5){writebest(out,bestus,best,iter,sec,seed);lastsave=sec;}}}
  else {place(a,-1);if(b>=0)place(b,-1);us[a]=ua;place(a,a);if(b>=0){us[b]=ub;place(b,b);}for(int i=0;i<n;i++)if(affected[i])ps[i]=move(backup[i]);for(int e=0;e<m;e++)if(changededges[e])ec[e]=oldec[e];if(changedgeo)components();}
  if(sec-lastlog>10){cerr<<"seed "<<seed<<" sec "<<sec<<" score "<<score<<" best "<<best<<" iter "<<iter<<" accepted "<<accepted<<'\n';lastlog=sec;}
 }
 writebest(out,bestus,best,iter,limit,seed);cerr<<"FINAL "<<best<<" iterations "<<iter<<" accepted "<<accepted<<'\n';
}
