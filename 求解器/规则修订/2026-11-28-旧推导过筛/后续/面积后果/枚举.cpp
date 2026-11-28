// g++ -std=c++17 -O2 枚举.cpp -o 枚举
#include <algorithm>
#include <cstdlib>
#include <array>
#include <iostream>
#include <map>
#include <tuple>
#include <string>
#include <vector>
using namespace std;
struct Rect { int x,y,w,h;
  bool has(int i,int j)const{return x<=i && i<x+w && y<=j && j<y+h;}
};
bool hits(Rect r,Rect s){return r.x<s.x+s.w && s.x<r.x+r.w && r.y<s.y+s.h && s.y<r.y+r.h;}
struct Config {const char *name; int extra,delta,box,n3,n5,lower;};
struct Budget {int p,j,n3,n5;};
enum Kind {Gap,Machine,Core,Pole,Free3,Free5,EndBlock};
struct Shape {Kind kind; int along,depth,axis;}; // axis=0 along, 1 normal
struct Option {int len,kind,cost,c,p,n3,n5;};
using Table=map<array<int,4>,int>;
void reduce(Table &t,array<int,4> k,int v){
  auto it=t.find(k);
  if(it==t.end()) t.emplace(k,v); else it->second=min(it->second,v);
}
// Each group of lines shares one core, its idle bodies, and its pole budget.
// Rotate or transpose into (along,normal) coordinates, preserving coordinate 0.
// Distinct covered machines have disjoint 3x3 subblocks meeting the
// 12x12 coverage square. Each translated 3x3 group of subblock origins
// can contribute at most one machine. Cache locally clipped windows.
int poleLoss(Rect r,int px,int py){
  auto clip=[](int a){return max(0,min(14,a));};
  int x0=px-7,y0=py-7;
  array<int,8> key={clip(1-x0),clip(68-x0),clip(1-y0),clip(68-y0),
      clip(r.x-2-x0),clip(r.x+r.w-x0),clip(r.y-2-y0),clip(r.y+r.h-y0)};
  static map<array<int,8>,int> cache;
  if(cache.count(key))return cache[key];
  int cap=23;
  for(int dx=0;dx<3;++dx)for(int dy=0;dy<3;++dy){
    bool occupied[6][6]={};int n=0;
    for(int u=key[0];u<key[1];++u)for(int v=key[2];v<key[3];++v){
      if(u>=key[4] && u<key[5] && v>=key[6] && v<key[7])continue;
      if(u>=5 && u<=8 && v>=5 && v<=8)continue;
      bool &seen=occupied[(u+dx)/3][(v+dy)/3];
      if(!seen){seen=true;++n;}
    }
    cap=min(cap,n);
  }
  return cache[key]=23-cap;
}
Table line(Rect r,bool outer,int sign,bool cornerDiscount,Budget b,bool box,int elbow=-1,int otherElbow=-1){
  int lo=outer?1:r.x, hi=outer?70:r.x+r.w;
  int yline=outer?69:(sign>0?r.y+r.h:r.y-1);
  if(yline==70)return {{{0,0,0,0},0}};
  vector<vector<Option>> opt(hi-lo);
  vector<Shape> shapes={{Machine,3,3,0},{Machine,3,3,1},{Machine,5,5,0},{Machine,5,5,1},
    {Machine,4,6,0},{Machine,6,4,1},{Core,9,9,0},{Core,9,9,1},{Pole,2,2,-1}};
  if(b.n3) shapes.push_back({Free3,3,3,-1});
  if(b.n5) shapes.push_back({Free5,5,5,-1});
  Rect fixedA{r.x-elbow,70-elbow,elbow,elbow},fixedB{70-otherElbow,r.y-otherElbow,otherElbow,otherElbow};
  auto fixed=[&](int x,int y){return (elbow>0 && fixedA.has(x,y)) || (otherElbow>0 && fixedB.has(x,y));};
  auto avail=[&](int x,int y){return !fixed(x,y) && x>=1 && y>=1 && x<70 && y<70 && !r.has(x,y);};
  for(auto [kind,w,h,axis]:shapes){
    int y=outer?70-h:(sign>0?yline:yline-h+1);
    if(y<1 || y+h>70) continue;
    for(int x=max(1,lo-w+1);x<hi && x+w<=70;++x){
      Rect s{x,y,w,h}; if(hits(r,s))continue;
      if((elbow>=0 && s.has(r.x-1,69)) || (otherElbow>=0 && s.has(69,r.y-1)))continue;
      if((elbow>0 && hits(s,fixedA)) || (otherElbow>0 && hits(s,fixedB)))continue;
      if(kind==Core && (x<2 || y<2 || (x<=3 && y<=3))) continue;
      bool ok=true;
      if(axis>=0){
        int n=axis==0?h:w;
        for(int side:{-1,1}){
          int live=0;
          for(int k=0;k<n;++k){
            if(kind==Core && k!=1 && k!=4 && k!=7) continue;
            int u=axis==0?(side==-1?x-1:x+w):x+k;
            int v=axis==1?(side==-1?y-1:y+h):y+k;
            live+=avail(u,v);
          }
          if(live<(kind==Core?3:1))ok=false;
        }
      }
      if(!ok)continue;
      int start=max(x,lo), end=min(x+w,hi);
      int tag=(start==x && end==x+w)?kind:EndBlock;
      bool discount=outer && cornerDiscount && s.has(69,69);
      int polePaid=0;
      if(kind==Pole){
        if(outer)polePaid=1;
        else {
          int loss=poleLoss(r,x,y);
          if(x>=r.x+5 && x+7<=r.x+r.w)loss=max(loss,10);
          if(x==1 || y==1 || x==68 || y==68)loss=max(loss,10);
          if(b.j==0 && (x==1 || y==1 || x==68 || y==68))continue;
          polePaid=loss;
        }
      }
      opt[start-lo].push_back({end-start,tag,0,kind==Core,(discount?0:polePaid),
                               kind==Free3&&!discount,kind==Free5&&!discount});
    }
  }
  // A full core touching Q by its output edge is impossible. With boxes a
  // core can have no active intake; C-M/C-P adjacency is excluded only along
  // its required take-port sides (full length on the projection line).
  int cap=outer?b.j:(23*b.p-217);
  vector<array<Table,8>> dp(hi-lo+1); dp[0][Gap][{0,0,0,0}]=0;
  for(int i=0;i<hi-lo;++i){
    opt[i].push_back({1,Gap,(outer&&r.has(lo+i,yline))||fixed(lo+i,yline)?0:1,0,0,0,0});
    for(int prev=0;prev<7;++prev) for(auto [key,v]:dp[i][prev]) for(auto o:opt[i]){
      if((prev==Machine && (o.kind==Machine||o.kind==Core)) ||
         (prev==Core && (o.kind==Machine||o.kind==Pole)) ||
         (prev==Pole && o.kind==Core))continue;
      array<int,4> k={key[0]+o.c,key[1]+o.p,key[2]+o.n3,key[3]+o.n5};
      if(k[0]>1 || k[1]>cap || k[2]>b.n3 || k[3]>b.n5)continue;
      reduce(dp[i+o.len][o.kind],k,v+o.cost);
    }
  }
  Table out; for(auto &t:dp.back())for(auto [k,v]:t)reduce(out,k,v);return out;
}
Table group(Rect r,bool outer,Budget b,bool box,int elbow=-1,int otherElbow=-1){
  Table t={{{0,0,0,0},0}};
  for(int dim:{0,1}){
    for(int sign:{-1,1}){
      if(outer && sign<0) continue;
      if(!outer && sign>0 && r.y+r.h==70)continue;
      Table u=line(r,outer,sign,dim==1,b,box,elbow,otherElbow),next;
      for(auto [k,v]:t)for(auto [l,z]:u){
        array<int,4> n;for(int i=0;i<4;++i)n[i]=k[i]+l[i];
        if(n[0]<=1 && n[1]<=(outer?b.j:(23*b.p-217)) && n[2]<=b.n3 && n[3]<=b.n5)
          reduce(next,n,v+z);
      }
      t=move(next);
    }
    r={r.y,r.x,r.h,r.w};swap(elbow,otherElbow);
  }
  return t;
}
struct Pattern {int h,d,side;};
vector<Pattern> patterns(Rect r){
  vector<Pattern> v;
  for(int k=0;k<=23;++k)for(int s=0;s<(k?2:1);++s){
    auto count=[](int k,int first,int n){int c=0;for(int i=0;i<23;++i){
      int u=3*i+1+(i>=k); c+=first<=u && u<first+n;}return c;};
    if(!getenv("SKIP_CORRIDOR") && ((r.x==4 && count(s?0:k,r.y,r.h)>6)||(r.y==4 && count(s?k:0,r.x,r.w)>6)))continue;
    int h=(k==0||k==23)?9:(k==1||k==22)?2:0;v.push_back({h,3*k,s});
  }
  return v;
}
// When Q reaches the northeast corner, strips wider than any core separate
// parallel lines. Touching both perpendicular lines would put an entire take
// side of the core against Q, or outside the base. Hence no shared core.
bool disjointCore(Rect r){
  return r.x+r.w==70 && r.y+r.h==70 && r.x>9 && r.y>9;
}
int main(int argc,char**argv){
  if(argc==2){
    Rect r{39,35,31,35};
    for(int a:{0,3})for(int b:{0,3})if(a+b<=3){
      Budget budget{10,0,1-(a+b)/3,0};
      for(int outer:{0,1}){
        cout<<"elbows "<<a<<" "<<b<<" outer "<<outer<<endl;
        map<array<int,2>,int> summary;
        for(auto [k,v]:group(r,outer,budget,true,a,b)){
          array<int,2> key{k[0],k[2]};
          if(!summary.count(key) || summary[key]>v)summary[key]=v;
        }
        for(auto [k,v]:summary)cout<<k[0]<<" core "<<k[1]<<" free "<<v<<endl;
      }
    }
    return 0;
  }
  // delta=4E+ceil(Omega)-110. Larger increments are excluded by the scalar bound.
  vector<Config> cases={{"base",0,0,0,0,0,1092},{"shaper",9,34,0,1,0,1083},
    {"other-small",9,36,0,1,0,1083},{"box",9,36,1,1,0,1083},
    {"box-next",9,36,1,1,0,1081},{"box+shaper",18,70,1,2,0,1071},{"box+other-small",18,72,1,2,0,1071},
    {"crusher+seed",34,136,0,1,1,1058}};
  for(auto c:cases){
    bool found=false;
    for(int A=string(c.name)=="box-next"?1083:(4558-160-c.delta)/4;A>=c.lower && !found;--A){
      for(int w=6;w*w<=A;++w){
        if(A%w || A/w>66)continue;
        int h=A/w;
        for(int p=10;14*p<=4558-4*A-c.delta;++p){
          int jmax=min({p,(23*p-217)/10,(54*p-520)/25});
          for(int j=0;j<=jmax;++j){
            int room=4558-4*A-16*p+2*j-c.delta;
            if(room<0)continue;
            Budget budget{p,j,c.n3,c.n5};
            int minSum=999,count=0; unsigned hmask=0; Rect witness{}; Pattern pat{};
            int X=0,Y=0;
            for(int x=4;x+w<=70;++x)for(int y=4;y+h<=70;++y){
              Rect r{x,y,w,h};auto pv=patterns(r);if(pv.empty())continue;
              auto bh=*min_element(pv.begin(),pv.end(),[](auto a,auto b){return a.h<b.h;});
              auto ext=group(r,true,budget,c.box);
              int xMin=999;
              for(auto [k,v]:ext)xMin=min(xMin,v);
              if(xMin+bh.h>room) continue;
              auto ring=group(r,false,budget,c.box);
              int joint=999,xb=999,yb=999,which=0;
              for(size_t i=0;i<pv.size();++i){
                auto pat=pv[i];
                for(auto [u,Xv]:ext)for(auto [v,Yv]:ring){
                  if(disjointCore(r) && u[0]+v[0]>1)continue;
                  int debt=2*u[1]; // top/right poles cannot cover the inner band except near a terminal gap
                  if(pat.d==69)debt=2*max(0,u[1]-1);
                  int cost=Xv+Yv+debt+pat.h;
                  if(cost<joint){joint=cost;xb=Xv;yb=Yv;which=i;}
                }
              }
              if(joint>room)continue;
              if(disjointCore(r) && j==0){
                joint=999;
                for(int left:{0,3,5})for(int right:{0,3,5}){
                  int m3=c.n3-(left==3)-(right==3),m5=c.n5-(left==5)-(right==5);
                  if(m3<0 || m5<0)continue;
                  Budget rem{p,j,m3,m5};
                  auto out=group(r,true,rem,c.box,left,right);
                  auto in=group(r,false,rem,c.box,left,right);
                  for(auto [u,Xv]:out)for(auto [v,Yv]:in){
                    if(u[0]+v[0]>1 || u[2]+v[2]>m3 || u[3]+v[3]>m5)continue;
                    int cost=Xv+Yv+bh.h;
                    if(cost<joint){joint=cost;xb=Xv;yb=Yv;which=int(find_if(pv.begin(),pv.end(),[&](Pattern e){return e.h==bh.h;})-pv.begin());}
                  }
                }
                if(joint>room)continue;
              }
              for(auto ev:pv){
                // Here only P=10,J=0 is needed for the printed h summary.
                if(j==0 && joint-bh.h+ev.h<=room)hmask|=1u<<ev.h;
              }
              count++;
              if(joint<minSum){
                minSum=joint;witness=r;pat=pv[which];X=xb;Y=yb;
              }
            }
            if(count){found=true;cout<<c.name<<" A "<<A<<" "<<w<<"x"<<h<<" P,J "<<p<<","<<j
              <<" hmask "<<hmask<<" budget "<<room<<" survivors "<<count<<" sample "<<witness.x<<","<<witness.y
              <<" d,side "<<pat.d<<","<<pat.side<<" X0lb,Y0lb "<<X<<","<<Y<<endl;}
          }
        }
      }
    }
    if(!found)cout<<c.name<<" no survivor down to "<<c.lower<<endl;
  }
}
