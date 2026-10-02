"""Independent timestamp/dictionary factory engine for this pure-belt graph."""
from collections import defaultdict,Counter
from model_spec import graph

class TimestampWorld:
    def __init__(self,lengths,prepared=True):
        self.spec,self.sources,self.routes=graph();self.lengths=lengths;self.t=0
        self.inputs={n:{x:50 if prepared else 0 for x,a in m.needs} for n,m in self.spec.items()}
        self.output={n:50 if prepared and m.duration==8 else 0 for n,m in self.spec.items()}
        self.done={n:0 if prepared and m.duration==8 else None for n,m in self.spec.items()}
        self.belts=[[-8]*l if prepared and d!="核心" else [None]*l for l,(_,d,_) in zip(lengths,self.routes)]
        self.outgoing=defaultdict(list);self.incoming=defaultdict(list)
        for i,(a,b,x) in enumerate(self.routes):self.outgoing[a].append(i);self.incoming[b].append(i)
        self.last_send=[None]*len(self.routes);self.last_receive={n:None for n in self.incoming}
        self.sent=[0]*len(self.routes);self.received=[0]*len(self.routes);self.refused=[0]*len(self.routes)
        self.started=Counter();self.delivered=Counter();self.on={n:True for n in self.spec}
        self.receive_rank=list(range(len(self.routes)));self.send_rank=list(range(len(self.routes)))
        self.unit_order=list(self.outgoing)
    def rebuild(self,build_order,clear):
        times={n:i for i,n in enumerate(build_order)}
        for i,(a,b,x) in enumerate(self.routes):
            self.send_rank[i]=(max(times[a],times[(i,0)]),i)
            self.receive_rank[i]=(max(times[b],times[(i,self.lengths[i]-1)]),i)
        self.unit_order=sorted(self.outgoing,key=lambda n:min(self.send_rank[i] for i in self.outgoing[n]))
        if clear:
            self.last_send=[None]*len(self.routes)
            self.last_receive={n:None for n in self.incoming}
    def flush(self,n):
        m=self.spec[n]
        if self.done[n] is not None and self.done[n]<=self.t and self.output[n]+m.amount<=50:
            self.output[n]+=m.amount;self.done[n]=None
    def step(self,warehouse=None):
        self.t+=1
        for n in self.spec:
            if not self.on[n] and self.done[n] is not None and self.done[n]>=self.t:self.done[n]+=1
        for n in self.spec:self.flush(n)
        for dst,group in self.incoming.items():
            order=sorted(group,key=lambda i:self.receive_rank[i])
            if self.last_receive[dst] in order:
                j=order.index(self.last_receive[dst])+1;order=order[j:]+order[:j]
            # Components that are unable to send cannot affect a sibling's store.
            # All are assessed once in the receiver's channel rotation.
            for i in order:
                row=self.belts[i];item=self.routes[i][2]
                if row[-1] is not None and row[-1]+8<=self.t:
                    can=(warehouse is None or warehouse.get(item,0)>0) if dst=="核心" else self.inputs[dst][item]<50
                    if can:
                        if dst=="核心":
                            self.delivered[item]+=1
                            if warehouse is not None:warehouse[item]-=1
                        else:self.inputs[dst][item]+=1
                        row[-1]=None;self.received[i]+=1;self.last_receive[dst]=i
                    else:self.refused[i]+=1
                for k in range(len(row)-2,-1,-1):
                    if row[k] is not None and row[k]+8<=self.t and row[k+1] is None:
                        row[k+1]=self.t;row[k]=None
        for src in self.unit_order:
            if src in self.spec:
                if self.output[src]==0:continue
            order=sorted(self.outgoing[src],key=lambda i:(-10**30 if self.last_send[i] is None else self.last_send[i],self.send_rank[i]))
            for i in order:
                if self.belts[i][0] is None:
                    self.belts[i][0]=self.t;self.last_send[i]=self.t;self.sent[i]+=1
                    if src in self.spec:self.output[src]-=1;self.flush(src)
                    break
        for n,m in self.spec.items():
            if self.on[n] and self.done[n] is None and all(self.inputs[n][x]>=a for x,a in m.needs):
                for x,a in m.needs:self.inputs[n][x]-=a
                self.done[n]=self.t+m.duration;self.started[n]+=1
    def signature(self):
        machines=tuple((n,tuple(self.inputs[n].values()),self.output[n],None if self.done[n] is None else max(0,self.done[n]-self.t)) for n in self.spec)
        belts=tuple(tuple(None if v is None else min(8,self.t-v) for v in b) for b in self.belts)
        ranks=tuple((n,tuple(sorted(ids,key=lambda i:(-10**30 if self.last_send[i] is None else self.last_send[i],self.send_rank[i])))) for n,ids in self.outgoing.items())
        return machines,belts,ranks,tuple(self.last_receive.items())
    def fill(self):
        for n,m in self.spec.items():
            for x in self.inputs[n]:self.inputs[n][x]=50
            if m.duration==8:self.output[n]=50
        for i,(_,dst,_) in enumerate(self.routes):
            if dst!="核心":
                for k in range(len(self.belts[i])):
                    if self.belts[i][k] is None:self.belts[i][k]=self.t
    def check_contract(self):
        for n,m in self.spec.items():
            if m.duration==40:continue
            if n in ("H6","Q6"):continue
            assert self.done[n] is not None,(self.t,n,"empty cache")
            plant=n.startswith("砂叶") or n.startswith("荞花")
            if not plant and n not in ("H6","Q6"):
                assert self.output[n]==50,(self.t,n,self.output[n])
                assert all(self.inputs[n][x]>=50-a for x,a in m.needs),(self.t,n,self.inputs[n])
            if plant:
                assert self.output[n]>=50-m.amount,(self.t,n,self.output[n])
                assert min(self.inputs[n].values())>=49,(self.t,n,self.inputs[n])
        assert self.inputs["H6"]["钢块"]==self.inputs["Q6"]["荞花粉末"]
        assert self.output["H6"]==self.output["Q6"]
        assert self.done["H6"]==self.done["Q6"]
        assert self.inputs["F3"]["钢质瓶"]==self.inputs["F3"]["细磨荞花粉末"]
        assert self.inputs["F4"]["钢质瓶"]==self.inputs["F4"]["细磨荞花粉末"]
