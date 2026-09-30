#!/usr/bin/env python3
"""v5 独立台账审计：stdin {input,input_base,record}；stdout JSON；不写文件。"""
import sys
sys.dont_write_bytecode=True
import copy,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'数据/工具'))
from step_graph import build,axis
PRODUCTS=('高容谷地电池','精选荞愈胶囊');ORES=('源矿','蓝铁矿')
FLOWS=('core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment')
def n(v):return int(v['value'])
def tm(v):assert v['kind']=='step';return n(v['value'])
def q(n):return {'value':str(n),'category':'算术推论'}
def counts(contents):
    c=Counter()
    for r in contents:c[r['item']]+=n(r['quantity'])
    return c

def delta(a,b,path=()):
    if a==b:return []
    if isinstance(a,dict) and isinstance(b,dict) and a.keys()==b.keys():return [op for k in sorted(a) for op in delta(a[k],b[k],(*path,k))]
    assert path
    return [{'op':'replace','path':list(path),'value':b}]
def decode_trace(trace):
    out=copy.deepcopy(trace);previous=out['start_state']
    if out['format']=='full_state_each_step':
        assert all('state' in r and 'delta' not in r for r in out['steps']);return out
    assert out['format']=='checkpoint_delta' and out['delta_encoding']=='object_replace_v1'
    k=out['checkpoint_interval'];assert isinstance(k,int) and k>0
    for i,row in enumerate(out['steps']):
        if i%k==0:assert 'state' in row and 'delta' not in row
        else:
            assert 'state' not in row and isinstance(row['delta'],list)
            state=copy.deepcopy(previous)
            for op in row['delta']:
                assert set(op)=={'op','path','value'} and op['op']=='replace' and op['path']
                at=state
                for key in op['path'][:-1]:assert isinstance(at,dict) and key in at;at=at[key]
                assert isinstance(at,dict) and op['path'][-1] in at;at[op['path'][-1]]=op['value']
            assert delta(previous,state)==row['delta'];row['state']=state;del row['delta']
        previous=row['state']
    return out

def check_schema(values):
    """AJV 2020 只读内存校验；配置路径可用 KERNEL_AJV 指定。"""
    import os,subprocess
    candidates=[os.environ.get('KERNEL_AJV',''),str(Path.home()/'.local/lib/devspace/node_modules/ajv/dist/2020.js')]
    candidates += [str(p) for p in sorted((Path.home()/'.local/lib/devspace-versions').glob('*/node_modules/ajv/dist/2020.js'),reverse=True)]
    module=next((p for p in candidates if p and Path(p).is_file()),'ajv/dist/2020.js')
    script="const fs=require('fs');const Ajv=require(process.argv[1]);const schema=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const v=new Ajv({strict:false,allErrors:true}).compile(schema);for(const x of JSON.parse(fs.readFileSync(0,'utf8'))){if(!v(x)){console.error(JSON.stringify(v.errors));process.exit(1);}}"
    r=subprocess.run(['node','-e',script,module,str(ROOT/'规格/内核输出.schema.json')],input=json.dumps(values,ensure_ascii=False),text=True,capture_output=True)
    assert r.returncode==0,r.stderr

def audit_ledger(record,raw,base=None):
    assert record['schema']=='kernel-output-v5' and raw['schema']=='kernel-input-v4'
    assert record['execution_mode'] in ('finite_concrete','production_abstraction')
    g=build(raw,base or ROOT);units=g['units'];boxes={u for u,r in units.items() if r['kind']=='协议储存箱'}
    assign={r['port']:r['slot'] for r in raw['settings']['warehouse_assignments']};switches={(r['unit'],r['function']):r['enabled'] for r in raw['settings']['switches']}
    enabled={u for u in boxes if u in g['powered'] and switches[u,'transfer']}
    timing={r['unit']:r['timing'] for r in axis(raw,'transfer.timing')['values']}
    capacity=n(g['kinds']['协议核心']['inventory'][0]['capacity']);boxcap=n(g['kinds']['协议储存箱']['inventory'][0]['capacity']);cooltime=n(g['kinds']['协议储存箱']['transfer']['cooldown_ticks'])*n(g['catalog']['timing']['steps_per_tick'])
    supply=axis(raw,'warehouse.external_supply');trace=decode_trace(record['trace']);previous=trace['start_state'];transactions=0
    for row in trace['steps']:
        step=row['step'];assert isinstance(step,int) and step==tm(previous['environment']['time']) and tm(row['state']['environment']['time'])==step+1
        events=row['events'];ids={e['event'] for e in events};assert [e['event'] for e in events]==[f'E|{step}|{i}' for i in range(len(events))]
        ledger=row['warehouse_ledger'];assert set(ledger)=={*FLOWS,'totals'};expected={f:[] for f in FLOWS}
        wh=counts([r for r in previous['warehouse']['slots'] if r['item']])
        if record['execution_mode']=='production_abstraction':
            for slot in previous['warehouse']['slots']:
                if slot['item'] in PRODUCTS and n(slot['quantity']):expected['representative_adjustment'].append({'item':slot['item'],'quantity':q(n(slot['quantity'])),'reason':'production_representative'})
            for item in PRODUCTS:wh[item]=0
        stock={r['slot']:counts(r['contents']) for r in previous['inventory'] if r['slot'].split(':')[0] in boxes}
        def slots(u):return sorted((s for s in stock if s.split(':')[0]==u),key=lambda s:int(s.rsplit(':',1)[1]))
        def total(u):return sum((stock[s] for s in slots(u)),Counter())
        cooldown={p['unit']:tm(p['cooldown']) for p in previous['progress'] if p['unit'] in boxes}
        for u in enabled:cooldown[u]=max(0,cooldown[u]-1)
        transferred=set()
        def transfer(e):
            nonlocal transactions
            u=e['subject'];assert u in enabled and u not in transferred and cooldown[u]==0
            transferred.add(u);before=total(u);sent={i:min(v,capacity-wh[i]) for i,v in sorted(before.items()) if v};sent={i:v for i,v in sent.items() if v}
            assert all(v>0 for v in sent.values())
            for item,quantity in sent.items():
                targets=[s for s in slots(u) if stock[s][item]];assert quantity==before[item] or len(targets)==1,'多格严格部分残留未定义'
                remaining=quantity
                for s in targets:take=min(stock[s][item],remaining);stock[s][item]-=take;remaining-=take
                assert remaining==0;wh[item]+=quantity;expected['wireless_inbound'].append(dict(event=e['event'],unit=u,item=item,quantity=q(quantity)));transactions+=1
            assert e['detail']['transfer']=={'sent':sent,'retained':dict(+total(u)),'cooldown_restarted':True}
            cooldown[u]=cooltime
        for event in events:
            assert set(event)=={'event','phase','subject','moves','detail'} and event['phase'] in ('supply','complete','flush','judge','start')
            eid=event['event'];has_transfer=isinstance(event['detail'],dict) and 'transfer' in event['detail']
            if has_transfer and timing[event['subject']]=='before_send':transfer(event)
            if event['phase']=='supply':
                v=event['detail'];assert v in supply.get('events',[]) and tm(v['time'])==step
                item=v['item'];quantity=n(v['quantity']);wh[item]+=quantity;assert wh[item]<=capacity
                expected['external_supply'].append(dict(event=eid,mode='explicit_ore_history',item=item,quantity=q(quantity)))
            for move in event['moves']:
                assert event['phase']=='judge' and set(move)=={'channel','item'}
                ch=g['channels'][move['channel']];src=ch['source_port'];dst=ch['target_port'];a,b=src.split(':')[0],dst.split(':')[0];item=move['item']
                if a in boxes:
                    s=next(s for s in slots(a) if +stock[s]);assert stock[s][item]>0;stock[s][item]-=1
                if b in boxes:
                    s=next(s for s in slots(b) if not +stock[s] or stock[s][item]>0 and sum(stock[s].values())<boxcap);stock[s][item]+=1
                if units[b]['kind']=='协议核心':
                    assert wh[item]<capacity;wh[item]+=1;expected['core_inbound'].append(dict(event=eid,channel=ch['id'],unit=b,item=item,quantity=q(1)))
                if src in assign:
                    old=next(r for r in previous['warehouse']['slots'] if r['slot']==assign[src]);assert old['item']==item and wh[item]>0;wh[item]-=1
                    expected['port_outbound'].append(dict(event=eid,channel=ch['id'],port=src,item=item,quantity=q(1)))
                    if supply['kind']=='sufficient' and item in ORES:wh[item]+=1;expected['external_supply'].append(dict(event=eid,mode='sufficient',item=item,quantity=q(1)))
            if has_transfer and timing[event['subject']]=='after_send':transfer(event)
        assert transferred=={u for u in enabled if max(0,next(tm(p['cooldown']) for p in previous['progress'] if p['unit']==u)-1)==0},'缺传输尝试事件'
        totals={item:{f:0 for f in FLOWS} for item in PRODUCTS}
        for f in FLOWS:
            assert ledger[f]==expected[f],(step,f,ledger[f],expected[f])
            for r in ledger[f]:
                assert n(r['quantity'])>0 and (r.get('event') in ids or f=='representative_adjustment')
                totals.setdefault(r['item'],{f:0 for f in FLOWS})[f]+=n(r['quantity'])
        want=[{'item':item,**{f:q(v) for f,v in values.items()},'actual_inbound':q(values['core_inbound']+values['wireless_inbound'])} for item,values in sorted(totals.items())]
        assert ledger['totals']==want
        got=counts([r for r in row['state']['warehouse']['slots'] if r['item']]);assert +wh==+got and all(n>=0 for n in wh.values())
        for inv in row['state']['inventory']:
            if inv['slot'] in stock:assert +stock[inv['slot']]==counts(inv['contents']),(step,inv['slot'])
        for p in row['state']['progress']:
            if p['unit'] in boxes:assert tm(p['cooldown'])==cooldown[p['unit']],(step,p['unit'],'cooldown')
        previous=row['state']
    assert trace['end_step']==tm(previous['environment']['time'])
    return {'steps':len(trace['steps']),'wireless_item_transactions':transactions}
if __name__=='__main__':
    payload=json.load(sys.stdin)
    if 'schema_values' in payload:
        check_schema(payload['schema_values']);print(json.dumps({'schema_checked':len(payload['schema_values'])}));sys.exit(0)
    check_schema([payload['record']])
    print(json.dumps(audit_ledger(payload['record'],payload['input'],payload.get('input_base')),ensure_ascii=False))
