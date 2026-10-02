"""Independent flattened integer age/countdown encoding; no transition imports."""
from collections import Counter
from model_spec import graph

class AgeWorld:
    def __init__(self,lengths,prepared=True):
        mm,ss,rr=graph();self.names=list(mm);self.recipes=list(mm.values());self.name_id={n:i for i,n in enumerate(self.names)}
        self.t=0;self.routes=rr;self.lengths=lengths;self.sources=ss
        self.need=[dict(m.needs) for m in self.recipes]
        self.stock=[[50 if prepared else 0 for _ in m.needs] for m in self.recipes]
        self.goods=[50 if prepared and m.duration==8 else 0 for m in self.recipes]
        self.clock=[0 if prepared and m.duration==8 else -1 for m in self.recipes]
        self.on=[True]*len(mm)
        self.cells=[];self.start=[];self.end=[]
        for i,l in enumerate(lengths):
            self.start.append(len(self.cells));self.cells.extend([8 if prepared and rr[i][1]!="核心" else -1]*l);self.end.append(len(self.cells)-1)
        self.to={};self.fr={};self.slot=[]
        for i,(a,b,x) in enumerate(rr):
            self.to.setdefault(b,[]).append(i);self.fr.setdefault(a,[]).append(i)
            self.slot.append(-1 if b=="核心" else list(self.need[self.name_id[b]]).index(x))
        self.receive_order={n:ls[:] for n,ls in self.to.items()};self.send_connection=list(range(len(rr)))
        self.outunits=list(self.fr);self.last=[-1]*len(rr);self.recvlast={n:None for n in self.to}
        self.sent=[0]*len(rr);self.received=[0]*len(rr);self.refused=[0]*len(rr);self.started=Counter();self.delivered=Counter()
    def rebuild(self,build_order,clear):
        pos=dict(zip(build_order,range(len(build_order))))
        send={i:(max(pos[a],pos[(i,0)]),i) for i,(a,b,x) in enumerate(self.routes)}
        recv={i:(max(pos[b],pos[(i,self.lengths[i]-1)]),i) for i,(a,b,x) in enumerate(self.routes)}
        self.send_connection=send
        self.outunits=sorted(self.fr,key=lambda n:min(send[e] for e in self.fr[n]))
        self.receive_order={n:sorted(ls,key=lambda e:recv[e]) for n,ls in self.to.items()}
        if clear:self.last=[-1]*len(self.routes);self.recvlast={n:None for n in self.to}
    def step(self,warehouse=None):
        self.t+=1
        self.cells=[a+1 if 0<=a<8 else a for a in self.cells]
        for m in range(len(self.names)):
            if self.on[m] and self.clock[m]>0:self.clock[m]-=1
            if self.clock[m]==0 and self.goods[m]<=50-self.recipes[m].amount:
                self.goods[m]+=self.recipes[m].amount;self.clock[m]=-1
        for dst,raw in self.receive_order.items():
            pivot=0 if self.recvlast[dst] is None else (raw.index(self.recvlast[dst])+1)%len(raw)
            for z in range(len(raw)):
                e=raw[(pivot+z)%len(raw)];tail=self.end[e]
                if self.cells[tail]==8:
                    item=self.routes[e][2]
                    if dst=="核心":
                        accepted=warehouse is None or warehouse.get(item,0)>0
                    else:
                        m=self.name_id[dst];accepted=self.stock[m][self.slot[e]]!=50
                    if accepted:
                        if dst=="核心":
                            self.delivered[item]+=1
                            if warehouse is not None:warehouse[item]-=1
                        else:self.stock[m][self.slot[e]]+=1
                        self.cells[tail]=-1;self.recvlast[dst]=e;self.received[e]+=1
                    else:self.refused[e]+=1
                k=tail-1
                while k>=self.start[e]:
                    if self.cells[k]==8 and self.cells[k+1]==-1:self.cells[k+1]=0;self.cells[k]=-1
                    k-=1
        for name in self.outunits:
            m=self.name_id.get(name)
            if m is not None and not self.goods[m]:continue
            available=[e for e in self.fr[name] if self.cells[self.start[e]]<0]
            if not available:continue
            e=min(available,key=lambda z:(self.last[z],self.send_connection[z]))
            self.cells[self.start[e]]=0;self.last[e]=self.t;self.sent[e]+=1
            if m is not None:
                self.goods[m]-=1
                if self.clock[m]==0 and self.goods[m]+self.recipes[m].amount<=50:
                    self.goods[m]+=self.recipes[m].amount;self.clock[m]=-1
        for m,r in enumerate(self.recipes):
            if not self.on[m] or self.clock[m]!=-1:continue
            quantities=[v for _,v in r.needs]
            if all(a>=b for a,b in zip(self.stock[m],quantities)):
                self.stock[m]=[a-b for a,b in zip(self.stock[m],quantities)]
                self.clock[m]=r.duration;self.started[self.names[m]]+=1
    def signature(self):
        machines=tuple((n,tuple(self.stock[j]),self.goods[j],None if self.clock[j]==-1 else self.clock[j]) for j,n in enumerate(self.names))
        belts=tuple(tuple(None if v<0 else v for v in self.cells[self.start[e]:self.end[e]+1]) for e in range(len(self.routes)))
        ranks=tuple((n,tuple(sorted(ids,key=lambda e:(self.last[e],self.send_connection[e])))) for n,ids in self.fr.items())
        return machines,belts,ranks,tuple(self.recvlast.items())
    def fill(self):
        for j,r in enumerate(self.recipes):
            self.stock[j]=[50]*len(r.needs)
            if r.duration==8:self.goods[j]=50
        for e,(_,dst,_) in enumerate(self.routes):
            if dst!="核心":
                for k in range(self.start[e],self.end[e]+1):
                    if self.cells[k]<0:self.cells[k]=0
