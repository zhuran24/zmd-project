"""独立运输核：显式元件/双向桥通道，与不使用元件的逐格参考核。

图是无坐标的放宽测试输入，不是合法布局证书。
"""
from collections import defaultdict
import random

class Topology:
    def __init__(self, routes, patterns, seed=0, pair=True, forced_pairs=None):
        self.routes=routes; self.patterns=patterns
        self.paths=[]; self.cell_kind=[]; self.owner=[]; self.physical=[]
        for r,pattern in enumerate(patterns):
            path=[]
            for p,k in enumerate(pattern):
                c=len(self.cell_kind);path.append(c)
                self.cell_kind.append(k);self.owner.append((r,p));self.physical.append(f'cell{c}')
            self.paths.append(path)
        rng=random.Random(seed)
        bridges=[c for c,k in enumerate(self.cell_kind) if k=='B'];rng.shuffle(bridges)
        self.pairs=[]
        if forced_pairs is not None:
            for a,b in forced_pairs:
                assert self.cell_kind[a]==self.cell_kind[b]=='B' and self.owner[a][0]!=self.owner[b][0]
                self.physical[b]=self.physical[a];self.pairs.append((a,b))
        elif pair:
            while bridges:
                a=bridges.pop()
                b=next((b for b in bridges if self.owner[b][0]!=self.owner[a][0]),None)
                if b is not None:
                    bridges.remove(b);self.physical[b]=self.physical[a];self.pairs.append((a,b))
        self.components=[];self.cell_component={};self.route_components=[]
        for path in self.paths:
            comps=[];start=0
            while start<len(path):
                stop=start+1
                if self.cell_kind[path[start]]=='T':
                    while stop<len(path) and self.cell_kind[path[stop]]=='T':stop+=1
                j=len(self.components);self.components.append(path[start:stop]);comps.append(j)
                for c in path[start:stop]:self.cell_component[c]=j
                start=stop
            self.route_components.append(comps)
        self.connections={};self.outgoing=defaultdict(list);self.incoming=defaultdict(list)
        self.expected_last={};self.forward={};self.layers={}
        # channel key: (发送元件编号或非运输单位名, 接收首格编号或非运输单位名)
        for r,(a,b,item) in enumerate(routes):
            path=self.paths[r];comps=self.route_components[r]
            for p,c in enumerate(path):
                self.expected_last[c]=a if p==0 else self.physical[path[p-1]]
            for z,comp in enumerate(comps):
                cells=self.components[comp]
                nxt=self.components[comps[z+1]][0] if z+1<len(comps) else b
                self.forward[comp]=nxt
                self._channel(comp,nxt,self.physical[cells[-1]],self.recipient_physical(nxt))
                if z and self.cell_kind[cells[0]]=='B' and self.cell_kind[self.components[comps[z-1]][-1]]=='B':
                    prev=self.components[comps[z-1]][-1]
                    self._channel(comp,prev,self.physical[cells[0]],self.physical[prev])
            self._channel(a,path[0],a,self.physical[path[0]])
        # 仅完整到达非运输终点的、不重访元件的路径产生层数。
        def lengths(c,visited):
            ans=set()
            for target in self.outgoing[c]:
                if isinstance(target,str):ans.add(1)
                else:
                    nxt=self.cell_component[target]
                    if nxt not in visited:
                        ans.update(d+1 for d in lengths(nxt,visited|{nxt}))
            return ans
        for c in range(len(self.components)):
            values=lengths(c,{c})
            assert len(values)==1,(c,values)
            self.layers[c]=values.pop()
        for comps in self.route_components:
            assert [self.layers[c] for c in comps]==list(range(len(comps),0,-1))

    def recipient_physical(self,target):
        return target if isinstance(target,str) else self.physical[target]

    def _channel(self,source,target,a,b):
        key=(source,target)
        assert key not in self.connections
        self.connections[key]=(a,b)
        self.outgoing[source].append(target)
        if isinstance(source,int):self.incoming[target].append(source)

    def order(self,rng):
        units=list(sorted(set(x for ab in self.connections.values() for x in ab)))
        rng.shuffle(units);built={v:i for i,v in enumerate(units)}
        channels=list(self.connections);rng.shuffle(channels)
        keys={ch:(max(built[x] for x in self.connections[ch]),i) for i,ch in enumerate(channels)}
        rank={ch:i for i,ch in enumerate(sorted(channels,key=keys.get))}
        return rank

class Transport:
    def __init__(self,topo,logical=False,empty=False):
        self.topo=topo;self.logical=logical
        self.entered=[None]*len(topo.cell_kind);self.last=[None]*len(self.entered)
        if not empty:
            for r,(_,b,_) in enumerate(topo.routes):
                if b!='核心':
                    for c in topo.paths[r]:self.entered[c]=-8;self.last[c]=topo.expected_last[c]
        self.receive_last={};self.send_last={};self.sent=[0]*len(topo.routes);self.received=[0]*len(topo.routes)
        self.rejected=[0]*len(topo.routes);self.inverse_blocked=0;self.decisions=0
        self.negative_whole_bridge_group=False

    def reset_history(self):
        self.receive_last.clear();self.send_last.clear()

    def ready(self,c,t):return self.entered[c] is not None and t-self.entered[c]>=8

    def cyclic(self,values,last,key):
        values=sorted(values,key=key)
        if last in values:
            i=values.index(last)+1;return values[i:]+values[:i]
        return values

    def put(self,c,t,origin):
        assert self.entered[c] is None
        self.entered[c]=t;self.last[c]=origin

    def move(self,a,b,t):
        assert self.ready(a,t) and self.entered[b] is None
        assert self.last[a]!=self.topo.physical[b]
        self.put(b,t,self.topo.physical[a]);self.entered[a]=None;self.last[a]=None

    def step(self,t,rank,accept):
        if self.logical:self._scalar(t,rank,accept)
        else:self._components(t,rank,accept)

    def _scalar(self,t,rank,accept):
        """所有末格先收货，再逐路倒序推空位；无层数、逆向边或元件分段。"""
        tp=self.topo
        tails=defaultdict(list)
        for r,(_,dest,_) in enumerate(tp.routes):tails[dest].append(r)
        for dest,rs in tails.items():
            lastcomp=self.receive_last.get(dest)
            cs=[tp.route_components[r][-1] for r in rs]
            ordered=self.cyclic(cs,lastcomp,lambda c:rank[(c,dest)])
            for comp in ordered:
                c=tp.components[comp][-1];r,_=tp.owner[c]
                if self.ready(c,t):
                    if accept(r):
                        self.entered[c]=None;self.last[c]=None;self.received[r]+=1
                        self.receive_last[dest]=comp
                    else:self.rejected[r]+=1
        for path in tp.paths:
            for p in range(len(path)-2,-1,-1):
                a,b=path[p:p+2]
                if self.ready(a,t) and self.entered[b] is None:self.move(a,b,t)

    def _components(self,t,rank,accept):
        tp=self.topo;done=set()
        def options(comp):
            cells=tp.components[comp];c=cells[-1]
            if not self.ready(c,t):return []
            result=[]
            for target in tp.outgoing[comp]:
                if self.last[c]==tp.recipient_physical(target):
                    self.inverse_blocked+=1
                else:result.append(target)
            return self.cyclic(result,self.send_last.get(comp),lambda target:rank[(comp,target)])
        def fire(comp):
            if comp in done:return
            done.add(comp);self.decisions+=1
            cells=tp.components[comp];c=cells[-1]
            for target in options(comp):
                r,_=tp.owner[c]
                if isinstance(target,str):
                    success=accept(r)
                    if success:
                        self.entered[c]=None;self.last[c]=None;self.received[r]+=1
                    else:self.rejected[r]+=1
                else:
                    success=self.entered[target] is None
                    if success:self.move(c,target,t)
                if success:
                    self.receive_last[target]=comp;self.send_last[comp]=target;break
            for p in range(len(cells)-2,-1,-1):
                a,b=cells[p:p+2]
                if self.ready(a,t) and self.entered[b] is None:self.move(a,b,t)
        order=sorted(range(len(tp.components)),key=lambda c:(tp.layers[c],min(rank[(c,d)] for d in tp.outgoing[c])))
        for comp in order:
            if comp in done:continue
            opts=options(comp)
            if not opts:fire(comp);continue
            target=opts[0]
            group=tp.incoming[target]
            if self.negative_whole_bridge_group and isinstance(target,int) and tp.cell_kind[target]=='B':
                groups=[z for z in tp.incoming if isinstance(z,int) and tp.physical[z]==tp.physical[target]]
                members=[(c,z) for z in groups for c in tp.incoming[z]]
                for c,z in sorted(members,key=lambda cz:rank[cz]):fire(c)
            else:
                for c in self.cyclic(group,self.receive_last.get(target),lambda c:rank[(c,target)]):fire(c)
        assert len(done)==len(tp.components)
        for c,e in enumerate(self.entered):
            assert e is None or self.last[c]==tp.expected_last[c],('来源失效',t,c,self.last[c],tp.expected_last[c])

    def observable(self,t):
        return (tuple(None if e is None else min(8,t-e) for e in self.entered),tuple(self.last),
                tuple(self.sent),tuple(self.received),tuple(self.rejected),
                tuple(self.receive_last.get(dest) for dest in sorted({b for a,b,x in self.topo.routes})))
