// Two independently encoded local schedulers. No derivation-seat source is used.
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <queue>
#include <utility>
#include <vector>
using Trace=std::vector<std::pair<int,int>>;

// Encoding A: a fixed step clock, absolute release deadlines, timestamp sort.
Trace absolute_clock(int k,const std::array<int,4>& g,int late,int delay,int mode){
    std::array<int,6> deadline,last; std::array<bool,6> full{};
    deadline.fill(-1); for(int j=0;j<6;j++)last[j]=-100-j;
    int pending=0,cursor=0; Trace out;
    for(int t=0;t<40;t++){
        for(int j=0;j<k;j++)if(full[j]&&deadline[j]==t&&!(late&(1<<j)))full[j]=false;
        int block=t/8;
        if(t%8==0&&block<4&&!(delay&(1<<block)))pending+=g[block];
        if(pending){
            int choice=-1;
            if(mode==0){
                for(int m=0;m<k;m++){int j=(cursor+m)%k;if(!full[j]){choice=j;break;}}
            }else{
                for(int j=0;j<k;j++)if(!full[j]&&(choice<0||last[j]<last[choice]))choice=j;
            }
            if(choice>=0){full[choice]=true;deadline[choice]=t+8;last[choice]=t;cursor=(choice+1)%k;--pending;out.emplace_back(t,choice);}
        }
        for(int j=0;j<k;j++)if(full[j]&&deadline[j]==t&&(late&(1<<j)))full[j]=false;
        if(t%8==0&&block<4&&(delay&(1<<block)))pending+=g[block];
    }
    assert(pending==0);return out;
}

struct Event { int instant,kind,payload; bool operator>(const Event& o)const{
    if(instant!=o.instant)return instant>o.instant;
    if(kind!=o.kind)return kind>o.kind;
    return payload>o.payload;
}};
// Encoding B: event heap; a circular channel list or recency queue; no step sweep.
Trace event_heap(int k,const std::array<int,4>& g,int late,int delay,int mode){
    std::priority_queue<Event,std::vector<Event>,std::greater<Event>> heap;
    for(int t=0;t<40;t++)heap.push({3*t+1,1,0}); // judgement
    for(int n=0;n<4;n++)heap.push({24*n+((delay&(1<<n))?2:0),2,g[n]});
    std::vector<int> order;for(int j=0;j<k;j++)order.push_back(mode?k-1-j:j);
    std::array<bool,6> busy{};int waiting=0;Trace out;
    while(!heap.empty()){
        Event e=heap.top();heap.pop();
        if(e.kind==0){busy[e.payload]=false;continue;}
        if(e.kind==2){waiting+=e.payload;continue;}
        if(!waiting)continue;
        int p=0;while(p<k&&busy[order[p]])++p;
        if(p==k)continue;
        int j=order[p],t=e.instant/3;
        busy[j]=true;--waiting;out.emplace_back(t,j);
        heap.push({3*(t+8)+((late&(1<<j))?2:0),0,j});
        if(mode){order.erase(order.begin()+p);order.push_back(j);}
        else std::rotate(order.begin(),order.begin()+p+1,order.end());
    }
    assert(waiting==0);return out;
}

static uint64_t hash_value=1469598103934665603ULL;
void hash_int(int x){for(int i=0;i<4;i++){hash_value^=static_cast<unsigned>((x>>(8*i))&255);hash_value*=1099511628211ULL;}}

int main(int argc,char**argv){
    assert(argc==2);uint64_t cases=0,successes=0;std::array<uint64_t,6> by_k{};
    for(int k=1;k<=6;k++)for(int a=0;a<=k;a++)for(int b=0;b<=k-a;b++)
    for(int c=0;c<=k-b;c++)for(int d=0;d<=k-c;d++){
        std::array<int,4> groups{a,b,c,d};
        for(int late=0;late<(1<<k);late++)for(int delay=0;delay<16;delay++)for(int mode=0;mode<2;mode++){
            auto x=absolute_clock(k,groups,late,delay,mode),y=event_heap(k,groups,late,delay,mode);
            assert(x==y);int sum=a+b+c+d;assert(static_cast<int>(x.size())==sum);
            for(int n=0;n<sum;n++)assert(x[n].second==(mode?k-1-(n%k):n%k));
            hash_int(k);for(int g:groups)hash_int(g);hash_int(late);hash_int(delay);hash_int(mode);
            for(auto [t,j]:x){hash_int(t);hash_int(j);}
            ++cases;++by_k[k-1];successes+=sum;
        }
    }
    assert(cases==1851008);
    std::ofstream f(argv[1]);f<<"{\n  \"status\": \"PASS\",\n  \"cases\": "<<cases<<",\n  \"independent_encodings\": 2,\n  \"trace_agreements\": "<<cases<<",\n  \"violations\": 0,\n  \"successes_checked\": "<<successes<<",\n  \"fnv1a64_trace\": \""<<std::hex<<hash_value<<std::dec<<"\",\n  \"cases_by_k\": [";
    for(int k=0;k<6;k++){if(k)f<<", ";f<<by_k[k];}f<<"]\n}\n";
    std::cout<<"PASS: "<<cases<<" cases, "<<successes<<" successful events; both schedulers agree\n";
}
