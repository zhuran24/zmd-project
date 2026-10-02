#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <random>
#include <set>
#include <string>
#include <tuple>
#include <vector>
using namespace std;
struct P{int x,y;};
struct U{string id;int k,fix,x,y,d,ni,no,w,h;vector<P> in,out;};
struct Score{int overlap,ports,power,wire,disconnected;double value()const{return 3000.*overlap+350.*ports+500.*power+150.*disconnected+5.*wire;}auto rank()const{return tuple(overlap,ports,power,disconnected,wire);}};
int grid[70][70],overlap=0;vector<U> units;vector<pair<int,int>> edges;vector<int> movers,poles;mt19937 gen;
int ri(int n){return int(gen()%n);}double ur(){return (gen()+.5)/4294967296.;}
void geometry(U &u){
 if(u.k==0)u.w=u.h=3;else if(u.k==1)u.w=u.h=5;else if(u.k==2){u.w=u.d%2?6:4;u.h=u.d%2?4:6;}else if(u.k==3)u.w=u.h=9;else if(u.k==4){u.w=1;u.h=3;}else if(u.k==5){u.w=3;u.h=1;}else u.w=u.h=2;
 u.in.clear();u.out.clear();
 auto port=[&](int s,int off,bool out){P p=s==0?P{u.x+u.w,u.y+off}:s==1?P{u.x+off,u.y+u.h}:s==2?P{u.x-1,u.y+off}:P{u.x+off,u.y-1};(out?u.out:u.in).push_back(p);};
 if(u.k<3){for(int j=0;j<(u.d%2?u.w:u.h);j++){port(u.d,j,false);port((u.d+2)%4,j,true);}}
 else if(u.k==3){for(int s:{u.d,(u.d+2)%4})for(int j=1;j<8;j++)port(s,j,false);for(int s:{(u.d+1)%4,(u.d+3)%4})for(int j:{1,4,7})port(s,j,true);}
 else if(u.k==4)port(0,1,true);else if(u.k==5)port(1,1,true);
}
bool inb(P p){return p.x>=0&&p.y>=0&&p.x<70&&p.y<70;}
bool freec(P p){return inb(p)&&grid[p.x][p.y]==0;}
void occupy(U const&u,int sign){for(int x=u.x;x<u.x+u.w;x++)for(int y=u.y;y<u.y+u.h;y++){overlap-=max(0,grid[x][y]-1);grid[x][y]+=sign;overlap+=max(0,grid[x][y]-1);}}
Score score(){Score s{overlap,0,0,0,0}; int comp[70][70];fill(&comp[0][0],&comp[0][0]+4900,-1);int nc=0;vector<P> todo; for(int x=0;x<70;x++)for(int y=0;y<70;y++)if(grid[x][y]==0&&comp[x][y]<0){todo.clear();todo.push_back({x,y});comp[x][y]=nc;for(size_t z=0;z<todo.size();z++){P a=todo[z];for(P p:vector<P>{{a.x-1,a.y},{a.x+1,a.y},{a.x,a.y-1},{a.x,a.y+1}})if(inb(p)&&grid[p.x][p.y]==0&&comp[p.x][p.y]<0){comp[p.x][p.y]=nc;todo.push_back(p);}}nc++;}
 for(U const&u:units){int a=0,b=0;for(P p:u.in)a+=freec(p);for(P p:u.out)b+=freec(p);s.ports+=max(0,u.ni-a)+max(0,u.no-b);
  if(u.k<3){bool ok=false;for(int j:poles){U const&p=units[j];if(u.x+u.w-1>=p.x-5&&u.x<=p.x+6&&u.y+u.h-1>=p.y-5&&u.y<=p.y+6){ok=true;break;}}s.power+=!ok;}}
 for(auto [a,b]:edges){int d=1000;for(P p:units[a].out)for(P q:units[b].in)d=min(d,abs(p.x-q.x)+abs(p.y-q.y)+1+4*!freec(p)+4*!freec(q));s.wire+=d;bool connected=false;for(P p:units[a].out)if(freec(p))for(P q:units[b].in)if(freec(q)&&comp[p.x][p.y]==comp[q.x][q.y])connected=true;s.disconnected+=!connected;}
 return s;
}
int main(int argc,char**argv){if(argc<5)return 2;ifstream f(argv[1]);string out=argv[2];double seconds=stod(argv[3]);gen.seed(stoi(argv[4]));int n,e,rx,ry,rw,rh;f>>n>>e>>rx>>ry>>rw>>rh;
 for(int i=0;i<n;i++){U u;f>>u.id>>u.k>>u.fix>>u.x>>u.y>>u.d>>u.ni>>u.no;geometry(u);units.push_back(u);if(!u.fix)movers.push_back(i);if(u.k==6)poles.push_back(i);}
 for(int i=0,a,b;i<e;i++){f>>a>>b;edges.emplace_back(a,b);}
 for(int x=rx;x<rx+rw;x++)for(int y=ry;y<ry+rh;y++)grid[x][y]=1;
 for(U const&u:units)occupy(u,1);Score cur=score(),best=cur;auto bu=units;long long it=0;auto start=chrono::steady_clock::now();
 auto elapsed=[&](){return chrono::duration<double>(chrono::steady_clock::now()-start).count();};
 auto write=[&](Score s){ofstream o(out);o<<s.overlap<<" "<<s.ports<<" "<<s.power<<" "<<s.wire<<" "<<it<<" "<<elapsed()<<"\n";for(auto const&u:bu)o<<u.id<<" "<<u.k<<" "<<u.x<<" "<<u.y<<" "<<u.d<<"\n";};
 write(best);
 while(elapsed()<seconds){it++;int a=movers[ri(movers.size())],b=-1;U oa=units[a],ob;double choice=ur();
  if(choice<.25){b=movers[ri(movers.size())];if(a==b||units[a].k!=units[b].k)continue;ob=units[b];occupy(units[a],-1);occupy(units[b],-1);swap(units[a].x,units[b].x);swap(units[a].y,units[b].y);swap(units[a].d,units[b].d);}
  else{occupy(units[a],-1);U &u=units[a];if(choice<.40)u.d=(u.d+(ri(3)+1))%4;else if(choice<.83){int scale=ri(6)==0?5:1;u.x+=(ri(3)-1)*scale;u.y+=(ri(3)-1)*scale;}else{u.x=1+ri(66);u.y=1+ri(66);}if(u.k==3)u.d%=2;}
  geometry(units[a]);if(b>=0)geometry(units[b]);auto good=[](U const&u){return u.x>=1&&u.y>=1&&u.x+u.w<=70&&u.y+u.h<=70;};
  if(!good(units[a])||(b>=0&&!good(units[b]))){units[a]=oa;occupy(units[a],1);if(b>=0){units[b]=ob;occupy(units[b],1);}continue;}
  occupy(units[a],1);if(b>=0)occupy(units[b],1);Score next=score();double phase=fmod(elapsed()/seconds*6.,1.);double temp=3000*pow(1-phase,5)+.05;double delta=next.value()-cur.value();
  if(delta<=0||ur()<exp(-delta/temp)){cur=next;if(cur.rank()<best.rank()){best=cur;bu=units;write(best);}}
  else{occupy(units[a],-1);units[a]=oa;occupy(units[a],1);if(b>=0){occupy(units[b],-1);units[b]=ob;occupy(units[b],1);}}
 }
 write(best);cout<<"iterations "<<it<<" best "<<best.overlap<<" "<<best.ports<<" "<<best.power<<" "<<best.wire<<" disconnected "<<best.disconnected<<" seconds "<<elapsed()<<"\n";
}
