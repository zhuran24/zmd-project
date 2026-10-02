#!/usr/bin/env python3
"""Dense splitter/merger check using current sim2, with real warehouse seed circulation."""
import importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[4]
SRC = ROOT/'求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec=importlib.util.spec_from_file_location('order_sim2',SRC)
sim=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sim;spec.loader.exec_module(sim)
class Admission(sim.Gate):
    def __init__(self,name): super().__init__(name); self.next_allowed=0
    def can_accept(self,item,w): return w.t>=self.next_allowed and super().can_accept(item,w)
    def receive(self,item,w): super().receive(item,w);self.next_allowed=w.t+40
class Withdrawal(sim.Source):
    def __init__(self,name,warehouse): super().__init__(name,kinds=('荞花种子',)); self.warehouse=warehouse
    def ready_item(self,w): return self.candidate if self.warehouse.stock['荞花种子'] else None
    def pop_item(self,item,w): self.warehouse.stock['荞花种子']-=1;super().pop_item(item,w)
def run(early):
    core=sim.Warehouse('协议核心');core.stock['荞花种子']=80000
    s1=Withdrawal('仓库取货口甲',core);s2=Withdrawal('仓库取货口乙',core)
    a=sim.Belt('上游带甲',16);b=sim.Belt('上游带乙',16)
    p=Admission('准入口甲');q=Admission('准入口乙')
    d=sim.Splitter('分流器');u=sim.Gate('另一上游');m=sim.Merger('汇流器')
    c=sim.Belt('汇流后带');e=sim.Merger('分流另一支');f=sim.Belt('另一支后带',2)
    # True blueprint-compatible formation times. All belts are constructed last.
    # B is an UNCONFIGURED admission gate, hence a special transport unit.
    build = ({'汇流器':1,'另一上游':2,'分流器':3,'分流另一支':4}
             if early=='另一上游' else
             {'汇流器':1,'分流器':2,'分流另一支':3,'另一上游':4})
    c.connect(core,100);f.connect(core,102);m.connect(c,100);e.connect(f,101)
    d.connect(m,build['分流器']);d.connect(e,build['分流另一支']);u.connect(m,build['另一上游'])
    p.connect(d,5);q.connect(u,6);a.connect(p,125);b.connect(q,145);s1.connect(a,110);s2.connect(b,130)
    nodes=[core,s1,s2,a,b,p,q,d,u,m,c,e,f]; choices={'分流器':'汇流器'}
    layers=sim.layers_for(nodes,choices)
    comps=sorted([x for x in nodes if x.component],key=lambda x:(layers[x.name],min(z.connected for z in x.output_channels)))
    schedule={'choices':choices,'order':[x.name for x in comps]+[s1.name,s2.name,core.name]}
    w=sim.World(nodes,schedule=schedule,trace=False)
    seen={};cycle=None
    def key():
        cells=tuple(tuple(None if x is None else min(8,w.t-x.entered) for x in n.cells) for n in [a,b,p,q,d,u,m,c,e,f])
        return cells,max(0,p.next_allowed-w.t),max(0,q.next_allowed-w.t),(1 if d.output_cursor is None else d.output_cursor),core.stock['荞花种子']
    for _ in range(5000):
        k=key()
        if k in seen:
            cycle=(seen[k],w.t);break
        seen[k]=w.t;w.step()
    assert cycle
    lo,hi=cycle
    counts={name:sum(lo<=t<hi and dst==name for t,kind,dst in d.sent) for name in ['汇流器','分流另一支']}
    return {'early':early,'special_build_order':build,'channel_formation_times':{x.name+'→'+z.dst.name:z.connected for x in nodes for z in x.output_channels},'layers':layers,'cycle_steps':[lo,hi],'period_steps':hi-lo,'split_counts':counts,'other_input_count':sum(lo<=t<hi for t,kind,dst in u.sent),'merger_output_count':sum(lo<=t<hi for t,kind,dst in m.sent),'split_rates':{k:f'{8*v}/{hi-lo}' for k,v in counts.items()},'core_stock_min':min(k[-1] for k in seen),'cycle_events':[{'step':t-lo,'to':dst} for t,kind,dst in d.sent if lo<=t<hi]}
if __name__=='__main__':
    data=[run('另一上游'),run('分流器')]
    target=pathlib.Path(__file__).with_name('order_reference.json');target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps(data,ensure_ascii=False,indent=2))
