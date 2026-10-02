#!/usr/bin/env python3
"""Independent step engine for S11 pure directed belt routes (no bridge).
One step: complete/flush, judge all belts (receiver round robin), judge each
nontransport source once (oldest successful output first), start recipes.
Only stdout; invoke with -B. Numeric item names are internal encoding only.
"""
import json, random, sys
from collections import Counter

class M:
    def __init__(self, name, recipe=None):
        self.name=name; self.recipe=recipe; self.stock=Counter(); self.out=0
        self.remaining=0; self.done=False; self.routes=[]; self.count=0; self.batches=0
        self.sent={}; self.order={}; self.accept_order={}; self.cursor=None
    def flush(self):
        if self.done and self.out+self.recipe[2]<=50:
            self.out+=self.recipe[2]; self.done=False

class R:
    def __init__(self, source, target, kind, length, index):
        self.source=source; self.target=target; self.kind=kind
        self.cells=[None]*length; self.index=index; self.count=0

class Factory:
    def __init__(self, seed=92, maxlen=3, initial='thin'):
        self.rng=random.Random(seed); self.ms=[]; self.sources=[]; self.rs=[]; self.t=0
        self.sink=M('协议核心收货'); self.delivered=Counter(); self.open=True
        self.units=[]; self.initial=initial
        def m(name, ingredients, product, quantity=1, duration=8):
            u=M(name,(ingredients,product,quantity,duration)); self.ms.append(u); return u
        def r(a,b,it):
            v=R(a,b,it,self.rng.randint(1,maxlen),len(self.rs)); self.rs.append(v)
            a.routes.append(v); a.sent[v.index]=-1; a.order[v.index]=v.index
            b.accept_order[v.index]=v.index; return v
        self.core=M('协议核心取货'); self.sources.append(self.core)
        def ore(kind,i):
            if i<6: return self.core
            u=M('仓库取货口'+str(i)); self.sources.append(u); return u
        fe=[m('矿精炼'+str(i),{'蓝铁矿':1},'蓝铁块') for i in range(34)]
        fc=[m('铁粉碎'+str(i),{'蓝铁块':1},'蓝铁粉末') for i in range(34)]
        oc=[m('源粉碎'+str(i),{'源矿':1},'源石粉末') for i in range(18)]
        for i in range(34): r(ore('蓝铁矿',i),fe[i],'蓝铁矿'); r(fe[i],fc[i],'蓝铁块')
        for i in range(18): r(ore('源矿',34+i),oc[i],'源矿')
        gf=[m('铁研磨'+str(i),{'蓝铁粉末':2,'砂叶粉末':1},'致密蓝铁粉末') for i in range(17)]
        go=[m('源研磨'+str(i),{'源石粉末':2,'砂叶粉末':1},'致密源石粉末') for i in range(9)]
        gq=[m('荞研磨'+str(i),{'荞花粉末':2,'砂叶粉末':1},'细磨荞花粉末') for i in range(6)]
        for i,u in enumerate(gf): r(fc[2*i],u,'蓝铁粉末'); r(fc[2*i+1],u,'蓝铁粉末')
        for i,u in enumerate(go): r(oc[2*i],u,'源石粉末'); r(oc[2*i+1],u,'源石粉末')
        ks=[]; kq=[]
        for plant,n,k in [('砂叶',11,3),('荞花',6,2)]:
            sd=plant+'种子'; pw=plant+'粉末'
            for i in range(n):
                c=m(plant+'采种'+str(i),{plant:1},sd,2)
                a=m(plant+'种植A'+str(i),{sd:1},plant)
                b=m(plant+'种植B'+str(i),{sd:1},plant)
                z=m(plant+'粉碎'+str(i),{plant:1},pw,k)
                ca=r(c,a,sd); r(c,b,sd); ac=r(a,c,plant); r(b,z,plant)
                self.units.append((c,a,b,z,ca,ac)); (ks if k==3 else kq).append(z)
        sand=[u for i,u in enumerate(ks) for _ in range(2 if i==10 else 3)]
        self.rng.shuffle(sand)
        for u,v in zip(sand,gf+go+gq): r(u,v,'砂叶粉末')
        for u,v in zip(kq,gq): r(u,v,'荞花粉末'); r(u,v,'荞花粉末')
        st=[m('钢精炼'+str(i),{'致密蓝铁粉末':1},'钢块') for i in range(17)]
        pc=[m('配件'+str(i),{'钢块':1},'钢制零件') for i in range(6)]
        sh=[m('塑形'+str(i),{'钢块':2},'钢质瓶') for i in range(6)]
        for u,v in zip(gf,st): r(u,v,'致密蓝铁粉末')
        for i in range(6): r(st[i],pc[i],'钢块')
        for i in range(5): r(st[6+2*i],sh[i],'钢块'); r(st[7+2*i],sh[i],'钢块')
        r(st[16],sh[5],'钢块')
        packs=[m('封装'+str(i),{'钢制零件':10,'致密源石粉末':15},'高容谷地电池',1,40) for i in range(3)]
        fills=[m('灌装'+str(i),{'钢质瓶':10,'细磨荞花粉末':10},'精选荞愈胶囊',1,40) for i in range(3)]
        for i in range(3):
            for j in range(2): r(pc[2*i+j],packs[i],'钢制零件'); r(sh[2*i+j],fills[i],'钢质瓶'); r(gq[2*i+j],fills[i],'细磨荞花粉末')
            for j in range(3): r(go[3*i+j],packs[i],'致密源石粉末')
            r(packs[i],self.sink,'高容谷地电池'); r(fills[i],self.sink,'精选荞愈胶囊')
        self.fills=fills; self.sh=sh; self.ore_routes=[v for v in self.rs if v.source in self.sources]
        self.incoming={u:[] for u in self.ms+[self.sink]}
        for v in self.rs: self.incoming[v.target].append(v)
        if initial=='full':
            for u in self.ms:
                u.stock.update({k:50 for k in u.recipe[0]}); u.out=50
            for v in self.rs: v.cells=[-8]*len(v.cells)
        elif initial=='random':
            for u in self.ms:
                u.stock.update({k:self.rng.randrange(51) for k in u.recipe[0]}); u.out=self.rng.randrange(51)
                if self.rng.random()<.5: u.remaining=self.rng.randrange(1,u.recipe[3]+1)
            for v in self.rs: v.cells=[-self.rng.randrange(9) if self.rng.random()<.7 else None for _ in v.cells]
        for c,a,b,z,ca,ac in self.units:
            if initial in ('thin','exact'):
                c.stock[next(iter(c.recipe[0]))]=len(ca.cells)+len(ac.cells)+(3 if initial=='thin' else 2)
                if initial=='exact': c.out=1
        self.reorder()
    def reorder(self):
        for u in self.ms+self.sources:
            vals=list(range(len(u.routes))); self.rng.shuffle(vals)
            for v,j in zip(u.routes,vals): u.order[v.index]=j
        for u,vs in self.incoming.items():
            self.rng.shuffle(vs)
            for i,v in enumerate(vs): u.accept_order[v.index]=i
    def step(self):
        t=self.t
        for u in self.ms:
            if u.remaining:
                u.remaining-=1
                if not u.remaining: u.done=True; u.batches+=1
            u.flush()
        for u,vs in self.incoming.items():
            j=0 if u.cursor is None else next((i+1 for i,v in enumerate(vs) if v.index==u.cursor),0)%len(vs)
            for v in vs[j:]+vs[:j]:
                if v.cells[-1] is not None and t-v.cells[-1]>=8:
                    if u is self.sink:
                        ok=self.open
                        if ok: self.delivered[v.kind]+=1
                    else:
                        ok=u.stock[v.kind]<50
                        if ok: u.stock[v.kind]+=1
                    if ok: v.cells[-1]=None; u.cursor=v.index
                for p in range(len(v.cells)-2,-1,-1):
                    if v.cells[p] is not None and v.cells[p+1] is None and t-v.cells[p]>=8:
                        v.cells[p+1]=t; v.cells[p]=None
        for u in self.sources+self.ms:
            if u.recipe and not u.out: continue
            for v in sorted(u.routes,key=lambda v:(u.sent[v.index],u.order[v.index])):
                if v.cells[0] is None:
                    v.cells[0]=t; v.count+=1; u.sent[v.index]=t; u.count+=1
                    if u.recipe: u.out-=1; u.flush()
                    break
        for u in self.ms:
            if not u.done and not u.remaining and all(u.stock[k]>=v for k,v in u.recipe[0].items()):
                for k,v in u.recipe[0].items(): u.stock[k]-=v
                u.remaining=u.recipe[3]
        self.t+=1
    def state(self):
        return (tuple((tuple(u.stock[k] for k in u.recipe[0]),u.out,u.remaining,u.done,tuple(v.index for v in sorted(u.routes,key=lambda v:(u.sent[v.index],u.order[v.index]))),u.cursor) for u in self.ms),
                tuple(tuple(-1 if c is None else min(8,self.t-c) for c in v.cells) for v in self.rs),
                tuple(tuple(v.index for v in sorted(u.routes,key=lambda v:(u.sent[v.index],u.order[v.index]))) for u in self.sources),self.sink.cursor)
    def phi2(self):
        ans=[]
        for c,a,b,z,ca,ac in self.units:
            ans.append(2*(sum(x is not None for x in ca.cells+ac.cells)+sum(a.stock.values())+a.out+sum(c.stock.values())+bool(a.remaining or a.done)+bool(c.remaining or c.done))+c.out)
        return ans

def run(seed,maxlen,initial,limit=160000,interruptions=True):
    f=Factory(seed,maxlen,initial); p0=f.phi2(); pmin=p0[:]
    # The first 16000 steps include two long warehouse interruptions and reorder.
    for t in range(16000 if interruptions else 0):
        f.open= not (1000<=t<6000 or 7500<=t<14000)
        if t in (899,1200,5900,7501,13500,15999): f.reorder()
        f.step(); pmin=[min(a,b) for a,b in zip(pmin,f.phi2())]
    f.open=True; seen={}; max_bottle=0
    for t in range(limit):
        f.step(); max_bottle=max(max_bottle,f.fills[2].stock['钢质瓶'])
        pmin=[min(a,b) for a,b in zip(pmin,f.phi2())]
        # Cycle sampling every 8 steps only; period reported is exact for this sampling.
        if f.t%8: continue
        key=f.state(); now=(f.t,dict(f.delivered),[v.count for v in f.ore_routes])
        if key in seen:
            old=seen[key]; period=f.t-old[0]
            delta={k:f.delivered[k]-old[1].get(k,0) for k in f.delivered}
            ore=[v.count-q for v,q in zip(f.ore_routes,old[2])]
            return dict(seed=seed,maxlen=maxlen,initial=initial,machines=len(f.ms),routes=len(f.rs),period_steps=period,cycle_start=old[0],delivery=delta,ore_counts=ore,phi2_initial=p0,phi2_min=pmin,max_bottle_transient=max_bottle,pass_rates=delta['高容谷地电池']*40==period*3 and delta['精选荞愈胶囊']*160==period*11 and all(q*8==period for q in ore))
        seen[key]=now
    return dict(seed=seed,initial=initial,period_steps=None,status='inconclusive: no repeated state within step limit')

if __name__=='__main__':
    args=sys.argv[1:]
    if args: print(json.dumps(run(int(args[0]),int(args[1]),args[2],interruptions='nointerrupt' not in args),ensure_ascii=False))
    else:
        for i in range(6): print(json.dumps(run(920+i,1+i%3,['thin','random','full'][i%3]),ensure_ascii=False),flush=True)
