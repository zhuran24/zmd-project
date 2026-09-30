#!/usr/bin/env python3
"""只读导入 sim2，以 v4 输入独立生成每步共同投影（JSON 标准输出）。"""
import sys
sys.dont_write_bytecode=True
import argparse,json
from pathlib import Path
from collections import Counter
from step_inputs import ROOT
from step_graph import build,axis
SIM2=ROOT/'规则修订/2026-09-30-迟滞/sim2'
sys.path.insert(0,str(SIM2))
from simulator import Belt,Gate,BridgeAxis,Splitter,Merger,Machine,Recipe,Box,Warehouse,Source,Item,World,layers_for

def number(v):return int(v['value'])
def time(v):return number(v['value'])
class ConfiguredGate(Gate):
    def __init__(self,name,settings,counter):
        super().__init__(name);self.settings=settings
        self.total=number(counter['total_received']);self.received=number(counter['window_received'])
        self.started=None if counter['window_started_at'] is None else time(counter['window_started_at'])
    def can_accept(self,item,w):
        s=self.settings
        return super().can_accept(item,w) and (s['item'] is None or s['item']==item.kind) and (s['total_limit'] is None or self.total<number(s['total_limit'])) and (s['window_limit'] is None or self.received<number(s['window_limit']))
    def receive(self,item,w):
        super().receive(item,w);self.total+=1;self.received+=1
        if self.started is None:self.started=w.t
    def normalize(self,t):
        if self.started is not None and self.started+40<=t:self.started=None;self.received=0
class WarehouseSource(Source):
    def __init__(self,name,item,warehouse,sufficient):
        super().__init__(name,kinds=[item]);self.wh=warehouse;self.sufficient=sufficient
    def ready_item(self,w):
        return super().ready_item(w) if self.wh.stock[self.kinds[0]]>0 else None
    def pop_item(self,item,w):
        super().pop_item(item,w)
        if not (self.sufficient and item.kind in ('源矿','蓝铁矿')):self.wh.stock[item.kind]-=1

def adapt(raw,base):
    g=build(raw,base);st=raw['initial_state']['nonwarehouse']['value'];inv={r['slot']:r['contents'] for r in st['inventory']};progress={r['unit']:r for r in st['progress']};switch={(r['unit'],r['function']):r['enabled'] for r in raw['settings']['switches']}
    if any(n['kind']=='BeltRing' or (n['kind']=='桥接器' and len(n['outputs'])>1) for n in g['nodes'].values()):raise ValueError('sim2 共同域不含纯带环或两出口桥轴')
    cores=[n for n,x in g['nodes'].items() if x['kind']=='协议核心'];assert len(cores)==1
    wh=Warehouse(cores[0]);wh.stock=Counter({r['item']:number(r['quantity']) for r in st['warehouse']['slots'] if r['item'] and number(r['quantity'])})
    whslots={r['slot']:r for r in st['warehouse']['slots']};assign={r['port']:r['slot'] for r in raw['settings']['warehouse_assignments']}
    recipes={r['id']:r for r in g['catalog']['recipes']};recipe_order=axis(raw,'manufacturing.recipe_selection')['recipes'];slot_order=axis(raw,'manufacturing.input_slot_selection')['slots'];timing={r['unit']:r['timing'] for r in axis(raw,'transfer.timing')['values']};settings={r['unit']:r for r in raw['settings']['gates']};counters={r['unit']:r for r in st['logistics']['gate_counters']}
    def enabled(uid,f):return uid in g['powered'] and switch.get((uid,f),False)
    nodes={};slots={}
    def items(contents):
        return [Item(c['item'],time(c['entered_at']) if c['entered_at'] else -100,previous=('C|'+c['last_unit'] if c.get('last_unit') else '')) for c in contents for _ in range(number(c['quantity']))]
    for name,n in sorted(g['nodes'].items()):
        kind=n['kind'];uid=n['unit']
        if name.startswith('C|'):
            node=Belt(name,len(n['cells'])) if kind=='BeltChain' else Splitter(name) if kind=='分流器' else Merger(name) if kind=='汇流器' else BridgeAxis(name) if kind=='桥接器' else ConfiguredGate(name,settings[uid],counters[uid])
            node.cells=[next(iter(items(inv[s])),None) for s in n['cells']]
        elif kind=='协议核心':
            if n['outputs']:raise ValueError('sim2 不含协议核心送货')
            node=wh
        elif kind=='仓库取货口':
            assigned={whslots[assign[c['source_port']]]['item'] for c in g['channels'].values() if c['source_port'].split(':')[0]==uid}
            if len(assigned)>1:raise ValueError('共同域仓库取货口只含一种指派物种')
            node=WarehouseSource(uid,next(iter(assigned),'源矿'),wh,axis(raw,'warehouse.external_supply')['kind']=='sufficient')
        elif kind=='协议储存箱':
            node=Box(uid,wireless=enabled(uid,'transfer'),wireless_order='before' if timing[uid]=='before_send' else 'after',cooldown=time(progress[uid]['cooldown']),warehouse=wh)
            names=sorted((s for s in inv if s.startswith(uid+':storage:')),key=lambda s:int(s.rsplit(':',1)[1]));slots[uid]=names;node.slots=[items(inv[s]) for s in names]
        elif g['kinds'][kind]['family']=='manufacturing':
            rr=[]
            for rid in recipe_order:
                r=recipes[rid]
                if r['kind']!=kind:continue
                if len(r['outputs'])!=1:raise ValueError('sim2 配方仅一个输出物种')
                product,quantity=next(iter(r['outputs'].items()));rr.append(Recipe(rid,tuple((i,number(q)) for i,q in r['inputs'].items()),product,number(quantity),8*number(r['duration'])))
            node=Machine(uid,recipes=rr);names=[s for s in slot_order if s.startswith(uid+':input:')];slots[uid]=names;node.slots=[items(inv[s]) for s in names];node.output=items(inv[uid+':output:0']);p=progress[uid]
            if p['phase']=='working':node.running=next(r for r in rr if r.name==p['recipe']);node.remaining=time(p['remaining'])
            elif p['phase']=='completed':node.cache=items(inv[uid+':buffer:0'])
            node.powered=uid in g['powered'];node.enabled=switch[uid,'manufacture']
        else:raise ValueError('共同域未支持 '+kind)
        nodes[name]=node
    for cid in sorted(g['ends'],key=g['rank'].get):
        a,b=g['ends'][cid];nodes[a].connect(nodes[b],connected=g['rank'][cid])
    order=axis(raw,'step.order');choices={r['component']:r['downstream'] for r in order['layer_choices']};unknown={r['component']:number(r['layer']) for r in order['cycle_layers']}
    layers=layers_for(list(nodes.values()),choices,unknown)
    components=sorted((n for n in nodes if nodes[n].component),key=lambda n:(layers[n],min((c.connected for c in nodes[n].output_channels),default=float('inf')),n))
    nt=order['nontransport_order'];schedule={'choices':choices,'unknown':unknown,'order':components+nt}
    w=World(list(nodes.values()),schedule=schedule,motion='eager',trace=True);w.t=time(st['environment']['time'])
    cursors={c['side']:c['last_success'] for c in st['logistics']['poll_state']['cursors']}
    for name,node in nodes.items():
        for side in ('input','output'):
            channels=sorted(getattr(node,side+'_channels'),key=lambda c:c.connected)
            last=cursors.get(name+':'+side)
            value=(next(i for i,c in enumerate(channels) if c.connected==g['rank'][last])+1)%len(channels) if last else (1 if len(channels)>1 and ((isinstance(node,Splitter) and side=='output') or (isinstance(node,Merger) and side=='input')) else 0)
            setattr(node,side+'_cursor',value)
    for row in st['logistics']['poll_state']['recency']:
        node=nodes[row['unit']]
        for c in node.output_channels:node.last_output[c]=-len(row['order'])-1
        for i,cid in enumerate(row['order']):
            ch=next(c for c in node.output_channels if c.connected==g['rank'][cid]);node.last_output[ch]=i-len(row['order'])
    return w,g,nodes,slots,wh

def projections(raw,base,steps):
    w,g,nodes,slots,wh=adapt(raw,base);output=[]
    def stock_add(stock,slot,items):
        if items:stock[slot]=dict(Counter(i.kind for i in items))
    for _ in range(steps):
        at=w.t;start=len(w.events);w.step()
        for node in nodes.values():
            if isinstance(node,ConfiguredGate):node.normalize(w.t)
        transport={};stock={};machines={};boxes={}
        for name,node in nodes.items():
            if node.component:
                for slot,item in zip(g['nodes'][name]['cells'],node.cells):
                    if item:transport[slot]=[item.kind,w.t-item.entered]
            elif isinstance(node,Machine):
                for slot,items in zip(slots[name],node.slots):stock_add(stock,slot,items)
                stock_add(stock,name+':output:0',node.output)
                cache=[Item(item) for item,n in node.running.ingredients for _ in range(n)] if node.running else node.cache
                stock_add(stock,name+':buffer:0',cache)
                machines[name]=['working' if node.running else 'completed' if node.cache else 'idle',node.remaining]
            elif isinstance(node,Box):
                for slot,items in zip(slots[name],node.slots):stock_add(stock,slot,items)
                boxes[name]=node.cooldown
        moves=[[e['unit'],e['destination'],e['kind']] for e in w.events[start:] if e['event']=='send']
        output.append(dict(step=at,moves=moves,transport=transport,stock=stock,machines=machines,boxes=boxes,warehouse={i:n for i,n in wh.stock.items() if n}))
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--steps',type=int,required=True);a=p.parse_args()
    print(json.dumps(projections(json.loads(a.input.read_text()),a.input.parent,a.steps),ensure_ascii=False))
