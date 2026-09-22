"""任务7独立事务审计：逐事件重算部分接收、编号箱格、仓库账和冷却。只读。"""
import copy,json,sys,collections
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'数据/样例'))
from checkpoint_delta import decode_trace
PRODUCTS=('高容谷地电池','精选荞愈胶囊')
FLOWS=('core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment')
def n(v):
    f=Fraction(v['value']);assert f.denominator==1;return int(f)
def tm(v):return n(v['value'])
def amount(state):
    return collections.Counter({r['item']:n(r['quantity']) for r in state['warehouse']['slots'] if r['item']})
def audit_ledger(record,data):
    trace=decode_trace(record['trace']);previous=trace['start_state']
    units={u['id']:u['kind'] for u in data['layout']['units']};boxes={u for u,k in units.items() if k=='协议储存箱'}
    channels={c['id']:c for c in data['layout']['physical_channels']};assign={r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    catalog=json.loads(Path(data['catalog']['path']).read_text());kinds={u['id']:u for u in catalog['units']}
    capacity=n(next(s['capacity'] for s in kinds['协议核心']['inventory'] if s['role']=='warehouse'))
    boxcap=n(kinds['协议储存箱']['inventory'][0]['capacity']);cooltime=n(kinds['协议储存箱']['transfer']['cooldown_ticks'])
    switches={r['unit']:r['enabled'] for r in data['settings']['switches'] if r['function']=='transfer'}
    transactions=0
    for index,tick in enumerate(trace['ticks']):
        advance=index>0 or previous['semantic_context']['judgment_context']['value']['phase']=='after_closure'
        assert tm(tick['time'])==tm(previous['environment']['time'])+advance
        ledger=tick['warehouse_ledger'];assert ledger['player_withdrawal']==[]
        totals={p:{f:0 for f in FLOWS} for p in PRODUCTS}
        for f in FLOWS:
            for row in ledger[f]:
                assert n(row['quantity'])>0
                totals.setdefault(row['item'],{k:0 for k in FLOWS})[f]+=n(row['quantity'])
        actual={r['item']:{k:n(v) for k,v in r.items() if k!='item'} for r in ledger['totals']}
        expected={i:{**v,'actual_inbound':v['core_inbound']+v['wireless_inbound']} for i,v in sorted(totals.items())}
        assert actual==expected and [r['item'] for r in ledger['totals']]==sorted(expected)
        wh=amount(previous)
        if record['execution_mode']=='production_abstraction':
            assert {r['item']:n(r['quantity']) for r in ledger['representative_adjustment']}=={p:wh[p] for p in PRODUCTS if wh[p]}
            for p in PRODUCTS:wh[p]=0
        else:assert ledger['representative_adjustment']==[]
        stock={r['slot']:collections.Counter({c['item']:sum(n(x['quantity']) for x in r['contents'] if x['item']==c['item']) for c in r['contents']}) for r in previous['inventory'] if r['slot'].split(':')[0] in boxes}
        def slots(u):return sorted([s for s in stock if s.split(':')[0]==u],key=lambda s:int(s.rsplit(':',1)[1]))
        def total(u):return sum((stock[s] for s in slots(u)),collections.Counter())
        movements={r['event']:r for r in tick['state']['semantic_context']['tick_context']['value']['movements']}
        inbound=[];outbound=[];wireless=[];external=[]
        for event in tick['events']:
            eid=event['event']
            if event['operation']=='move' and event['outcome']=='success':
                move=movements[eid];c=channels[move['channel']];src,dst=c['source_port'],c['target_port'];a,b=src.split(':')[0],dst.split(':')[0];item=move['item'];assert n(move['quantity'])==1
                if a in boxes:
                    slot=next(s for s in slots(a) if +stock[s]);assert stock[slot][item]>0;stock[slot][item]-=1
                if b in boxes:
                    slot=next(s for s in slots(b) if not +stock[s] or (stock[s][item]>0 and sum(stock[s].values())<boxcap));stock[slot][item]+=1
                qty={'value':'1','category':'算术推论'}
                if units[b]=='协议核心':
                    assert wh[item]<capacity;wh[item]+=1;inbound.append(dict(event=eid,channel=c['id'],port=dst,item=item,quantity=qty))
                if src in assign:
                    assert wh[item]>0;wh[item]-=1;outbound.append(dict(event=eid,channel=c['id'],port=src,slot=assign[src],item=item,quantity=qty))
                    supply=data['parameters']['fixedness_unproven']['warehouse.external_supply']['value']
                    if supply['kind']=='sufficient' and item in ('源矿','蓝铁矿'):
                        wh[item]+=1;external.append(dict(event=eid,mode='sufficient',item=item,quantity=qty))
            if event['operation']=='transfer' and event['outcome'] in ('success','failure'):
                u=event['target'];before=total(u);sent={i:min(v,capacity-wh[i]) for i,v in before.items()};sent={i:v for i,v in sent.items() if v}
                assert all(v>=0 for v in sent.values())
                for item,qty in sorted(sent.items()):
                    targets=[s for s in slots(u) if stock[s][item]]
                    assert qty==before[item] or len(targets)==1,'未定义跨格部分残留不得提交'
                    left=qty
                    for slot in targets:
                        take=min(stock[slot][item],left);stock[slot][item]-=take;left-=take
                    assert left==0;wh[item]+=qty
                    wireless.append(dict(event=eid,unit=u,item=item,quantity={'value':str(qty),'category':'算术推论'}));transactions+=1
                detail=json.loads(event['detail']);assert detail=={'sent':sent,'retained':dict(+total(u)),'cooldown_restarted':True}
                assert event['outcome']==('failure' if before and not sent else 'success')
            if event['operation']=='ore_supply':
                row=json.loads(event['detail']);wh[row['item']]+=n(row['quantity']);assert wh[row['item']]<=capacity
                external.append(dict(event=eid,mode='explicit_ore_history',item=row['item'],quantity={'value':str(n(row['quantity'])),'category':'算术推论'}))
        assert ledger['core_inbound']==inbound and ledger['port_outbound']==outbound and ledger['wireless_inbound']==wireless and ledger['external_supply']==external
        assert +wh==+amount(tick['state']) and all(v>=0 for v in wh.values())
        for row in tick['state']['inventory']:
            if row['slot'] in stock:
                got=collections.Counter()
                for c in row['contents']:got[c['item']]+=n(c['quantity'])
                assert +stock[row['slot']]==got,(row['slot'],stock[row['slot']],got)
        oldcool={p['unit']:tm(p['cooldowns'][0]['remaining']) for p in previous['progress'] if p['unit'] in boxes}
        newcool={p['unit']:tm(p['cooldowns'][0]['remaining']) for p in tick['state']['progress'] if p['unit'] in boxes}
        for u in boxes:
            events=[v for v in tick['events'] if v['operation']=='transfer' and v['target']==u]
            disabled=any(v['detail']=='function_disabled' for v in events)
            remaining=max(0,oldcool[u]-advance) if switches[u] and not disabled else oldcool[u]
            for v in events:
                if v['outcome'] in ('success','failure'):
                    assert switches[u] and remaining==0;remaining=cooltime
            assert newcool[u]==remaining,(u,oldcool[u],newcool[u],events)
        previous=tick['state']
    return {'ticks':len(trace['ticks']),'wireless_item_transactions':transactions}
