"""本席自写230台步进核，桥元件核与逻辑链核逐步比较。

缓存整批进入不占用对外判定；仓库用本步各成品可收件数表示。
两核共用本文件机器制造代码，运输转移分开；这是桥归约互核，非两套独立制造核。
"""
import argparse, json, random
from collections import defaultdict
from pathlib import Path
from model_data import build
from transport import Topology,Transport

class Factory:
    def __init__(self,topo,logical=False):
        self.nodes,self.routes,self.inc,self.out=build();self.topo=topo
        self.trans=Transport(topo,logical)
        self.inv={n:{x:50 for x in rec[1]} for n,rec in self.nodes.items()}
        self.output={n:0 if rec[4]==40 else 50 for n,rec in self.nodes.items()}
        self.due={n:None if rec[4]==40 else -1 for n,rec in self.nodes.items()}
        self.started={n:0 for n in self.nodes};self.source_last={}
        self.t=-1;self.delivered=defaultdict(int);self.enabled={n:True for n in self.nodes}
        self.rank={};self.min_inv={};self.offlines=0

    def offline(self,rank,clear):
        self.rank=rank;self.offlines+=1
        if clear:self.source_last.clear();self.trans.reset_history()

    def flush(self,n):
        rec=self.nodes[n]
        if self.due[n] is not None and self.due[n]<=self.t and self.output[n]+rec[3]<=50:
            assert rec[2] not in self.inv[n] # 本接法满足同种唯一格。
            self.output[n]+=rec[3];self.due[n]=None

    def step(self,quota=None,contracts=True):
        self.t+=1;t=self.t
        if quota is None:quota={'高容谷地电池':100,'精选荞愈胶囊':100}
        remaining=dict(quota)
        for n in self.nodes:
            if not self.enabled[n] and self.due[n] is not None and self.due[n]>t-1:self.due[n]+=1
            self.flush(n)
        def accept(r):
            a,b,item=self.routes[r]
            if b=='核心':
                if remaining[item]<=0:return False
                remaining[item]-=1;self.delivered[item]+=1;return True
            if self.inv[b][item]>=50:return False
            self.inv[b][item]+=1;return True
        self.trans.step(t,self.rank,accept)
        sources=sorted(self.out,key=lambda n:min(self.rank[(n,self.topo.paths[r][0])] for r in self.out[n]))
        for n in sources:
            if n in self.nodes and self.output[n]==0:continue
            order=sorted(self.out[n],key=lambda r:(self.source_last.get(r,-1),self.rank[(n,self.topo.paths[r][0])]))
            for r in order:
                c=self.topo.paths[r][0]
                if self.trans.entered[c] is None:
                    self.trans.put(c,t,n);self.trans.sent[r]+=1;self.source_last[r]=t
                    if n in self.nodes:self.output[n]-=1;self.flush(n)
                    break
        for n,rec in self.nodes.items():
            if self.enabled[n] and self.due[n] is None and all(self.inv[n][x]>=amount for x,amount in rec[1].items()):
                for x,amount in rec[1].items():self.inv[n][x]-=amount
                self.due[n]=t+rec[4];self.started[n]+=1
        if contracts:self.check_contracts()

    def check_contracts(self):
        for n,rec in self.nodes.items():
            assert all(0<=v<=50 for v in self.inv[n].values()) and 0<=self.output[n]<=50
            if rec[4]==40 or n in ('H6','Q6'):continue
            assert self.due[n] is not None,('空缓存',self.t,n)
            if n[0] in ('S','J'):
                if n[1] in 'BK':
                    assert min(self.inv[n].values())>=49,('植物存货',self.t,n,self.inv[n])
                    assert self.output[n]>=50-rec[3],('植物取货',self.t,n,self.output[n])
            else:
                assert self.output[n]==50,('单出口取货',self.t,n,self.output[n])
                assert all(self.inv[n][x]>=50-a for x,a in rec[1].items()),('原料合同',self.t,n,self.inv[n])
        assert self.inv['H6']['钢块']==self.inv['Q6']['荞花粉末']
        assert self.output['H6']==self.output['Q6'] and self.due['H6']==self.due['Q6']
        assert len(set(self.inv['F4'].values()))==1
        r1=self.out['H6'][0];r2=self.out['Q6'][0]
        assert [None if self.trans.entered[c] is None else min(8,self.t-self.trans.entered[c]) for c in self.topo.paths[r1]]==[
                None if self.trans.entered[c] is None else min(8,self.t-self.trans.entered[c]) for c in self.topo.paths[r2]]

    def observable(self):
        return (self.inv,self.output,self.due,self.started,self.source_last,dict(self.delivered),self.trans.observable(self.t))

    def cycle_state(self):
        source_orders=tuple(tuple(sorted(self.out[n],key=lambda r:(self.source_last.get(r,-1),self.rank[(n,self.topo.paths[r][0])]))) for n in sorted(self.out))
        receiver=tuple(self.trans.receive_last.get(dest) for dest in sorted({b for a,b,x in self.routes}))
        return (tuple((tuple(self.inv[n].values()),self.output[n],None if self.due[n] is None else max(0,self.due[n]-self.t)) for n in self.nodes),
                tuple(None if e is None else min(8,self.t-e) for e in self.trans.entered),tuple(self.trans.last),source_orders,receiver)

def setup(seed,maxlen,mode):
    nodes,routes,inc,out=build();rng=random.Random(seed)
    lengths=[rng.randint(1,maxlen) for r in routes]
    lengths[out['Q6'][0]]=lengths[out['H6'][0]]
    patterns=[('B'*n if mode=='bridge' else ''.join(rng.choice('BT') for _ in range(n))) for n in lengths]
    topo=Topology(routes,patterns,seed+91)
    return topo,rng

def run(seed,maxlen,mode,history,frequent,stop_steps,settle):
    topo,rng=setup(seed,maxlen,mode);a=Factory(topo);b=Factory(topo,True)
    comparisons=0
    def offline():
        rank=topo.order(rng);clear=(history=='clear' or (history=='mixed' and rng.randrange(2)==0))
        a.offline(rank,clear);b.offline(rank,clear)
    def advance(quota=None):
        nonlocal comparisons
        a.step(quota);b.step(quota)
        assert a.observable()==b.observable(),('两运输核不同',a.t)
        comparisons+=1
    offline()
    # 两成品分别停收，然后双方停收；单库位竞争也作为有限扰动。
    phases=[(1200,None),(stop_steps,{'高容谷地电池':0,'精选荞愈胶囊':100}),
            (stop_steps,{'高容谷地电池':100,'精选荞愈胶囊':0}),
            (stop_steps,{'高容谷地电池':0,'精选荞愈胶囊':0}),(800,'partial')]
    for length,quota in phases:
        for k in range(length):
            if frequent and a.t%frequent==0:offline()
            q={item:rng.randrange(2) for item in ['高容谷地电池','精选荞愈胶囊']} if quota=='partial' else quota
            advance(q)
        offline()
    # 恢复后继续离线压力，随后固定次序检出并重放完整周期。
    for k in range(settle):
        if frequent and a.t%frequent==0:offline()
        advance()
    for k in range(max(1600,24*maxlen)):advance()
    state=a.cycle_state();counts=list(a.trans.sent);received=list(a.trans.received);deliv=dict(a.delivered)
    period=None
    for p in range(1,5001):
        advance()
        if a.cycle_state()==state:period=p;break
    assert period is not None,('未闭环',seed)
    d={x:a.delivered[x]-deliv.get(x,0) for x in ['高容谷地电池','精选荞愈胶囊']}
    assert d['高容谷地电池']*40==period*3
    assert d['精选荞愈胶囊']*160==period*11
    mine=[a.trans.sent[r]-counts[r] for r,(_,_,x) in enumerate(a.routes) if x in ('蓝铁矿','源矿')]
    assert len(mine)==52 and all(v*8==period for v in mine)
    state=a.cycle_state();reject=list(a.trans.rejected)
    for _ in range(period):advance()
    assert a.cycle_state()==state
    shared=[r for r,(n,_,_) in enumerate(a.routes) if n=='核心' or (n.startswith(('SK','JK')) and len(a.out[n])>1)]
    assert all(a.trans.rejected[r]==reject[r] for r in shared)
    return {'seed':seed,'maxlen':maxlen,'mode':mode,'history':history,'offline_interval':frequent,
            'is_layout':False,'steps_compared':comparisons,'offline_rebuilds':a.offlines,
            'transport_slots':len(topo.cell_kind),'bridge_pairs':len(topo.pairs),
            'period_steps':period,'period_deliveries':d,'mine_per_route':mine[0],
            'shared_zero_reject_routes':len(shared),'inverse_checks_blocked':a.trans.inverse_blocked,
            'closed_state_replayed':True,'violations':0}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=108001)
    p.add_argument('--maxlen',type=int,default=5);p.add_argument('--mode',choices=['mixed','bridge'],default='mixed')
    p.add_argument('--history',choices=['keep','clear','mixed'],default='keep');p.add_argument('--frequent',type=int,default=13)
    p.add_argument('--stop-steps',type=int,default=5000);p.add_argument('--settle',type=int,default=5000)
    args=p.parse_args();res=run(args.seed,args.maxlen,args.mode,args.history,args.frequent,args.stop_steps,args.settle)
    Path(__file__).with_name(f'factory_{args.seed}.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(res,ensure_ascii=False,indent=2))
